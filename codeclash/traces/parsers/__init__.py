"""
Game-specific trace parsers.

Each game has its own output format from the game engine.
These parsers convert native formats to our unified GameTrace format.

Also provides game-specific utility functions for action/state handling:
- normalize_action(): Convert to canonical format
- actions_equal(): Compare two actions
- compute_state_distance(): Compute metric distance between states
"""

from codeclash.traces.parsers.battlesnake import (
    BattleSnakeTraceParser,
    parse_battlesnake_trace,
    # Action/state utilities
    normalize_action as battlesnake_normalize_action,
    actions_equal as battlesnake_actions_equal,
    compute_state_distance as battlesnake_state_distance,
    VALID_ACTIONS as BATTLESNAKE_VALID_ACTIONS,
)
from codeclash.traces.parsers.robotrumble import (
    RobotRumbleTraceParser,
    parse_robotrumble_trace,
    # Action/state utilities
    normalize_action as robotrumble_normalize_action,
    actions_equal as robotrumble_actions_equal,
    compute_state_distance as robotrumble_state_distance,
    VALID_DIRECTIONS as ROBOTRUMBLE_VALID_DIRECTIONS,
    VALID_ACTION_TYPES as ROBOTRUMBLE_VALID_ACTION_TYPES,
    TEAMS as ROBOTRUMBLE_TEAMS,
)

__all__ = [
    # BattleSnake
    "BattleSnakeTraceParser",
    "parse_battlesnake_trace",
    "battlesnake_normalize_action",
    "battlesnake_actions_equal",
    "battlesnake_state_distance",
    "BATTLESNAKE_VALID_ACTIONS",
    # RobotRumble
    "RobotRumbleTraceParser",
    "parse_robotrumble_trace",
    "robotrumble_normalize_action",
    "robotrumble_actions_equal",
    "robotrumble_state_distance",
    "ROBOTRUMBLE_VALID_DIRECTIONS",
    "ROBOTRUMBLE_VALID_ACTION_TYPES",
    "ROBOTRUMBLE_TEAMS",
    # Registry
    "TRACE_PARSERS",
    "get_parser",
]


# Registry of parsers by game type
TRACE_PARSERS = {
    "BattleSnake": BattleSnakeTraceParser,
    "RobotRumble": RobotRumbleTraceParser,
}


def get_parser(game_type: str):
    """Get the trace parser for a game type."""
    if game_type not in TRACE_PARSERS:
        raise ValueError(f"No trace parser for game type: {game_type}")
    return TRACE_PARSERS[game_type]
