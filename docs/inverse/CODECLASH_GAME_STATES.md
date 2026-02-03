# CodeClash Game State Documentation

This document catalogs the game state available from each CodeClash environment, to inform design decisions about exposing and gating state access for inverse strategy evaluation.

## State Availability Summary

| Game | Full Turn State | Replay Format | State Granularity | Replay Possible | Notes |
|------|----------------|---------------|-------------------|-----------------|-------|
| BattleSnake | ✅ Yes | `.jsonl` | Per-turn | ✅ Yes | Best for replay |
| Halite | ✅ Yes | `.hlt` (JSON) | Per-frame | ✅ Yes | Large files |
| RoboCode | ✅ Yes | `.xml` | Per-turn | ✅ Yes | 12-30MB/game |
| **RobotRumble** | ✅ Yes | `.json` | Per-turn | ✅ **Best** | State + actions! |
| **HuskyBench** | ✅ Yes | `.json` | Per-action | ✅ Yes | Poker - actions + cards! |
| CoreWar | ⚠️ Possible | `.log` + debugger | Per-cycle | ⚠️ With mods | pmars has debugger |

---

## Fast-Forward Replay Capability

A key requirement for inverse strategy evaluation is the ability to **fast-forward** to any point in a game and reconstruct complete state. This enables:

1. **Policy Querying**: Jump to turn N, extract state, ask "what would you do?"
2. **Action Comparison**: Compare policy output to actual logged action
3. **Divergence Scoring**: Measure how different a policy is from the original

### Fast-Forward Support by Game

| Game | Fast-Forward | State Completeness | Actions Logged | Use Case |
|------|-------------|-------------------|----------------|----------|
| **RobotRumble** | ✅ 100% | Full state every turn | ✅ Explicit | Perfect for inverse strategy |
| **BattleSnake** | ✅ 100% | Complete board state | ⚠️ Infer from diff | Excellent - easy JSON parsing |
| **Halite** | ✅ 100% | Full frames + moves | ✅ `moves[]` array | Good - complete replay data |
| **RoboCode** | ✅ 100% | Robots + bullets | ⚠️ Infer from diff | Good - verbose but complete |
| **HuskyBench** | ⚠️ 70% | Actions + revealed cards | ✅ Explicit | Poker limitation: future cards unknown |
| **CoreWar** | ✅ 100% | Full memory dump | N/A (programs) | Requires debugger scripting |

### What Each Game Logs

#### RobotRumble (Gold Standard)
```
Turn N → state.objs (all units with coords, health, team)
      → robot_actions (explicit: Move/Attack + direction)
      → errors (runtime errors with stack traces)
```
**Verdict**: Can jump to any turn and know exactly what each robot saw AND did.

#### BattleSnake
```
Turn N → board.snakes[].body, head, health, length
      → board.food[], board.hazards[]
      → game.ruleset
```
**Verdict**: Complete state. Actions inferred by comparing head positions between turns.

#### Halite
```
Frame N → frames[N] (2D array: [owner, strength] per cell)
       → moves[N] (2D array: direction per cell)
```
**Verdict**: Complete state AND explicit moves. Can reconstruct any frame.

#### RoboCode
```
Turn N → <robot x= y= energy= velocity= bodyHeading= gunHeading= radarHeading=>
      → <bullets> with x, y, power, state for each bullet in flight
```
**Verdict**: Complete state including bullets. Actions inferred from state changes.

#### HuskyBench (Poker)
```
Hand → playerHands (hole cards - revealed at end)
    → finalBoard (community cards - revealed progressively)
    → rounds[].action_sequence (RAISE/CALL/CHECK/FOLD + amounts)
```
**Verdict**: Can replay all decisions. BUT: future community cards are unknown at decision time. This is correct for poker EV calculations - evaluate based on information available, not outcome.

#### CoreWar
```
Cycle N → Memory dump via `list 0,7999` command
       → Process states via debugger
```
**Verdict**: Requires running pmars with `-e` flag and scripted debugger commands.

### Implications for Inverse Strategy

```python
# Pseudo-code for fast-forward evaluation
def evaluate_policy_at_turn(game_log, turn: int, policy):
    # 1. Fast-forward to turn N
    state = game_log.get_state_at_turn(turn)
    
    # 2. Query policy
    predicted_action = policy.decide(state)
    
    # 3. Get actual action (explicit or inferred)
    actual_action = game_log.get_action_at_turn(turn)
    
    # 4. Compare
    return action_similarity(predicted_action, actual_action)

# This works for 5/6 games with full fidelity
# HuskyBench works but with poker's inherent hidden information
```

### Bottom Line

**5 out of 6 CodeClash games support perfect fast-forward replay** for inverse strategy evaluation. HuskyBench (poker) works for strategy evaluation but respects poker's hidden information constraints - which is actually correct for evaluating poker decisions.

---

## BattleSnake

**Log Format:** `sim_{idx}.jsonl` (JSON Lines - one JSON object per line)

### State Structure (per turn)

```json
{
  "game": {
    "id": "uuid",
    "ruleset": {
      "name": "standard",
      "version": "cli",
      "settings": {
        "foodSpawnChance": 15,
        "minimumFood": 1,
        "hazardDamagePerTurn": 14,
        "royale": { "shrinkEveryNTurns": 25 }
      }
    },
    "timeout": 500
  },
  "turn": 0,
  "board": {
    "height": 11,
    "width": 11,
    "snakes": [
      {
        "id": "uuid",
        "name": "player-name",
        "health": 100,
        "body": [{"x": 5, "y": 9}, {"x": 5, "y": 9}, {"x": 5, "y": 9}],
        "head": {"x": 5, "y": 9},
        "length": 3,
        "latency": "21"
      }
    ],
    "food": [{"x": 4, "y": 10}, {"x": 5, "y": 5}],
    "hazards": []
  },
  "you": { /* same structure as snakes[i] for the receiving player */ }
}
```

### Available State Fields

| Field | Type | Description | Available |
|-------|------|-------------|-----------|
| `turn` | int | Current turn number | ✅ |
| `board.width/height` | int | Board dimensions | ✅ |
| `board.snakes[].body` | [{x,y}] | Complete body positions | ✅ |
| `board.snakes[].head` | {x,y} | Head position | ✅ |
| `board.snakes[].health` | int | Health (0-100) | ✅ |
| `board.snakes[].length` | int | Snake length | ✅ |
| `board.snakes[].latency` | string | Response time ms | ✅ |
| `board.food` | [{x,y}] | Food positions | ✅ |
| `board.hazards` | [{x,y}] | Hazard positions | ✅ |
| `game.ruleset` | object | Game rules/settings | ✅ |

### Replay Capability
**Full replay possible** - State is complete enough to:
1. Reconstruct any board position
2. Query a policy with exact game state
3. Derive moves from consecutive states (Δhead position)

### Design Considerations
- Each `.jsonl` line is independent - can seek to any turn
- `you` field perspective varies by which player's turn it was
- Moves can be inferred: `state[t+1].head - state[t].head`

---

## Halite

**Log Format:** 
- `sim_{idx}.log` - Text summary (turn numbers + final ranking)
- `*.hlt` - JSON replay file with full game state

### State Structure (`.hlt` replay)

```json
{
  "frames": [
    [
      // Frame 0: 2D array of [owner_id, strength] per cell
      [[0, 17], [0, 12], [1, 50], ...],  // row 0
      [[0, 20], [2, 30], [0, 15], ...],  // row 1
      // ... more rows
    ],
    // Frame 1, 2, ... (one per turn)
  ],
  "moves": [
    // Per-frame move commands by player
  ],
  "productions": [
    // 2D array of production values per cell
  ],
  "player_names": ["Player1", "Player2"],
  "map_width": 40,
  "map_height": 40
}
```

### Available State Fields

| Field | Type | Description | Available |
|-------|------|-------------|-----------|
| `frames[t][y][x]` | [owner, strength] | Cell ownership & strength | ✅ |
| `productions[y][x]` | int | Cell production rate | ✅ |
| `moves[t]` | array | Move commands per turn | ✅ |
| `map_width/height` | int | Map dimensions | ✅ |
| `player_names` | [string] | Player identifiers | ✅ |

### Replay Capability
**Full replay possible** - The `.hlt` format contains:
1. Complete board state every frame
2. Move commands issued
3. Production map (static)

### Design Considerations
- Large file sizes (1-6MB per game)
- Binary-like JSON structure optimized for Halite visualizer
- Need to parse frame-by-frame for state reconstruction

---

## CoreWar

**Log Format:** `sim_{idx}.log` (plain text) - **but full state IS available via pmars**

### Current CodeClash Output

```
Program "Stone/Imp Hybrid" (length 7) by "Claude (Round 3)"
       ORG      START
START  SPL.B  #     5, #     0     
       MOV.I  >  -953, $  -952     
       ...

Program "Counter Strategy v2" (length 22) by "Claude (Round 7)"
       ORG      START
START  SPL.B  $     4, $     0     
       ...

Stone/Imp Hybrid by Claude (Round 3) scores 232
Counter Strategy v2 by Claude (Round 7) scores 34
Results: 66 0 34
```

### ⚠️ Key Finding: Full State IS Available

CodeClash uses **pMARS** (portable Memory Array Redcode Simulator), which has a **full-featured debugger (`cdb`)** that CAN output complete game state.

**pMARS Debugger Capabilities:**
- **`-e` flag**: Enter interactive debugger mode
- **`step`/`STEP`**: Execute one cycle at a time
- **`print_core(start, stop)`**: Dump memory contents
- **`print_registers()`**: Show current execution state
- **`trace`**: Set trace points on memory addresses
- **`list`**: List core memory with disassembly

**Memory Structure (per cell):**
```c
typedef struct mem_struct {
  ADDR_T  A_value, B_value;   // Operand values
  FIELD_T opcode;             // Instruction opcode
  FIELD_T A_mode, B_mode;     // Addressing modes
  FIELD_T debuginfo;          // Debug/trace flags
} mem_struct;
```

**Core size**: 8000 cells by default

### Why CodeClash Doesn't Log Full State

1. **Design choice, not limitation**: CodeClash runs pmars in batch mode (`-r N` for N rounds)
2. **Not compiled with `-DSERVER`**: Debugger IS enabled in their build
3. **Could be modified**: Adding `-e` flag or piping debugger commands would expose state

### Available State Fields (Current vs Possible)

| Field | Type | Description | Current | Possible |
|-------|------|-------------|---------|----------|
| Program source | text | Redcode assembly | ✅ | ✅ |
| Program author | string | Creator name | ✅ | ✅ |
| Final scores | int | Win/loss/tie points | ✅ | ✅ |
| Per-cycle memory | mem_struct[8000] | Full core dump | ❌ | ✅ |
| Process queues | ADDR_T[] | Task pointers per warrior | ❌ | ✅ |
| Program counter | ADDR_T | Current instruction | ❌ | ✅ |
| Cycle number | int | Current simulation cycle | ❌ | ✅ |

### How to Enable Full State Logging

**Option 1: Scripted debugger commands (no code changes)**
```bash
# Pipe debugger commands to pmars with -e flag
echo -e "step 1000\nlist 0,7999\na\nquit" | ./pmars -e warrior1.red warrior2.red

# For periodic snapshots throughout a game:
CYCLES=80000 INTERVAL=1000 bash -c '
for ((i=0; i<CYCLES; i+=INTERVAL)); do
    echo "step $INTERVAL"
    echo "list 0,7999"
    echo "a"  # bypass pagination
done
echo "quit"
' | ./pmars -e warrior1.red warrior2.red > trace.log
```

**Option 2: Modify pmars source**
Add logging to `sim.c` in the main simulation loop to output state each cycle.

**Option 3: Use pMARS with `-v` (view mode)**
Requires graphical display but outputs state changes.

### Output Size & Performance

| Scenario | File Size | Time |
|----------|-----------|------|
| 1 snapshot (8000 cells) | ~30KB | <1ms |
| 5 snapshots (every 1000 cycles) | ~150KB | ~4ms |
| 80 snapshots (full game @ 1000 cycle intervals) | ~2.4MB | ~50ms |
| Every cycle (80,000 × 8000 cells) | **~2.4GB** | Minutes |

### Implementation Effort

| Approach | Effort | Result |
|----------|--------|--------|
| Shell script piping | **~10 lines** | Works, but messy text output |
| Python wrapper | **~50 lines** | Clean JSON output |
| Modify CodeClash arena | **~30 lines** | Integrated solution |

### Drawbacks

1. **Output parsing needed**: Format is text-based debugger output, not structured JSON:
   ```
   00003   DAT.F  #     0, #     0
   01673   ADD.AB #     4, $     3
   ```

2. **Pagination handling**: Need to send `a` (all) command to bypass interactive prompts

3. **No process queue in list**: Core memory is shown, but getting process queues requires additional `queue` commands

4. **Different paradigm** (fundamental limitation):
   - **BattleSnake**: LLM makes a decision EVERY TURN → can test "given state X, what move?"
   - **CoreWar**: LLM writes code ONCE, then it runs autonomously → no "per-turn decision" to evaluate
   - For CoreWar, "inverse strategy" = analyzing **Redcode assembly patterns**, not replaying decisions

### Replay Capability
**Replay IS possible** with modifications:
1. ✅ Full memory state can be dumped via debugger
2. ✅ Process queues are trackable
3. ✅ Deterministic simulation (same seed = same result)
4. ⚠️ Requires running pmars with debugger, not just batch mode

### Design Considerations
- CoreWar is fundamentally different - programs execute in shared memory
- "Moves" are instruction executions (SPL, MOV, JMP, etc.), not discrete player decisions
- State = 8000-cell memory array + process queues + program counters
- **Key insight**: The LLM writes the warrior program once, then it runs autonomously
- Policy "extraction" means understanding the Redcode assembly strategy, not per-turn decisions

---

## RoboCode

**Log Format:** 
- `results_{idx}.txt` - Score summary
- `record_{idx}.xml` - **FULL TURN-BY-TURN STATE** (12-30MB per game)

### ⚠️ Key Finding: Full State IS Available

The XML recording contains **complete state for every turn**, not just events!

### State Structure (`record_*.xml`)

```xml
<turn round="0" turn="5" ver="1">
    <robots>
        <robot id="0" vsName="MyTank*" state="ACTIVE" 
               energy="100.0" 
               x="730.158" y="101.480" 
               bodyHeading="2.047" gunHeading="1.305" radarHeading="5.232" 
               gunHeat="2.5" velocity="5.0" 
               teamName="player1.MyTank*" name="player1.MyTank*">
            <debugProperties/>
            <score totalScore="0.0" currentScore="0.0" 
                   totalBulletDamageScore="0.0" totalRammingDamageScore="0.0" .../>
        </robot>
        <robot id="1" ...>
            ...
        </robot>
    </robots>
    <bullets>
        <!-- Active bullets with position, heading, velocity, owner -->
    </bullets>
</turn>
```

### Available State Fields

| Field | Type | Description | Available |
|-------|------|-------------|-----------|
| `x`, `y` | float | Robot position | ✅ Every turn |
| `bodyHeading` | float | Body angle (radians) | ✅ Every turn |
| `gunHeading` | float | Gun angle (radians) | ✅ Every turn |
| `radarHeading` | float | Radar angle (radians) | ✅ Every turn |
| `energy` | float | Health (0-100+) | ✅ Every turn |
| `velocity` | float | Current speed | ✅ Every turn |
| `gunHeat` | float | Weapon cooldown | ✅ Every turn |
| `state` | enum | ACTIVE/HIT_WALL/HIT_ROBOT/DEAD | ✅ Every turn |
| `bullets` | array | All bullets in flight | ✅ Every turn |
| `score` | object | Detailed scoring breakdown | ✅ Every turn |

### File Sizes

| Scenario | File Size |
|----------|-----------|
| Single game (10 rounds, ~400 turns) | 12-30 MB |
| 50 games per round | 600MB - 1.5GB |

### Replay Capability
**Full replay possible** - The XML format contains:
1. ✅ Complete robot state every turn (position, heading, energy, velocity)
2. ✅ All bullets in flight with full trajectory info
3. ✅ Score snapshots
4. ✅ Debug output from robots

### Why Documentation Said "Event-Based"
The **Robot API** (what bots see) is event-based - robots only get `ScannedRobotEvent` when radar sees enemy. But the **recording format** captures everything.

### Design Considerations
- Large XML files need efficient parsing (streaming parser recommended)
- CodeClash uses `record_ratio` config to only record a fraction of games
- Like BattleSnake: can derive "what action at turn T?" from consecutive states

### Replay Capability
**Limited replay** - Event-based logs don't capture continuous state

---

## RobotRumble

**Log Format:** `sim_{idx}.json` (JSON - when run with `--raw` flag)

**Key Discovery:** The `rumblebot run term --raw` command outputs **complete JSON with full turn-by-turn state AND robot actions**. Files are ~1.1MB per game (100 turns × full state + actions).

### State Structure (per turn)

```json
{
  "winner": "Red",
  "errors": {},
  "turns": [
    {
      "state": {
        "turn": 0,
        "objs": {
          "113": {
            "id": "113",
            "coords": [5, 17],
            "obj_type": "Unit",
            "type": "Soldier",
            "team": "Blue",
            "health": 5
          },
          "1": {
            "id": "1",
            "coords": [0, 0],
            "obj_type": "Terrain",
            "type": "Wall"
          }
        }
      },
      "robot_actions": {
        "113": {"Err": {"RuntimeError": {"summary": "...", "details": "..."}}},
        "114": {"Ok": {"type": "Move", "direction": "South"}},
        "115": {"Ok": {"type": "Attack", "direction": "East"}}
      },
      "logs": {},
      "debug_inspect_tables": {},
      "debug_locate_queries": {}
    }
  ]
}
```

### Available State Fields

| Field | Type | Description | Available |
|-------|------|-------------|-----------|
| `winner` | string | "Blue"/"Red"/"tie" | ✅ |
| `turns[].state.turn` | int | Turn number | ✅ |
| `turns[].state.objs` | dict | All game objects | ✅ |
| Unit `coords` | [x,y] | Robot position | ✅ |
| Unit `team` | string | "Blue"/"Red" | ✅ |
| Unit `health` | int | Robot health | ✅ |
| Unit `type` | string | "Soldier" etc. | ✅ |
| Terrain `type` | string | "Wall" etc. | ✅ |
| `robot_actions` | dict | **Actions per unit** | ✅ |
| Action `type` | string | "Move"/"Attack" | ✅ |
| Action `direction` | string | "North"/"South"/"East"/"West" | ✅ |
| `errors` | dict | Runtime errors with stack traces | ✅ |
| `logs`, `debug_*` | dict | Debug information | ✅ |

### Replay Capability
**FULL REPLAY POSSIBLE** - This is the **best** game for inverse strategy:
1. Complete state every turn (all unit positions, health, terrain)
2. **Explicit action records** - Know exactly what each robot decided
3. Action outcomes (Ok vs Err with full error details)
4. ~100 turns per game, ~1.1MB per simulation

### Usage
```bash
# Run simulation with JSON output
rumblebot run term --raw ./bot1 ./bot2

# Output: sim_*.json files with full state
```

---

## HuskyBench (Poker)

**Log Format:** `game_log_{round}_{gameid}.json` (JSON per poker hand)

**Key Discovery:** HuskyBench is a **poker game**, and the `game_log_*.json` files contain **complete poker hand histories** with every action, pot state, cards, and final outcomes.

### State Structure

```json
{
  "gameId": "dad6b774-2ca5-4cbf-b503-bb12924b2580",
  "playerNames": {"1263106363": "player1", "2939737361": "player2"},
  "blinds": {"small": 5, "big": 10},
  "finalBoard": ["Td", "Ts", "Kh", "Jc", "Jh"],
  "playerHands": {
    "1263106363": ["7h", "9s"],
    "2939737361": ["9h", "Qc"]
  },
  "playerMoney": {
    "initialAmount": 10000,
    "finalMoney": {"1263106364": 9980, "2939737362": 10020},
    "gameScores": {"1263106364": -5, "2939737362": 5}
  },
  "rounds": {
    "0": {
      "pot": 15,
      "bets": {"1263106363": 5, "2939737361": 10},
      "actions": {"1263106363": "RAISE", "2939737361": "RAISE"},
      "action_sequence": [
        {
          "player": 1263106363,
          "action": "RAISE",
          "amount": 5,
          "timestamp": 1768823410616,
          "pot_after_action": 5,
          "total_pot_after_action": 5
        }
      ]
    },
    "1": {"actions": {"1263106363": "CHECK", "2939737361": "CHECK"}},
    "2": {"actions": {"1263106363": "FOLD", "2939737361": "CHECK"}}
  }
}
```

### Available State Fields

| Field | Type | Description | Available |
|-------|------|-------------|-----------|
| `gameId` | string | Unique hand identifier | ✅ |
| `playerNames` | dict | Player ID → name mapping | ✅ |
| `blinds` | dict | Small/big blind amounts | ✅ |
| `finalBoard` | [string] | Community cards (5 cards) | ✅ |
| `playerHands` | dict | Hole cards per player | ✅ |
| `playerMoney` | dict | Stack sizes, deltas | ✅ |
| `rounds` | dict | Pre-flop, Flop, Turn, River | ✅ |
| `action_sequence` | [action] | **Every action in order** | ✅ |
| Action `player` | int | Who acted | ✅ |
| Action `action` | string | RAISE/CALL/CHECK/FOLD | ✅ |
| Action `amount` | int | Bet amount | ✅ |
| Action `pot_after_action` | int | Pot size after | ✅ |
| `sidePots` | [dict] | Side pot tracking | ✅ |

### Replay Capability
**FULL REPLAY POSSIBLE** - Excellent for poker strategy analysis:
1. Complete action history with exact sequence
2. All cards revealed (hole cards + board)
3. Pot states after every action
4. Money tracking (initial, final, deltas)
5. Standard poker betting rounds (0=pre-flop, 1=flop, 2=turn, 3=river)

### Notes
- Each `game_log_*.json` = one poker hand
- ~20 hands per round (configurable via `--sim-rounds`)
- Files are 5-11KB each (compact)
- Rounds: 0=Pre-flop, 1=Flop, 2=Turn, 3=River

---

## Design Recommendations

### Tier 0: Gold Standard 🏆
- **RobotRumble** - **BEST candidate for inverse strategy**
  - Complete state per turn in JSON
  - **Explicit action records** - Know exactly what each robot decided
  - Action types: Move (direction) and Attack (direction)
  - Error logs with full stack traces
  - Debug inspection tables available
  - ~1.1MB per game, ~100 turns

### Tier 1: Full State Access (Ready for MVP)
- **BattleSnake** - Excellent candidate
  - Complete state per turn in JSON
  - Easy parsing, deterministic move derivation
  - HTTP API allows live testing

- **RoboCode** - Excellent candidate
  - Complete state per turn in XML
  - All robot positions, headings, energy, bullets
  - Larger files but full coverage (12-30MB/game)

- **HuskyBench (Poker)** - Excellent candidate
  - Complete hand histories with every action
  - All cards revealed, pot states, money tracking
  - Compact files (5-11KB per hand)

### Tier 2: Full State with Extra Parsing
- **Halite** - Good candidate
  - Full state in `.hlt` files (JSON frames)
  - Requires frame extraction logic
  - Larger files to process

### Tier 2.5: Full State with Engine Modification
- **CoreWar** - Possible with work
  - pmars debugger CAN output full state
  - Requires: debugger scripting or source modification
  - Different paradigm: program-level strategy, not turn-level decisions

### Tier 3: Aggregate Only (Not Suitable for Turn Replay)
- **None!** All CodeClash games have full state available 🎉

---

## State Gating Architecture

If exposing state through a unified interface:

```python
class GameStateProvider(ABC):
    """Abstract interface for accessing game state."""
    
    @abstractmethod
    def supports_full_replay(self) -> bool:
        """Whether this game supports turn-by-turn state."""
        pass
    
    @abstractmethod
    def get_state_at_turn(self, game_id: str, turn: int) -> dict | None:
        """Get complete state at a specific turn (if supported)."""
        pass
    
    @abstractmethod
    def get_final_scores(self, game_id: str) -> dict[str, float]:
        """Get final game scores (always available)."""
        pass
    
    @abstractmethod
    def iter_states(self, game_id: str) -> Iterator[dict]:
        """Iterate through all states (if supported)."""
        pass
```

### Implementations

| Game | `supports_full_replay()` | `get_state_at_turn(turn)` | `get_actions_at_turn(turn)` | `iter_states()` |
|------|-------------------------|---------------------------|----------------------------|-----------------|
| **RobotRumble** | `True` | ✅ `data['turns'][turn]['state']` | ✅ `data['turns'][turn]['robot_actions']` | ✅ Iterate `turns[]` |
| **BattleSnake** | `True` | ✅ Read line `turn+1` from `.jsonl` | ⚠️ Infer from state diff | ✅ Stream lines |
| **RoboCode** | `True` | ✅ Parse `<turn turn="N">` from XML | ⚠️ Infer from state diff | ✅ Stream `<turn>` elements |
| **HuskyBench** | `True` | ✅ `data['rounds'][round]['action_sequence'][idx]` | ✅ Explicit in `action_sequence` | ✅ Iterate rounds + actions |
| **Halite** | `True` | ✅ `data['frames'][turn]` | ✅ `data['moves'][turn]` | ✅ Iterate frames |
| **CoreWar** | `True` (with mods) | ⚠️ Run pmars debugger with `list 0,7999` | ❌ N/A (program execution) | ⚠️ Script debugger |

### Implementation Details

#### RobotRumble (Best - Tier 0)
```python
def get_state_at_turn(data: dict, turn: int) -> dict:
    return data['turns'][turn]['state']

def get_actions_at_turn(data: dict, turn: int) -> dict:
    return data['turns'][turn]['robot_actions']
    # Returns: {"unit_id": {"Ok": {"type": "Move", "direction": "South"}}, ...}
```

#### BattleSnake (Tier 1)
```python
def get_state_at_turn(filepath: str, turn: int) -> dict:
    with open(filepath) as f:
        for i, line in enumerate(f):
            if i == turn + 1:  # Line 0 is metadata, line 1 is turn 0
                return json.loads(line)
    # State contains: board.snakes[].body, head, health, length + food, hazards
```

#### RoboCode (Tier 1)
```python
def get_state_at_turn(filepath: str, round_num: int, turn: int) -> dict:
    tree = ET.parse(filepath)
    for turn_elem in tree.findall('.//turn'):
        if turn_elem.get('round') == str(round_num) and turn_elem.get('turn') == str(turn):
            robots = []
            for r in turn_elem.findall('robot'):
                robots.append({
                    'id': r.get('id'), 'x': float(r.get('x')), 'y': float(r.get('y')),
                    'energy': float(r.get('energy')), 'velocity': float(r.get('velocity')),
                    'bodyHeading': float(r.get('bodyHeading')), 'gunHeading': float(r.get('gunHeading'))
                })
            return {'robots': robots}
```

#### HuskyBench / Poker (Tier 1)
```python
def get_state_at_action(data: dict, round_idx: str, action_idx: int) -> dict:
    action = data['rounds'][round_idx]['action_sequence'][action_idx]
    return {
        'player': action['player'],
        'action': action['action'],  # RAISE, CALL, CHECK, FOLD
        'amount': action['amount'],
        'pot_after': action['pot_after_action'],
        'hole_cards': data['playerHands'],  # Available at end
        'board': data['finalBoard']  # Community cards
    }
```

#### Halite (Tier 2)
```python
def get_state_at_turn(data: dict, turn: int) -> dict:
    return {
        'frame': data['frames'][turn],      # 2D array: [owner, strength] per cell
        'moves': data['moves'][turn] if turn < len(data['moves']) else None  # Move directions
    }
    # frames[turn][y][x] = [owner_id, strength]
    # moves[turn][y][x] = direction (0-4: STILL, NORTH, EAST, SOUTH, WEST)
```

#### CoreWar (Tier 2.5)
```bash
# Requires pmars debugger scripting
echo -e "step 1000\nlist 0,7999\nquit" | pmars -e warrior1.red warrior2.red
# Outputs full 8000-cell memory dump after 1000 cycles
```

---

## File Locations

### BattleSnake
```
logs/{user}/PvpTournament.BattleSnake.{config}/rounds/
└── round_N.tar.gz
    └── N/
        ├── sim_0.jsonl      # JSONL: line 0 = metadata, lines 1+ = turn states
        ├── sim_1.jsonl      # Each file = one game
        ├── ...
        └── results.json     # Round summary
```
**File format:** `.jsonl` (JSON Lines)
**Size:** ~1-5KB per game
**Typical games per round:** 1000

### Halite
```
logs/{user}/PvpTournament.Halite.{config}/rounds/
└── round_N.tar.gz
    └── N/
        ├── replay-{timestamp}-{seed}.hlt    # JSON replay file
        ├── sim_0.log                         # Text summary
        └── results.json
```
**File format:** `.hlt` (JSON with frames + moves arrays)
**Size:** ~100KB-1MB per game (depends on game length)
**Key fields:** `frames[]`, `moves[]`, `productions`, `player_names`

### RoboCode
```
logs/{user}/PvpTournament.RoboCode.{config}/rounds/
└── round_N.tar.gz
    └── N/
        ├── record_0.xml     # Full battle recording
        ├── record_1.xml     # XML with <turn> elements containing <robot> states
        ├── ...
        └── results.json
```
**File format:** `.xml` (RoboCode battle recording)
**Size:** 12-30MB per game (verbose XML)
**Key elements:** `<turn round="R" turn="T">`, `<robot id= x= y= energy= velocity= bodyHeading=>`

### RobotRumble
```
logs/{user}/PvpTournament.RobotRumble.{config}/rounds/
└── round_N.tar.gz
    └── N/
        ├── sim_0.json       # JSON with full turns[] array (requires --raw flag)
        ├── sim_1.json
        ├── ...
        └── results.json
```
**File format:** `.json` (full state + actions)
**Size:** ~1.1MB per game
**Key fields:** `turns[].state.objs`, `turns[].robot_actions`, `winner`

### HuskyBench (Poker)
```
logs/{user}/PvpTournament.HuskyBench.{config}/rounds/
└── round_N.tar.gz
    └── N/
        ├── game_log_0_{gameid}.json    # One JSON per poker hand
        ├── game_log_1_{gameid}.json
        ├── ...
        ├── engine.log                   # Engine output
        ├── {player}.log                 # Per-player logs
        └── results.json
```
**File format:** `.json` (poker hand history)
**Size:** 5-11KB per hand
**Key fields:** `playerHands`, `finalBoard`, `rounds[].action_sequence`, `playerMoney`

### CoreWar
```
logs/{user}/PvpTournament.CoreWar.{config}/rounds/
└── round_N.tar.gz
    └── N/
        ├── sim_0.log        # pmars text output (winner only)
        ├── sim_1.log
        ├── ...
        └── results.json
```
**File format:** `.log` (text, winner only by default)
**Size:** ~100 bytes per game
**Note:** Full state requires running pmars debugger separately with `-e` flag

---

## Quick Reference: Parsing Commands

```bash
# BattleSnake - get turn 5 state
sed -n '6p' sim_0.jsonl | jq '.board.snakes'

# Halite - get frame count
jq '.num_frames' replay.hlt

# RoboCode - count turns (approximate)
grep -c '<turn ' record_0.xml

# RobotRumble - get turn 10 actions
jq '.turns[10].robot_actions' sim_0.json

# HuskyBench - get all actions in a hand
jq '[.rounds[].action_sequence[]] | length' game_log_0_*.json

# CoreWar - dump memory at cycle 5000
echo -e "step 5000\nlist 0,7999\nquit" | pmars -e warrior1.red warrior2.red
```
