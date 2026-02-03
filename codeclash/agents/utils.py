from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Template
from pydantic import BaseModel

load_dotenv()


class GameContext(BaseModel):
    """
    A class that gives agent access to a partial view of the game state.

    NOTE: Instead of passing `game` directly as a reference to the agent,
    we create this interface instead to make the communication of game state
    more explicit and controlled. We go with this loose coupling to avoid
    making the agent too dependent on the entire game object.
    """

    id: str
    log_env: Path
    log_local: Path
    name: str
    player_id: str
    prompts: dict
    round: int
    rounds: int
    working_dir: str
    accuracy_history: dict[int, float] = {}  # round -> accuracy

    def _render_prompt_templates(self) -> dict:
        context = self.model_dump()
        return {key: Template(template_str).render(**context) for key, template_str in self.prompts.items()}

    def _format_accuracy_progress(self) -> str:
        """Format accuracy history as a readable progress string with deltas."""
        if not self.accuracy_history:
            return "No accuracy data yet (this is round 0 or 1)."
        
        lines = []
        sorted_rounds = sorted(self.accuracy_history.keys())
        
        for i, r in enumerate(sorted_rounds):
            acc = self.accuracy_history[r]
            if i == 0:
                lines.append(f"Round {r}: {acc:.1%}")
            else:
                prev_r = sorted_rounds[i - 1]
                prev_acc = self.accuracy_history[prev_r]
                delta = acc - prev_acc
                if delta > 0.01:
                    symbol = "📈 IMPROVED"
                elif delta < -0.01:
                    symbol = "📉 DROPPED"
                else:
                    symbol = "➡️ unchanged"
                lines.append(f"Round {r}: {acc:.1%} ({delta:+.1%} from Round {prev_r}) {symbol}")
        
        return "\n".join(lines)

    def to_template_vars(self) -> dict[str, str]:
        """Convert the GameContext to a dictionary for rendering prompts in the agent"""
        out = self.model_dump() | self._render_prompt_templates()
        out.pop("prompts")
        out["accuracy_progress"] = self._format_accuracy_progress()
        return out
