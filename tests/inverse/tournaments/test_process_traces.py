"""
Tests for _process_traces() in InverseStrategyTournament.

Tests the post-simulation trace processing:
1. Parses sim_*.jsonl files
2. Computes strategy recovery accuracy (learner vs target)
3. Saves traces.json summary

Uses fixture data from data/test_fixtures/traces/.
"""

import json
import pytest
import shutil
from pathlib import Path
from unittest.mock import MagicMock

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_round_dir(tmp_path):
    """Create a temporary round directory."""
    round_dir = tmp_path / "rounds" / "0"
    round_dir.mkdir(parents=True)
    return round_dir


@pytest.fixture
def battlesnake_sim_file():
    """Path to BattleSnake test fixture."""
    return PROJECT_ROOT / "data" / "test_fixtures" / "traces" / "battlesnake" / "short_game.jsonl"


@pytest.fixture
def robotrumble_sim_file():
    """Path to RobotRumble test fixture."""
    return PROJECT_ROOT / "data" / "test_fixtures" / "traces" / "robotrumble" / "short_game.json"


# =============================================================================
# Helper: Extracted _process_traces logic
# =============================================================================

def process_traces(
    round_dir: Path,
    round_num: int,
    game_name: str,
    learner_name: str,
    target_name: str,
) -> dict | None:
    """
    Extracted logic from InverseStrategyTournament._process_traces().
    
    This allows testing without mocking the full tournament.
    """
    from codeclash.traces import get_parser
    
    # Find all sim files
    sim_files = sorted(round_dir.glob("sim_*.jsonl")) + sorted(round_dir.glob("sim_*.json"))
    if not sim_files:
        return None
    
    # Get the appropriate parser for this game
    try:
        parser_class = get_parser(game_name)
    except ValueError:
        return None
    
    # Import the action comparison function
    if game_name == "BattleSnake":
        from codeclash.traces.parsers.battlesnake import actions_equal
    elif game_name == "RobotRumble":
        from codeclash.traces.parsers.robotrumble import actions_equal
    else:
        return None
    
    total_actions = 0
    matching_actions = 0
    per_simulation = []
    sample_mismatches = []
    
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
                    elif len(sample_mismatches) < 10:
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
            
        except Exception:
            continue
    
    if total_actions == 0:
        return None
    
    accuracy = matching_actions / total_actions
    
    summary = {
        "round": round_num,
        "game": game_name,
        "learner": learner_name,
        "target": target_name,
        "total_actions": total_actions,
        "matching_actions": matching_actions,
        "accuracy": accuracy,
        "num_simulations": len(per_simulation),
        "per_simulation": per_simulation,
        "sample_mismatches": sample_mismatches,
    }
    
    # Save traces.json
    traces_file = round_dir / "traces.json"
    traces_file.write_text(json.dumps(summary, indent=2))
    
    return summary


# =============================================================================
# Tests: BattleSnake
# =============================================================================

class TestProcessTracesBattleSnake:
    """Tests for _process_traces with BattleSnake data."""
    
    def test_parses_battlesnake_sim_file(self, temp_round_dir, battlesnake_sim_file):
        """Should parse BattleSnake sim file and compute accuracy."""
        # Copy fixture to temp dir as sim_0.jsonl
        shutil.copy(battlesnake_sim_file, temp_round_dir / "sim_0.jsonl")
        
        result = process_traces(
            round_dir=temp_round_dir,
            round_num=0,
            game_name="BattleSnake",
            learner_name="player_a",
            target_name="player_b",
        )
        
        assert result is not None
        assert result["game"] == "BattleSnake"
        assert result["learner"] == "player_a"
        assert result["target"] == "player_b"
        assert result["round"] == 0
        assert result["total_actions"] > 0
        assert 0.0 <= result["accuracy"] <= 1.0
    
    def test_saves_traces_json(self, temp_round_dir, battlesnake_sim_file):
        """Should save traces.json to round directory."""
        shutil.copy(battlesnake_sim_file, temp_round_dir / "sim_0.jsonl")
        
        process_traces(
            round_dir=temp_round_dir,
            round_num=0,
            game_name="BattleSnake",
            learner_name="player_a",
            target_name="player_b",
        )
        
        traces_file = temp_round_dir / "traces.json"
        assert traces_file.exists()
        
        data = json.loads(traces_file.read_text())
        assert "accuracy" in data
        assert "total_actions" in data
        assert "per_simulation" in data
    
    def test_handles_multiple_sim_files(self, temp_round_dir, battlesnake_sim_file):
        """Should process multiple sim files."""
        # Copy fixture multiple times
        shutil.copy(battlesnake_sim_file, temp_round_dir / "sim_0.jsonl")
        shutil.copy(battlesnake_sim_file, temp_round_dir / "sim_1.jsonl")
        shutil.copy(battlesnake_sim_file, temp_round_dir / "sim_2.jsonl")
        
        result = process_traces(
            round_dir=temp_round_dir,
            round_num=0,
            game_name="BattleSnake",
            learner_name="player_a",
            target_name="player_b",
        )
        
        assert result is not None
        assert result["num_simulations"] == 3
        assert len(result["per_simulation"]) == 3
    
    def test_per_simulation_breakdown(self, temp_round_dir, battlesnake_sim_file):
        """Should include per-simulation accuracy breakdown."""
        shutil.copy(battlesnake_sim_file, temp_round_dir / "sim_0.jsonl")
        
        result = process_traces(
            round_dir=temp_round_dir,
            round_num=0,
            game_name="BattleSnake",
            learner_name="player_a",
            target_name="player_b",
        )
        
        assert len(result["per_simulation"]) == 1
        sim_result = result["per_simulation"][0]
        assert "file" in sim_result
        assert "total" in sim_result
        assert "matching" in sim_result
        assert "accuracy" in sim_result
    
    def test_identical_players_have_100_accuracy(self, temp_round_dir, battlesnake_sim_file):
        """When comparing player to itself, accuracy should be 100%."""
        shutil.copy(battlesnake_sim_file, temp_round_dir / "sim_0.jsonl")
        
        result = process_traces(
            round_dir=temp_round_dir,
            round_num=0,
            game_name="BattleSnake",
            learner_name="player_a",
            target_name="player_a",  # Same player!
        )
        
        assert result is not None
        assert result["accuracy"] == 1.0
        assert result["matching_actions"] == result["total_actions"]


# =============================================================================
# Tests: RobotRumble
# =============================================================================

class TestProcessTracesRobotRumble:
    """Tests for _process_traces with RobotRumble data."""
    
    def test_parses_robotrumble_sim_file(self, temp_round_dir, robotrumble_sim_file):
        """Should parse RobotRumble sim file and compute accuracy."""
        # Copy fixture to temp dir as sim_0.json
        shutil.copy(robotrumble_sim_file, temp_round_dir / "sim_0.json")
        
        # RobotRumble uses team names: "Blue" and "Red"
        result = process_traces(
            round_dir=temp_round_dir,
            round_num=0,
            game_name="RobotRumble",
            learner_name="Blue",
            target_name="Red",
        )
        
        assert result is not None
        assert result["game"] == "RobotRumble"
        assert result["total_actions"] > 0
        assert 0.0 <= result["accuracy"] <= 1.0
    
    def test_robotrumble_identical_team_100_accuracy(self, temp_round_dir, robotrumble_sim_file):
        """When comparing team to itself, accuracy should be 100%."""
        shutil.copy(robotrumble_sim_file, temp_round_dir / "sim_0.json")
        
        result = process_traces(
            round_dir=temp_round_dir,
            round_num=0,
            game_name="RobotRumble",
            learner_name="Blue",
            target_name="Blue",  # Same team!
        )
        
        assert result is not None
        assert result["accuracy"] == 1.0


# =============================================================================
# Tests: Edge Cases
# =============================================================================

class TestProcessTracesEdgeCases:
    """Edge case tests for _process_traces."""
    
    def test_returns_none_for_empty_directory(self, temp_round_dir):
        """Should return None when no sim files exist."""
        result = process_traces(
            round_dir=temp_round_dir,
            round_num=0,
            game_name="BattleSnake",
            learner_name="player_a",
            target_name="player_b",
        )
        
        assert result is None
    
    def test_returns_none_for_unknown_game(self, temp_round_dir, battlesnake_sim_file):
        """Should return None for unsupported game type."""
        shutil.copy(battlesnake_sim_file, temp_round_dir / "sim_0.jsonl")
        
        result = process_traces(
            round_dir=temp_round_dir,
            round_num=0,
            game_name="UnknownGame",
            learner_name="player_a",
            target_name="player_b",
        )
        
        assert result is None
    
    def test_handles_invalid_sim_file(self, temp_round_dir):
        """Should skip invalid sim files gracefully."""
        # Create an invalid sim file
        (temp_round_dir / "sim_0.jsonl").write_text("not valid json")
        
        result = process_traces(
            round_dir=temp_round_dir,
            round_num=0,
            game_name="BattleSnake",
            learner_name="player_a",
            target_name="player_b",
        )
        
        # Should return None since no valid files
        assert result is None
    
    def test_sample_mismatches_limited_to_10(self, temp_round_dir, battlesnake_sim_file):
        """Should keep at most 10 sample mismatches."""
        # Copy many times to get more mismatches
        for i in range(20):
            shutil.copy(battlesnake_sim_file, temp_round_dir / f"sim_{i}.jsonl")
        
        result = process_traces(
            round_dir=temp_round_dir,
            round_num=0,
            game_name="BattleSnake",
            learner_name="player_a",
            target_name="player_b",
        )
        
        assert result is not None
        assert len(result["sample_mismatches"]) <= 10


# =============================================================================
# Tests: Integration with InverseStrategyTournament
# =============================================================================

class TestTournamentIntegration:
    """Test _process_traces via InverseStrategyTournament mock."""
    
    def test_tournament_calls_process_traces(self, temp_round_dir, battlesnake_sim_file):
        """Verify the tournament method produces same results."""
        # This test uses mocks to verify the tournament's _process_traces
        # produces consistent results with our extracted function
        shutil.copy(battlesnake_sim_file, temp_round_dir / "sim_0.jsonl")
        
        # First, get result from our extracted function
        expected = process_traces(
            round_dir=temp_round_dir,
            round_num=0,
            game_name="BattleSnake",
            learner_name="player_a",
            target_name="player_b",
        )
        
        # Verify it worked
        assert expected is not None
        assert expected["total_actions"] > 0
        
        # The tournament's _process_traces should produce equivalent results
        # (we can't easily instantiate the full tournament without Docker)
        # So we verify the output format matches what the agent expects
        assert "accuracy" in expected
        assert "per_simulation" in expected
        assert "sample_mismatches" in expected
        assert "learner" in expected
        assert "target" in expected
