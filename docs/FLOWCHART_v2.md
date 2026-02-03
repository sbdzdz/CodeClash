# Inverse Strategy Tournament - Flow Chart v2

## Design Overview (Offline Evaluation)

The key change in v2 is **offline evaluation**: the learner does NOT play in the simulation.
Instead, target and opponent play, and the learner's code is queried offline with target's states.

```
OLD (v1): learner vs target → compare actions at DIFFERENT states (flawed!)
NEW (v2): target vs opponent → query learner with target's states → compare at SAME state
```

**Accuracy Formula:** `learner_code(target_state) == target_action`

---

## Main Tournament Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TOURNAMENT START                                     │
│                                                                             │
│  Config: 3 players                                                          │
│    - learner (editable, does NOT play in simulation)                        │
│    - target (static, plays in simulation)                                   │
│    - opponent (static, plays against target)                                │
│                                                                             │
│  Creates: Game Container + Learner Container                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ROUND 0: BASELINE                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SIMULATION: TARGET vs OPPONENT                    │   │
│  │                                                                      │   │
│  │  1. Target and Opponent play N games                                 │   │
│  │  2. Record all (state, action) pairs for TARGET                      │   │
│  │  3. Write sim_0.jsonl, sim_1.jsonl... to /logs/                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    OFFLINE EVALUATION                                │   │
│  │                                                                      │   │
│  │  1. Load learner's code module (importlib)                           │   │
│  │  2. Extract (state, action) pairs from traces                        │   │
│  │  3. For each target state:                                           │   │
│  │     learner_action = learner_module.move(target_state)               │   │
│  │     Compare: learner_action == target_action                         │   │
│  │  4. Compute accuracy, collect ALL mismatches with full state         │   │
│  │  5. Save traces.json (accuracy + mismatches array)                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
          ┌─────────────────────────────────────────────────────┐
          │              FOR round_num IN 1..N                   │
          └─────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EDIT PHASE (Round N)                                 │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      LEARNER CONTAINER                                │  │
│  │                                                                       │  │
│  │  1. Copy logs/rounds/N-1/ → /logs/rounds/N-1/                         │  │
│  │     (includes traces.json with accuracy + mismatches)                 │  │
│  │                                                                       │  │
│  │  2. pre_run_hook()                                                    │  │
│  │     - git tag round N-1                                               │  │
│  │                                                                       │  │
│  │  3. run() ← LLM AGENT                                                 │  │
│  │     - Reads traces.json (accuracy, mismatches with full states)       │  │
│  │     - Analyzes: "when target saw X, it did Y, but I did Z"            │  │
│  │     - Identifies patterns in target's decision-making                 │  │
│  │     - Edits main.py in /workspace to match target                     │  │
│  │                                                                       │  │
│  │  4. post_run_hook()                                                   │  │
│  │     - git commit changes                                              │  │
│  │     - git tag round N                                                 │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SIMULATION PHASE (Round N)                             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              GAME CONTAINER: TARGET vs OPPONENT                      │   │
│  │              (Learner does NOT play!)                                │   │
│  │                                                                      │   │
│  │  1. Copy target code → Game /target/                                 │   │
│  │     Copy opponent code → Game /opponent/                             │   │
│  │                                                                      │   │
│  │  2. Run N simulations (target vs opponent)                           │   │
│  │     Write sim_*.jsonl with target's (state, action) pairs            │   │
│  │                                                                      │   │
│  │  3. Copy Game /logs/ → local logs/rounds/N/                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              OFFLINE EVALUATION (Local)                              │   │
│  │                                                                      │   │
│  │  1. _setup_learner_for_eval():                                       │   │
│  │     Copy learner's code from container                               │   │
│  │     Load module via importlib.util.spec_from_file_location()         │   │
│  │                                                                      │   │
│  │  2. extract_state_action_pairs(sim_file, "target"):                  │   │
│  │     Parse traces to get [(turn, state, target_action), ...]          │   │
│  │                                                                      │   │
│  │  3. For each (turn, state, target_action):                           │   │
│  │     learner_action = _query_learner(learner_module, state)           │   │
│  │     if learner_action != target_action:                              │   │
│  │       mismatches.append({turn, state, learner_action, target_action})│   │
│  │                                                                      │   │
│  │  4. accuracy = matching_actions / total_actions                      │   │
│  │                                                                      │   │
│  │  5. Save traces.json:                                                │   │
│  │     {accuracy, total_actions, matching_actions, mismatches: [...]}   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │     More rounds?              │
                    │                               │
                    │   YES ──────► Loop back       │
                    │   NO  ──────► End             │
                    └───────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TOURNAMENT END                                       │
│                                                                             │
│  1. Compress final round logs                                               │
│  2. Save metadata.json (includes accuracy_history)                          │
│  3. Cleanup containers                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Container Architecture (v2)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           LEARNER CONTAINER                                 │
│                           (edits code, does NOT play)                       │
│                                                                             │
│  /workspace/                                                                │
│    main.py  ← LLM edits this to match target                                │
│    docs/    ← game documentation                                            │
│                                                                             │
│  /logs/rounds/N-1/                                                          │
│    traces.json   ← accuracy + ALL mismatches with full state                │
│    sim_*.jsonl   ← raw traces (target's states and actions)                 │
└────────────────────────────────────────────────────────────────────────────┘


┌────────────────────────────────────────────────────────────────────────────┐
│                           GAME CONTAINER                                    │
│                           (runs target vs opponent)                         │
│                                                                             │
│  /target/                                                                   │
│    main.py  ← target strategy (static)                                      │
│                                                                             │
│  /opponent/                                                                 │
│    main.py  ← opponent strategy (static)                                    │
│                                                                             │
│  /logs/                                                                     │
│    sim_0.jsonl, sim_1.jsonl, ...  ← game traces                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Offline Evaluation Flow (Key Innovation)

```
                    ┌─────────────────────────────────┐
                    │   SIMULATION                    │
                    │   target vs opponent            │
                    │   (learner NOT involved)        │
                    └─────────────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────┐
                    │   TRACE EXTRACTION              │
                    │                                 │
                    │   For each turn in each sim:    │
                    │   - target_state (what target   │
                    │     saw at that turn)           │
                    │   - target_action (what target  │
                    │     actually did)               │
                    └─────────────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────┐
                    │   LEARNER QUERY (Offline)       │
                    │                                 │
                    │   1. Load learner's main.py     │
                    │      via importlib              │
                    │                                 │
                    │   2. For each target_state:     │
                    │      learner_action =           │
                    │        learner.move(target_state)│
                    └─────────────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────┐
                    │   COMPARISON                    │
                    │                                 │
                    │   learner_action == target_action│
                    │                                 │
                    │   Same state, same question:    │
                    │   "What would you do here?"     │
                    └─────────────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────┐
                    │   FEEDBACK TO LEARNER           │
                    │                                 │
                    │   traces.json:                  │
                    │   {                             │
                    │     "accuracy": 0.85,           │
                    │     "mismatches": [             │
                    │       {                         │
                    │         "turn": 5,              │
                    │         "state": {...full...},  │
                    │         "learner_action": "up", │
                    │         "target_action": "down" │
                    │       },                        │
                    │       ...                       │
                    │     ]                           │
                    │   }                             │
                    └─────────────────────────────────┘
```

---

## Why Offline Evaluation?

### Old Design (v1) - FLAWED

```
Learner at position (2,3) → action "up"
Target at position (5,7)  → action "down"

Comparison: "up" != "down" → MISMATCH

Problem: Different positions = different states = unfair comparison!
This allowed metric hacking (learner could look up target's position)
```

### New Design (v2) - CORRECT

```
Target at position (5,7) → action "down"
Query learner: "What would you do at (5,7)?"
Learner code says: "up"

Comparison: "up" != "down" → MISMATCH

Now we're asking: "Given the EXACT SAME state, would you make the same decision?"
No way to hack - learner sees target's state, must produce target's action.
```

---

## Config Structure (3 Players)

```yaml
players:
  # Learner: edits code, does NOT play in simulation
  - agent: inverse
    name: learner
    editable: true
    config:
      agent: !include mini/default.yaml
      model: {...}

  # Target: strategy to be recovered, plays in simulation
  - agent: static
    name: target
    editable: false
    args:
      source_path: data/targets/greedy_food

  # Opponent: plays against target in simulation
  - agent: static
    name: opponent
    editable: false
    args:
      source_path: data/targets/greedy_food
```

---

## traces.json Format

```json
{
  "accuracy": 0.85,
  "total_actions": 100,
  "matching_actions": 85,
  "mismatches": [
    {
      "turn": 5,
      "learner_action": "up",
      "target_action": "down",
      "state": {
        "game": {"id": "abc123"},
        "turn": 5,
        "board": {
          "height": 11,
          "width": 11,
          "food": [{"x": 3, "y": 4}],
          "snakes": [...]
        },
        "you": {
          "head": {"x": 5, "y": 7},
          "body": [...],
          "health": 95
        }
      }
    }
  ]
}
```

The LLM agent uses these mismatches to identify patterns:
- "When food is above, target goes up, but my code went left"
- "Target avoids walls more aggressively than I do"
- etc.

---

## Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `_setup_learner_for_eval()` | inverse_strategy.py | Copy and load learner's code |
| `_load_learner_module()` | inverse_strategy.py | Use importlib to import main.py |
| `_query_learner()` | inverse_strategy.py | Call learner.move(state) |
| `extract_state_action_pairs()` | battlesnake.py | Parse traces for (state, action) |
| `_process_traces()` | inverse_strategy.py | Compute accuracy, collect mismatches |
