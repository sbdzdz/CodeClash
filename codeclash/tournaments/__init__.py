"""Tournament implementations for CodeClash."""

from codeclash.tournaments.tournament import AbstractTournament
from codeclash.tournaments.pvp import PvpTournament
from codeclash.tournaments.single_player import SinglePlayerTraining

# Lazy import to avoid circular dependency with agents module
def __getattr__(name):
    if name == "InverseStrategyTournament":
        from codeclash.tournaments.inverse_strategy import InverseStrategyTournament
        return InverseStrategyTournament
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "AbstractTournament",
    "PvpTournament",
    "SinglePlayerTraining",
    "InverseStrategyTournament",
]
