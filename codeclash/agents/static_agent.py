"""Static agent that uses pre-existing code from extracted strategies."""
import json
import os
from pathlib import Path
from codeclash.agents.player import Player
from minisweagent.environments.docker import DockerEnvironment
from codeclash.game_context import GameContext


# Map game types to their file extension and destination in Docker container
GAME_FILE_CONFIG = {
    "BattleSnake": {"ext": ".py", "dest": "/workspace/main.py"},
    "CoreWar": {"ext": ".red", "dest": "/workspace/warrior.red"},
    "Halite": {"ext": ".c", "dest": "/workspace/submission/main.c"},
    "HuskyBench": {"ext": ".py", "dest": "/workspace/client/player.py"},
    "RoboCode": {"ext": ".java", "dest": "/workspace/robots/custom/"},  # Special: copy all .java files
    "RobotRumble": {"ext": ".js", "dest": "/workspace/robot.js"},
}


class Static(Player):
    """A player that uses pre-written code instead of generating it.
    
    Copies the pre-written code during initialization so it's ready for round 0.
    """
    
    def __init__(
        self,
        config: dict,
        environment: DockerEnvironment,
        game_context: GameContext,
    ) -> None:
        super().__init__(config, environment, game_context)
        
        # Copy code immediately during init so it's ready for round 0
        self._copy_strategy_code()
    
    def _copy_strategy_code(self):
        """Copy the pre-written code to the container."""
        agent_args = self.config.get("args", {})
        source_path = agent_args.get("source_path")
        
        if not source_path:
            self.logger.error("No source_path provided for static agent")
            return
        
        source = Path(source_path)
        if not source.exists():
            self.logger.error(f"Source path does not exist: {source}")
            return
        
        # Determine game type from game_context
        game_name = self.game_context.name
        file_config = GAME_FILE_CONFIG.get(game_name, GAME_FILE_CONFIG["BattleSnake"])
        
        # Expected submission filename (e.g., "main.py" for BattleSnake)
        expected_name = Path(file_config["dest"]).name
        
        # Read info.json to find the latest file
        info_file = source / "info.json"
        latest_file = None
        latest_round = -1
        submission_file = None
        submission_round = -1
        
        if info_file.exists():
            with open(info_file) as f:
                info = json.load(f)
            files = info.get("files", {})
            
            # Find files matching the extension
            for fname, round_num in files.items():
                matches_ext = fname.endswith(file_config["ext"])
                
                if not matches_ext:
                    continue
                
                # Priority 1: exact match on submission name (e.g., main.py)
                if fname == expected_name and round_num > submission_round:
                    submission_round = round_num
                    submission_file = fname
                
                # Track highest round for any matching extension as fallback
                if round_num > latest_round:
                    latest_round = round_num
                    latest_file = fname
            
            # Prefer submission file if found, otherwise use highest round file
            if submission_file:
                latest_file = submission_file
                latest_round = submission_round
                self.logger.info(f"Using {latest_file} (submission file) from round {latest_round} for {game_name}")
            elif latest_file:
                self.logger.info(f"Using {latest_file} from round {latest_round} for {game_name}")
        
        # Fallback: find any file matching the extension
        if not latest_file:
            for f in source.iterdir():
                if f.suffix == file_config["ext"]:
                    latest_file = f.name
                    self.logger.info(f"Fallback: using {latest_file} for {game_name}")
                    break
        
        if not latest_file:
            self.logger.error(f"No suitable file found in {source} for {game_name}")
            return
        
        # Handle special case for RoboCode (copy all .java files)
        if game_name == "RoboCode":
            self._copy_robocode_files(source)
            return
        
        # Copy to container
        src_file = source / latest_file
        if src_file.exists():
            code = src_file.read_text()
            dest = file_config["dest"]
            
            # Ensure parent directory exists
            parent_dir = os.path.dirname(dest)
            if parent_dir and parent_dir != "/workspace":
                self.environment.execute(f"mkdir -p {parent_dir}")
            
            # Write file using heredoc
            self.environment.execute(f"cat > {dest} << 'STATICEOF'\n{code}\nSTATICEOF")
            self.logger.info(f"Copied {latest_file} to container {dest}")
        else:
            self.logger.error(f"File not found: {src_file}")

    def _copy_robocode_files(self, source: Path):
        """Copy all .java files for RoboCode."""
        self.environment.execute("mkdir -p /workspace/robots/custom")
        
        for java_file in source.glob("*.java"):
            code = java_file.read_text()
            dest = f"/workspace/robots/custom/{java_file.name}"
            self.environment.execute(f"cat > {dest} << 'STATICEOF'\n{code}\nSTATICEOF")
            self.logger.info(f"Copied {java_file.name} to container {dest}")

    def run(self):
        """No-op since code was already copied during init."""
        pass
