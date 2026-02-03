"""
Inverse Strategy Tournament.

A tournament where a Learner agent recovers a Target's strategy.

Design:
- Learner: Can edit code (LLM agent), does NOT play in simulation
- Target: Static code (strategy to be recovered), plays in simulation
- Opponent: Static code (plays against target), can be same as target for self-play

Flow:
1. Round 0: Run simulation (Target vs Opponent) → baseline traces
2. Round N (N >= 1):
   a. Edit Phase: Learner edits code based on traces from round N-1
   b. Simulation Phase: Run game (Target vs Opponent, NOT learner) → new traces
   c. Evaluation Phase: Query learner's code on target's states (offline)
   d. Compute accuracy: Does learner produce same action as target for same state?

The learner receives:
- logs/rounds/N-1/sim_*.jsonl - Raw game traces (target's states and actions)
- logs/rounds/N-1/traces.json - Parsed summary with accuracy metrics
- logs/rounds/N-1/eval_results.json - Evaluation results (mismatches for debugging)

Key insight: Learner never plays in the game. Evaluation is offline - we feed
target's states to learner's code and compare actions.
"""

import json
from pathlib import Path
from typing import Any

from codeclash.agents import get_agent
from codeclash.agents.player import Player
from codeclash.agents.utils import GameContext
from codeclash.arenas import get_arena
from codeclash.arenas.arena import CodeArena
from codeclash.constants import DIR_LOGS, DIR_WORK, FILE_RESULTS
from codeclash.tournaments.tournament import AbstractTournament
from codeclash.utils.atomic_write import atomic_write
from codeclash.utils.aws import is_running_in_aws_batch, s3_log_sync
from codeclash.utils.environment import copy_to_container


class InverseStrategyTournament(AbstractTournament):
    """
    Tournament for inverse strategy learning.
    
    Learner tries to recover Target's strategy by:
    1. Observing traces from Target vs Opponent simulations
    2. Writing/editing code to reproduce Target's behavior
    
    Key design: Learner does NOT play in simulations. Evaluation is offline -
    we query learner's code with target's states and compare actions.
    """
    
    def __init__(
        self,
        config: dict,
        *,
        output_dir: Path,
        cleanup: bool = False,
        keep_containers: bool = False,
    ):
        metadata_file = output_dir / "metadata.json"
        if metadata_file.exists():
            raise FileExistsError(f"Metadata file already exists: {metadata_file}")

        super().__init__(config, name="InverseStrategyTournament", output_dir=output_dir)
        self.cleanup_on_end = cleanup
        
        # Initialize game arena
        self.game: CodeArena = get_arena(
            self.config,
            tournament_id=self.tournament_id,
            local_output_dir=self.local_output_dir,
            keep_containers=keep_containers,
        )
        
        # Initialize all agents from config
        self.agents: list[Player] = []
        player_configs = self.config["players"]
        
        if len(player_configs) < 2:
            raise ValueError("InverseStrategyTournament requires at least 2 players (learner + target)")
        if len(player_configs) > 3:
            raise ValueError("InverseStrategyTournament supports at most 3 players (learner + target + opponent)")
        
        for agent_conf in player_configs:
            self.agents.append(self.get_agent(agent_conf, self.config["prompts"]))
        
        # Identify agent roles
        self.learner_agent: Player = self._get_learner_agent()
        self.target_agent: Player = self._get_target_agent()
        self.opponent_agent: Player = self._get_opponent_agent()
        
        # Agents that participate in the simulation (NOT learner)
        self.game_agents: list[Player] = [self.target_agent, self.opponent_agent]
        
        self.logger.info(f"Learner agent: {self.learner_agent.name} (edits code, does NOT play)")
        self.logger.info(f"Target agent: {self.target_agent.name} (strategy to recover)")
        self.logger.info(f"Opponent agent: {self.opponent_agent.name} (plays against target)")

    def _get_learner_agent(self) -> Player:
        """Get the agent that can edit (learner). Does not play in simulation."""
        for i, agent_conf in enumerate(self.config["players"]):
            if agent_conf.get("editable", False):
                return self.agents[i]
        # Default to first agent if none explicitly marked
        return self.agents[0]
    
    def _get_target_agent(self) -> Player:
        """Get the target agent (strategy to be recovered)."""
        for i, agent_conf in enumerate(self.config["players"]):
            if agent_conf.get("name") == "target":
                return self.agents[i]
        # If no explicit target, use first non-learner agent
        for agent in self.agents:
            if agent != self.learner_agent:
                return agent
        raise ValueError("Could not identify target agent")
    
    def _get_opponent_agent(self) -> Player:
        """Get the opponent agent (plays against target in simulation).
        
        If not explicitly specified, defaults to target (self-play).
        """
        for i, agent_conf in enumerate(self.config["players"]):
            if agent_conf.get("name") == "opponent":
                return self.agents[i]
        # Default: use target as opponent (self-play)
        self.logger.info("No explicit opponent specified, using target for self-play")
        return self.target_agent

    @property
    def metadata_file(self) -> Path:
        return self.local_output_dir / "metadata.json"

    @property
    def rounds(self) -> int:
        return self.config["tournament"]["rounds"]

    def get_metadata(self) -> dict:
        return {
            **super().get_metadata(),
            "game": self.game.get_metadata(),
            "agents": [agent.get_metadata() for agent in self.agents],
            "learner": self.learner_agent.name,
            "target": self.target_agent.name,
            "opponent": self.opponent_agent.name,
            "game_agents": [a.name for a in self.game_agents],
        }

    def get_agent(self, agent_config: dict, prompts: dict) -> Player:
        """Create an agent with environment and game context."""
        environment = self.game.get_environment(f"{self.game.game_id}.{agent_config['name']}")

        game_context = GameContext(
            id=self.game.game_id,
            log_env=self.game.log_env,
            log_local=self.game.log_local,
            name=self.game.name,
            player_id=agent_config["name"],
            prompts=prompts,
            round=1,
            rounds=self.rounds,
            working_dir=str(DIR_WORK),
        )

        return get_agent(agent_config, game_context, environment)

    def run(self) -> None:
        """Main execution function that runs all rounds."""
        try:
            # Round 0: Initial simulation (Target vs Opponent, no editing)
            self.run_simulation_phase(0)
            self.run_evaluation_phase(0)
            
            for round_num in range(1, self.rounds + 1):
                self.run_edit_phase(round_num)
                self.run_simulation_phase(round_num)
                self.run_evaluation_phase(round_num)
            
            # Compress the last round
            self._compress_round_folder(self.rounds)
        finally:
            self.end()

    def run_simulation_phase(self, round_num: int) -> None:
        """
        Run game simulations (Target vs Opponent, NOT learner).
        
        Steps:
        1. Run game via Arena with game_agents (target + opponent)
        2. Produces sim_X.jsonl files with target's states and actions
        
        Note: Learner does NOT participate in simulation.
        """
        self.logger.info(f"Running simulation: {self.target_agent.name} vs {self.opponent_agent.name}")
        
        # Run the game round with ONLY game agents (target + opponent)
        stats = self.game.run_round(self.game_agents, round_num)
        self.logger.info(stats)

        # Store basic stats
        self._metadata.setdefault("round_stats", {})[round_num] = stats.to_dict()

        # Create directory for round logs
        round_dir = self.game.log_local / "rounds" / str(round_num)
        round_dir.mkdir(parents=True, exist_ok=True)

        # Write results
        results_file = round_dir / FILE_RESULTS
        results_file.write_text(json.dumps(stats.to_dict(), indent=2))

        self._save()

    def run_evaluation_phase(self, round_num: int) -> None:
        """
        Evaluate learner's code on target's states (offline).
        
        For each (target_state, target_action) in traces:
            learner_action = learner_code(target_state)
            compare(learner_action, target_action)
        
        This measures: "If learner was in target's position, would it act the same?"
        """
        round_dir = self.game.log_local / "rounds" / str(round_num)
        
        # Process traces and compute accuracy
        trace_summary = self._process_traces(round_dir, round_num)
        
        # Store accuracy in metadata
        if trace_summary:
            self._metadata.setdefault("accuracy_history", {})[round_num] = trace_summary.get("accuracy", 0.0)
            self._metadata.setdefault("evaluation_failed", {})[round_num] = False
            self.logger.info(f"Round {round_num} strategy recovery accuracy: {trace_summary.get('accuracy', 0.0):.2%}")
        else:
            # Evaluation failed - record explicitly
            self._metadata.setdefault("accuracy_history", {})[round_num] = None
            self._metadata.setdefault("evaluation_failed", {})[round_num] = True
            self.logger.warning(f"Round {round_num} evaluation failed - no accuracy recorded")

        self._save()

    def _process_traces(self, round_dir: Path, round_num: int) -> dict[str, Any] | None:
        """
        Offline evaluation: Query learner's code with target's states.
        
        For each turn in the simulation traces:
        1. Extract target's state (what target saw)
        2. Extract target's action (what target did)
        3. Query learner's code with target's state
        4. Compare learner's action vs target's action
        
        Returns a summary dict saved to traces.json:
        {
            "round": N,
            "total_actions": 1000,        # Total target actions evaluated
            "matching_actions": 750,      # Learner matches target
            "accuracy": 0.75,             # Pooled accuracy
            "learner": "learner",
            "target": "target",
            "per_simulation": [...],      # Per-sim breakdown
            "sample_mismatches": [...]    # Examples for debugging
        }
        """
        # Find all sim files
        sim_files = sorted(round_dir.glob("sim_*.jsonl")) + sorted(round_dir.glob("sim_*.json"))
        if not sim_files:
            self.logger.warning(f"No simulation files found in {round_dir}")
            return None
        
        game_name = self.game.name
        
        # Import game-specific functions from parser
        if game_name == "BattleSnake":
            from codeclash.traces.parsers.battlesnake import (
                actions_equal,
                extract_state_action_pairs,
            )
        else:
            self.logger.warning(f"No offline evaluation support for game {game_name}")
            return None
        
        # Setup: Copy learner code to host and load module
        learner_code_dir = self._setup_learner_for_eval(round_dir)
        if learner_code_dir is None or not self._load_learner_module(learner_code_dir):
            self.logger.warning("Failed to setup learner for offline evaluation")
            return None
        
        total_actions = 0
        matching_actions = 0
        per_simulation = []
        all_mismatches = []  # Collect ALL mismatches for debugging
        
        learner_name = self.learner_agent.name
        target_name = self.target_agent.name
        
        # Query learner's code for each target state
        for sim_file in sim_files:
            try:
                sim_total = 0
                sim_matching = 0
                sim_mismatches = []
                
                # Use parser to extract all state-action pairs for target
                state_action_pairs = extract_state_action_pairs(sim_file, target_name)
                
                for turn_idx, (target_state, target_action) in enumerate(state_action_pairs):
                    # Query learner's code with target's state (offline)
                    learner_action = self._query_learner(target_state)
                    if learner_action is None:
                        continue
                    
                    sim_total += 1
                    if actions_equal(learner_action, target_action):
                        sim_matching += 1
                    else:
                        # Record mismatch with full state for debugging
                        mismatch = {
                            "sim_file": sim_file.name,
                            "turn": target_state.get("turn", turn_idx),
                            "learner_action": learner_action,
                            "target_action": target_action,
                            "state": target_state,  # Full state for debugging
                        }
                        sim_mismatches.append(mismatch)
                        all_mismatches.append(mismatch)
                
                total_actions += sim_total
                matching_actions += sim_matching
                
                per_simulation.append({
                    "file": sim_file.name,
                    "total": sim_total,
                    "matching": sim_matching,
                    "accuracy": sim_matching / sim_total if sim_total > 0 else 0.0,
                    "num_mismatches": len(sim_mismatches),
                })
                
            except Exception as e:
                self.logger.warning(f"Error processing {sim_file}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Compute statistics
        accuracy = matching_actions / total_actions if total_actions > 0 else 0.0
        
        sim_accuracies = [s["accuracy"] for s in per_simulation if s["total"] > 0]
        if sim_accuracies:
            import statistics
            mean_accuracy = statistics.mean(sim_accuracies)
            accuracy_std = statistics.stdev(sim_accuracies) if len(sim_accuracies) > 1 else 0.0
            accuracy_se = accuracy_std / (len(sim_accuracies) ** 0.5) if sim_accuracies else 0.0
        else:
            mean_accuracy = 0.0
            accuracy_std = 0.0
            accuracy_se = 0.0
        
        summary = {
            "round": round_num,
            "game": game_name,
            "learner": learner_name,
            "target": target_name,
            "evaluation_type": "offline",  # Evaluated offline: learner_code(target_state) vs target_action
            "total_actions": total_actions,
            "matching_actions": matching_actions,
            "accuracy": accuracy,
            "mean_accuracy": mean_accuracy,
            "accuracy_std": accuracy_std,
            "accuracy_se": accuracy_se,
            "num_simulations": len(per_simulation),
            "per_simulation": per_simulation,
            "mismatches": all_mismatches,  # ALL mismatches with full state
        }
        
        # Save traces.json
        traces_file = round_dir / "traces.json"
        traces_file.write_text(json.dumps(summary, indent=2))
        self.logger.info(f"Saved trace summary to {traces_file}")
        
        return summary
    
    def _setup_learner_for_eval(self, round_dir: Path) -> Path | None:
        """Copy learner's code from container to host for direct import.
        
        Returns the path to the copied workspace, or None if failed.
        """
        try:
            from codeclash.utils.environment import copy_from_container
            
            # Copy learner's /workspace to local eval directory
            eval_dir = round_dir / "learner_code"
            eval_dir.mkdir(parents=True, exist_ok=True)
            
            copy_from_container(
                self.learner_agent.environment,
                Path("/workspace"),
                eval_dir,
            )
            
            self.logger.debug(f"Copied learner code to {eval_dir}")
            return eval_dir
            
        except Exception as e:
            self.logger.warning(f"Failed to copy learner code: {e}")
            return None
    
    def _load_learner_module(self, learner_code_dir: Path) -> bool:
        """Load the learner's main.py as a Python module.
        
        Returns True if successful, False otherwise.
        """
        import importlib.util
        import sys
        
        # copy_from_container copies /workspace as a subdirectory
        # So the actual code is in learner_code/workspace/main.py
        workspace_dir = learner_code_dir / "workspace"
        if workspace_dir.exists():
            main_py = workspace_dir / "main.py"
            code_dir = workspace_dir
        else:
            # Fallback to direct path
            main_py = learner_code_dir / "main.py"
            code_dir = learner_code_dir
        
        if not main_py.exists():
            self.logger.warning(f"Learner main.py not found at {main_py}")
            return False
        
        try:
            # Add learner's code directory to path for any relative imports
            if str(code_dir) not in sys.path:
                sys.path.insert(0, str(code_dir))
            
            # Load the module
            spec = importlib.util.spec_from_file_location("learner_main", main_py)
            if spec is None or spec.loader is None:
                self.logger.warning("Failed to create module spec")
                return False
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Verify it has a move function (accept both move() and choose_move())
            # TODO: Better solution - specify expected function name in config or prompt
            if hasattr(module, 'move'):
                self._learner_move_func = module.move
            elif hasattr(module, 'choose_move'):
                self._learner_move_func = module.choose_move
                self.logger.info("Using choose_move() instead of move()")
            else:
                self.logger.warning("Learner main.py has no move() or choose_move() function")
                return False
            
            self._learner_module = module
            self.logger.info(f"Loaded learner module from {main_py}")
            return True
            
        except Exception as e:
            self.logger.warning(f"Failed to load learner module: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _query_learner(self, state: dict) -> str | None:
        """Query learner's code with a game state (offline evaluation).
        
        Directly imports and calls the learner's move()/choose_move() function.
        Requires _load_learner_module() to have been called first.
        """
        if not hasattr(self, '_learner_move_func') or self._learner_move_func is None:
            return None
        
        try:
            result = self._learner_move_func(state)
            if isinstance(result, dict):
                return result.get("move", "")
            return str(result) if result else None
            
        except Exception as e:
            self.logger.debug(f"Error querying learner: {e}")
            return None

    def run_edit_phase(self, round_num: int) -> None:
        """
        Execute the edit phase where only the learner agent can edit.
        
        Steps:
        1. Copy previous round's logs (including traces) to learner's container
        2. Run learner agent (LLM edits code)
        3. Target agent does NOT edit (static)
        """
        # Copy logs from previous round to learner's container
        self.logger.info(f"Copying round {round_num - 1} logs to {self.learner_agent.name}'s container...")
        copy_to_container(
            self.learner_agent.environment,
            self.game.log_local / "rounds" / str(round_num - 1),
            DIR_LOGS / "rounds" / str(round_num - 1),
        )
        
        # Compress previous round's logs on local machine
        self._compress_round_folder(round_num - 1)

        # Run only the learner agent
        self.logger.info(f"Running learner agent: {self.learner_agent.name}")
        self.run_agent(self.learner_agent, round_num)
        
        # Target agent does NOT run - its code stays static
        self.logger.info(f"Target agent {self.target_agent.name} is static, skipping edit phase")

        self._save()
        self.logger.info("Edit phase completed.")

    def run_agent(self, agent: Player, round_num: int) -> None:
        """Run a single agent for the current round."""
        # Pass accuracy history so agent can see progress
        accuracy_history = self._metadata.get("accuracy_history", {})
        agent.pre_run_hook(new_round=round_num, accuracy_history=accuracy_history)
        agent.run()
        agent.post_run_hook(round=round_num)

    def _save(self) -> None:
        """Save metadata to disk."""
        self.local_output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(self.metadata_file, json.dumps(self.get_metadata(), indent=2))
        self.logger.debug(f"Metadata saved to {self.metadata_file}")
        if is_running_in_aws_batch():
            s3_log_sync(self.local_output_dir, logger=self.logger)

    def _compress_round_folder(self, round_num: int) -> None:
        """Compress a round's logs to save space."""
        import shutil
        import subprocess
        
        round_dir = self.game.log_local / "rounds" / str(round_num)
        if not round_dir.exists():
            return

        archive = self.game.log_local / "rounds" / f"round_{round_num}.tar.gz"
        cmd = [
            "tar",
            "-zcf",
            str(archive),
            "-C",
            str(round_dir.parent),
            str(round_num),
        ]
        self.logger.info(f"Compressing round {round_num} logs...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.logger.warning(f"Failed to compress round {round_num}: {result.stderr}")
            return
        
        shutil.rmtree(round_dir)
        self.logger.info(f"Round {round_num} logs compressed successfully")

    def end(self) -> None:
        """Save output files, clean up resources."""
        self._save()
        self.game.end(self.cleanup_on_end)
        self.cleanup_handlers()
