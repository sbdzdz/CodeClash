from codeclash.agents.dummy_agent import Dummy
from codeclash.agents.minisweagent import MiniSWEAgent, InverseStrategyAgent
from codeclash.agents.player import Player
from codeclash.agents.static_agent import Static
from codeclash.agents.utils import GameContext
from codeclash.utils.environment import ContainerEnvironment


def get_agent(config: dict, game_context: GameContext, environment: ContainerEnvironment) -> Player:
    agents = {
        "dummy": Dummy,
        "mini": MiniSWEAgent,
        "static": Static,
        "inverse": InverseStrategyAgent,
    }.get(config["agent"])
    if agents is None:
        raise ValueError(f"Unknown agent type: {config['agent']}")
    return agents(config, environment, game_context)

