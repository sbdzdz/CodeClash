"""
Mini-SWE-Agent integration for inverse_strategy.

This module provides LLM-powered agents that can edit code in Docker environments.
Based on CodeClash's minisweagent.py with adaptations for inverse strategy tasks.
"""

import logging
import os
import traceback
from collections.abc import Callable

from minisweagent import Model
from minisweagent.agents.default import AgentConfig, DefaultAgent
from minisweagent.models import get_model
from minisweagent.models.test_models import DeterministicModel
from minisweagent.run.utils.save import save_traj

from codeclash import REPO_DIR
from codeclash.agents.player import Player
from codeclash.agents.utils import GameContext
from codeclash.utils.environment import ContainerEnvironment, copy_to_container

os.environ["MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT"] = "90"
os.environ["LITELLM_MODEL_REGISTRY_PATH"] = str(
    (REPO_DIR / "configs" / "mini" / "litellm_custom_model_config.yaml").resolve()
)


class ClashAgent(DefaultAgent):
    """
    Slightly modified version of `DefaultAgent` from mini-SWE-agent
    (https://github.com/SWE-agent/mini-swe-agent)
    """

    def __init__(
        self,
        model: Model,
        env: ContainerEnvironment,
        *,
        logger: logging.Logger,
        config_class: Callable = AgentConfig,
        **kwargs,
    ):
        super().__init__(model, env, config_class=config_class, **kwargs)
        self.logger = logger

    def add_message(self, role: str, content: str, **kwargs):
        super().add_message(role, content, **kwargs)
        self.logger.debug(f"[{role}] {content}", extra={"highlighter": None})


class MiniSWEAgent(Player):
    """Player with agentic code editing capabilities using mini-swe-agent."""

    def __init__(self, config: dict, environment: ContainerEnvironment, game_context: GameContext):
        super().__init__(config, environment=environment, game_context=game_context)

    def run(self):
        # temporary workaround around https://github.com/SWE-agent/mini-swe-agent/issues/477
        if "DeterministicModel" not in self.config["config"]["model"].get("model_class", ""):
            model = get_model(config=self.config["config"]["model"])
        else:
            model = DeterministicModel(outputs=self.config["config"]["model"]["outputs"])
        self.agent = ClashAgent(
            model=model,
            env=self.environment,
            logger=self.logger,
            **self.config["config"]["agent"],
        )
        exit_status = None
        result = None
        exc_message = None
        try:
            exit_status, result = self.agent.run(task="", **self.game_context.to_template_vars())
        except Exception as e:
            exit_status = str(e)
            exc_message = traceback.format_exc()
            result = exc_message
            self.logger.critical(exc_message)
        finally:
            traj_path = (
                self.game_context.log_local
                / "players"
                / self.name
                / f"{self.name}_r{self.game_context.round}.traj.json"
            )
            save_traj(
                self.agent,  # type: ignore
                traj_path,
                exit_status=exit_status,
                result=result,
                print_fct=self.logger.debug,
            )
            copy_to_container(
                self.environment,
                traj_path,
                self.game_context.log_env / "edits" / traj_path.name,
            )
            self._metadata["agent_stats"][self.game_context.round] = {
                "exit_status": exit_status,
                "cost": self.agent.model.cost,
                "api_calls": self.agent.model.n_calls,
            }
        if exit_status.lower().strip() not in ["", "submitted", "limitsexceeded"] and exc_message is not None:
            raise RuntimeError(f"Agent {self.name} failed with exit status: {exit_status} and exception: {exc_message}")


class InverseStrategyAgent(MiniSWEAgent):
    """
    Agent for inverse strategy extraction.
    
    Extends MiniSWEAgent to handle the inverse strategy task:
    - Receives game traces (state-action pairs) as context
    - Analyzes traces to understand the strategy
    - Writes code that reproduces the observed behavior
    
    The key difference from regular CodeClash:
    - CodeClash: Agent competes by writing better code each round
    - InverseStrategy: Agent analyzes traces and writes code that matches observed behavior
    
    Additional context passed via game_context.prompts:
    - traces_summary: Summary of available traces
    - evaluation_results: Results from previous round's code evaluation
    """

    def __init__(self, config: dict, environment: DockerEnvironment, game_context: GameContext):
        super().__init__(config, environment=environment, game_context=game_context)
        # Track inverse strategy specific metadata
        self._metadata["inverse_strategy"] = {
            "traces_provided": False,
            "evaluation_history": [],
        }

    def run(self):
        """
        Run the inverse strategy agent.
        
        Before calling the base run(), we can prepare additional context
        specific to inverse strategy (e.g., copy trace files to container).
        """
        # Mark that we're running inverse strategy
        self._metadata["inverse_strategy"]["traces_provided"] = True
        
        # Call the base MiniSWEAgent run
        super().run()
        
        # After run, record evaluation results if available
        if hasattr(self, 'agent') and hasattr(self.agent, 'model'):
            self._metadata["inverse_strategy"]["evaluation_history"].append({
                "round": self.game_context.round,
                "cost": self.agent.model.cost,
                "api_calls": self.agent.model.n_calls,
            })
