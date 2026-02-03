# Inverse Strategy (CodeClash Fork)

Recover game strategies from behavioral observations using LLMs.

> **Note:** This is a fork of [CodeClash](https://github.com/CodeClash-ai/CodeClash) with inverse strategy recovery capabilities.

## Quick Start

```bash
# Setup
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -e .

# Run (requires LLM API - see configs/inverse/examples/)
python main.py configs/inverse/test/gpt5_offline_eval.yaml
```

## How It Works

**Offline Evaluation Design (v2):**
- Target plays against opponent to generate traces
- Learner's code is evaluated **offline** with target's exact states
- Accuracy = "Given the same state, would learner make the same decision as target?"

```
Round 0: Target vs Opponent → Query learner offline → 35% accuracy
Round 1: LLM edits code → New games → Query learner → 100% accuracy 📈
Round 2: LLM refines code → New games → Query learner → 95% accuracy
```

**Key insight:** Learner never plays in simulation. We ask: `learner_code(target_state) == target_action`

## Project Structure

```
configs/inverse/
├── mini/default.yaml      # Agent prompt templates
├── examples/              # Example configs for different LLM providers
└── test/                  # Test configs

data/inverse/
├── targets/               # Sample target strategies for testing
│   └── greedy_food/       # Simple deterministic BattleSnake strategy
└── extracted_strategies/  # Strategies from codeclash_viewer (gitignored)

codeclash/
├── tournaments/           # Tournament orchestration (incl. inverse_strategy.py)
├── agents/                # LLM agent (mini-swe-agent based)
├── arenas/                # Game simulators
└── traces/                # Trace parsing
```

## Configuration

See `configs/inverse/examples/` for different LLM providers:
- `battlesnake_gpt5.yaml` - GPT-5 via local proxy
- `battlesnake_gpt4o.yaml` - GPT-4o via Portkey
- `battlesnake_o3.yaml` - o3 via Portkey
- `battlesnake_github_models.yaml` - GitHub Models (free with GITHUB_TOKEN)
- `battlesnake_ollama_qwen.yaml` - Local Ollama

**3-Player Config (Offline Evaluation):**
```yaml
tournament:
  rounds: 3              # Number of edit→simulate cycles

game:
  name: BattleSnake
  sims_per_round: 10     # Games per evaluation

players:
  # Learner: edits code, does NOT play in simulation
  - agent: inverse
    name: learner
    editable: true
    config:
      agent: !include inverse/mini/default.yaml
      model:
        model_name: openai/gpt-5

  # Target: strategy to recover, plays in simulation
  - agent: static
    name: target
    editable: false
    args:
      source_path: data/inverse/targets/greedy_food

  # Opponent: plays against target in simulation
  - agent: static
    name: opponent
    editable: false
    args:
      source_path: data/inverse/targets/greedy_food
```

## Adding Target Strategies

Create a directory under `data/inverse/targets/`:
```
data/inverse/targets/my_strategy/
├── main.py      # Strategy implementation (game-specific API)
└── README.md    # Document the rules
```

See `data/inverse/targets/greedy_food/` for an example.

## Logs

Experiments save to `logs/<experiment_id>/`:
```
logs/InverseStrategy.BattleSnake.r3.s10.p3.gpt-5.greedy_food.greedy_food.260203203611/
├── rounds/              # Per-round traces and accuracy
│   ├── 0/traces.json    # Accuracy + ALL mismatches with full state
│   ├── round_0.tar.gz
│   └── round_1.tar.gz
├── players/learner/     # Agent trajectories and code changes
│   ├── learner_r1.traj.json
│   └── changes_r1.json
└── metadata.json
```

**traces.json format:**
```json
{
  "accuracy": 0.95,
  "total_actions": 100,
  "matching_actions": 95,
  "mismatches": [
    {"turn": 5, "state": {...}, "learner_action": "up", "target_action": "down"}
  ]
}
```

## Supported Games

- **BattleSnake** - Multiplayer snake game
- **RobotRumble** - (experimental)

The architecture is game-agnostic. To add a new game:
1. Implement an Arena (runs simulations)
2. Implement a TraceParser with `extract_state_action_pairs()`
3. Create a game_description prompt

## Documentation

- [FLOWCHART_v2.md](docs/inverse/FLOWCHART_v2.md) - Detailed architecture diagram
- [configs/inverse/examples/](configs/inverse/examples/) - Ready-to-use configs

## Downloading Strategies from CodeClash

Use the scripts in `scripts/inverse/codeclash/` to download strategies:

```bash
# Download HTML artifacts
python scripts/inverse/codeclash/download.py --index path/to/index.html

# Extract strategies
python scripts/inverse/codeclash/extract.py
```

See [scripts/inverse/codeclash/README.md](scripts/inverse/codeclash/README.md) for details.
