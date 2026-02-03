# TODO: Inverse Strategy - CodeClash Style

## Completed ✅

### Infrastructure
- [x] Copy `minisweagent.py` from CodeClash
- [x] Create `InverseStrategyAgent` class
- [x] Register agents in `__init__.py`
- [x] Add `REPO_DIR` to package
- [x] Create `AbstractTournament` base class
- [x] Create `InverseStrategyTournament` class
- [x] Create example config files
- [x] Wire up static evaluator with tournament
- [x] Implement trace file format for arena
- [x] Add accuracy computation (matching actions / total actions)
- [x] Use model name in directory naming (matches CodeClash convention)

### Offline Evaluation (v2) ✨
- [x] **3-player design**: learner (offline), target, opponent
- [x] Learner does NOT play in simulation
- [x] Extract (state, action) pairs from target's traces
- [x] Query learner's code offline with target's exact states
- [x] Collect ALL mismatches with full game state
- [x] Add `extract_state_action_pairs()` to BattleSnake parser
- [x] Use `importlib` for direct module loading (no shell escaping issues)
- [x] Add `evaluation_failed` flag for error handling

### Prompt Design
- [x] Design prompts that explain imitation task
- [x] Include trace format (`traces.json`, `sim_*.jsonl`)
- [x] Show evaluation results (accuracy, mismatches with full state)
- [x] Add README_agent.md for cross-round notes
- [x] Update prompts to explain offline evaluation clearly

### Testing & Validation
- [x] End-to-end test with BattleSnake
- [x] Test with GPT-4o via TRAPI → 29.27% peak accuracy
- [x] Test with GPT-5 via TRAPI → **55.08% peak accuracy** (old design)
- [x] Test GPT-5 with offline evaluation → **95.20% accuracy** ✨
- [x] Verify no metric hacking possible with new design

## Results

| Model | Design | Peak Accuracy | Rounds | Notes |
|-------|--------|--------------|--------|-------|
| GPT-4o | v1 (live) | 29.27% | 2 | Old design |
| GPT-5 | v1 (live) | 55.08% | 2 | Old design |
| **GPT-5** | **v2 (offline)** | **95.20%** | 3 | ✅ No hacking |

## Next Steps

### High Priority
- [ ] Run more models (Claude, Gemini, o3) with offline evaluation
- [ ] Test with harder targets (not just greedy_food)
- [ ] Analyze remaining 5% mismatches (edge cases?)

### Analysis
- [ ] Compare v1 vs v2 results systematically
- [ ] Document learner's strategy discovery process
- [ ] Visualize accuracy progression across rounds

### Features
- [ ] Add automatic model comparison script
- [ ] Add visualization of accuracy over rounds
- [ ] Support extracting target from PvP tournament winners

### Games
- [ ] Add RobotRumble `extract_state_action_pairs()`
- [ ] Add Connect4 support
- [ ] Test game-agnostic offline evaluation

## Design Notes (v2 - Offline Evaluation)

```
SIMULATION PHASE (Round N)
├── Game Container
│   ├── /target/   ← target's code (plays)
│   ├── /opponent/ ← opponent's code (plays)
│   └── Run simulations, capture target's (state, action) pairs

OFFLINE EVALUATION
├── Load learner's main.py via importlib
├── For each target_state:
│   learner_action = learner.move(target_state)
│   Compare: learner_action == target_action
├── Collect ALL mismatches with full state

EDIT PHASE (Round N)
├── Learner Container
│   └── /logs/rounds/N-1/traces.json ← accuracy + mismatches
│   └── LLM reads mismatches, edits code to match target
```

**Why offline?** Old design compared actions at different states (flawed).
New design asks: "Given the EXACT SAME state, would you make the same decision?"
