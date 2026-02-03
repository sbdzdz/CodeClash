"""
Inverse Strategy Tournament.

A tournament where Agent A (learner) recovers Agent B's (target) strategy.

Design:
- Agent A (Learner): Can edit code (LLM agent or similar)
- Agent B (Target): Static code (strategy to be recovered)
- Simulation: Run game in Docker via Arena, outputs sim_X.jsonl traces
- Post-simulation: Parse traces, compute strategy recovery accuracy

Flow:
1. Round 0: Run simulation with starter code → baseline traces
2. Round N (N >= 1):
   a. Edit Phase: Only Agent A edits (sees traces from round N-1)
   b. Simulation Phase: Run game, Arena stores traces in sim_X.jsonl
   c. Post-simulation: Parse traces, compute accuracy, save traces.json

The agent receives:
- logs/rounds/N-1/sim_*.jsonl - Raw game traces
- logs/rounds/N-1/traces.json - Parsed summary with accuracy metrics
- logs/rounds/N-1/results.json - Round statistics (wins/losses)
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
    
    Agent A (learner) tries to recover Agent B (target) by:
    1. Observing traces from game simulations
    2. Writing/editing code to reproduce the behavior
    
    Evaluation is done separately using the traces module.
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
        
        # Initialize agents
        # Agent A: the learner (can edit)
        # Agent B: the target (static, no editing)
        self.agents: list[Player] = []
        player_configs = self.config["players"]
        
        if len(player_configs) != 2:
            raise ValueError("InverseStrategyTournament requires exactly 2 players")
        
        for agent_conf in player_configs:
            self.agents.append(self.get_agent(agent_conf, self.config["prompts"]))
        
        # Identify which agent is the learner (can edit) vs target (static)
        self.learner_agent: Player = self._get_learner_agent()
        self.target_agent: Player = self._get_target_agent()
        
        self.logger.info(f"Learner agent: {self.learner_agent.name}")
        self.logger.info(f"Target agent: {self.target_agent.name}")

    def _get_learner_agent(self) -> Player:
        """Get the agent that can edit (learner)."""
        for i, agent_conf in enumerate(self.config["players"]):
            if agent_conf.get("editable", True):  # Default: first agent is editable
                return self.agents[i]
        # Default to first agent if none explicitly marked
        return self.agents[0]
    
    def _get_target_agent(self) -> Player:
        """Get the target agent (static, to be recoverd)."""
        for agent in self.agents:
            if agent != self.learner_agent:
                return agent
        raise ValueError("Could not identify target agent")

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
            # Round 0: Initial simulation with starter code (no editing)
            self.run_simulation_phase(0)
            
            for round_num in range(1, self.rounds + 1):
                self.run_edit_phase(round_num)
                self.run_simulation_phase(round_num)
            
            # Compress the last round
            self._compress_round_folder(self.rounds)
        finally:
            self.end()

    def run_simulation_phase(self, round_num: int) -> None:
        """
        Run game simulations and process traces.
        
        Steps:
        1. Run game via Arena → produces sim_X.jsonl files
        2. Parse traces using game-specific parser
        3. Compute strategy recovery accuracy (learner vs target)
        4. Save traces.json summary for agent to read
        """
        # Run the game round
        stats = self.game.run_round(self.agents, round_num)
        self.logger.info(stats)

        # Store basic stats
        self._metadata.setdefault("round_stats", {})[round_num] = stats.to_dict()

        # Create directory for round logs
        round_dir = self.game.log_local / "rounds" / str(round_num)
        round_dir.mkdir(parents=True, exist_ok=True)

        # Write results
        results_file = round_dir / FILE_RESULTS
        results_file.write_text(json.dumps(stats.to_dict(), indent=2))

        # POST-SIMULATION: Parse traces and compute accuracy
        trace_summary = self._process_traces(round_dir, round_num)
        
        # Store accuracy in metadata
        if trace_summary:
            self._metadata.setdefault("accuracy_history", {})[round_num] = trace_summary.get("accuracy", 0.0)
            self.logger.info(f"Round {round_num} strategy recovery accuracy: {trace_summary.get('accuracy', 0.0):.2%}")

        self._save()

    def _process_traces(self, round_dir: Path, round_num: int) -> dict[str, Any] | None:
        """
        Parse trace files and compute strategy recovery accuracy.
        
        Returns a summary dict that gets saved to traces.json:
        {
            "round": N,
            "total_actions": 1000,        # Total actions across all sims
            "matching_actions": 750,      # Actions matching target
            "accuracy": 0.75,             # Pooled accuracy (weighted by game length)
            "mean_accuracy": 0.72,        # Mean per-sim accuracy (normalized)
            "accuracy_std": 0.08,         # Std dev of per-sim accuracies
            "accuracy_se": 0.025,         # Standard error (std / sqrt(n_sims))
            "learner": "agent_a",
            "target": "agent_b",
            "per_simulation": [...],      # Per-sim breakdown
            "sample_mismatches": [...]    # Examples for debugging
        }
        """
        from codeclash.traces import get_parser
        
        # Find all sim files
        sim_files = sorted(round_dir.glob("sim_*.jsonl")) + sorted(round_dir.glob("sim_*.json"))
        if not sim_files:
            self.logger.warning(f"No simulation files found in {round_dir}")
            return None
        
        # Get the appropriate parser for this game
        game_name = self.game.name
        try:
            parser_class = get_parser(game_name)
        except ValueError as e:
            self.logger.warning(f"No parser for game {game_name}: {e}")
            return None
        
        # Import the action comparison function
        if game_name == "BattleSnake":
            from codeclash.traces.parsers.battlesnake import actions_equal
        elif game_name == "RobotRumble":
            from codeclash.traces.parsers.robotrumble import actions_equal
        else:
            self.logger.warning(f"No action comparison for game {game_name}")
            return None
        
        total_actions = 0
        matching_actions = 0
        per_simulation = []
        sample_mismatches = []
        
        learner_name = self.learner_agent.name
        target_name = self.target_agent.name
        
        for sim_file in sim_files:
            try:
                parser = parser_class()
                trace = parser.parse_file(sim_file)
                
                sim_total = 0
                sim_matching = 0
                
                # Iterate through turns and compare actions
                for turn in trace.turns:
                    # Find actions for both players in this turn
                    learner_action = None
                    target_action = None
                    
                    for player_action in turn.actions:
                        if player_action.player_name == learner_name:
                            learner_action = player_action.action
                        if player_action.player_name == target_name:
                            target_action = player_action.action
                    
                    # Only compare if both players acted
                    if learner_action is not None and target_action is not None:
                        sim_total += 1
                        if actions_equal(learner_action, target_action):
                            sim_matching += 1
                        elif len(sample_mismatches) < 10:  # Keep some examples
                            sample_mismatches.append({
                                "sim": sim_file.name,
                                "turn": turn.turn,
                                "learner_action": learner_action,
                                "target_action": target_action,
                            })
                
                total_actions += sim_total
                matching_actions += sim_matching
                
                per_simulation.append({
                    "file": sim_file.name,
                    "total": sim_total,
                    "matching": sim_matching,
                    "accuracy": sim_matching / sim_total if sim_total > 0 else 0.0,
                })
                
            except Exception as e:
                self.logger.warning(f"Error parsing {sim_file}: {e}")
                continue
        
        # Pooled accuracy (current metric - weighted by game length)
        accuracy = matching_actions / total_actions if total_actions > 0 else 0.0
        
        # Mean accuracy per sim (normalized - equal weight per game)
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
            # Pooled accuracy (weighted by game length)
            "total_actions": total_actions,
            "matching_actions": matching_actions,
            "accuracy": accuracy,
            # Normalized accuracy (equal weight per sim)
            "mean_accuracy": mean_accuracy,
            "accuracy_std": accuracy_std,
            "accuracy_se": accuracy_se,
            "num_simulations": len(per_simulation),
            "per_simulation": per_simulation,
            "sample_mismatches": sample_mismatches,
        }
        
        # Save traces.json
        traces_file = round_dir / "traces.json"
        traces_file.write_text(json.dumps(summary, indent=2))
        self.logger.info(f"Saved trace summary to {traces_file}")
        
        return summary

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
