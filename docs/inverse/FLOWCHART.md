# Inverse Strategy Tournament - Flow Chart

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TOURNAMENT START                                     │
│                                                                             │
│  Config: learner (editable) + target (static)                               │
│  Creates: Game Container + Learner Container + Target Container             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ROUND 0: BASELINE                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SIMULATION PHASE ONLY                             │   │
│  │                                                                      │   │
│  │  1. Copy code from both containers → Game Container                  │   │
│  │  2. Run N simulations (game engine)                                  │   │
│  │  3. Write sim_0.jsonl, sim_1.jsonl... to /logs/                      │   │
│  │  4. Copy /logs/ → local logs/rounds/0/                               │   │
│  │  5. Parse traces, compute baseline accuracy                          │   │
│  │  6. Save traces.json (summary for agent)                             │   │
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
│  ┌──────────────────────────────────┐  ┌──────────────────────────────────┐│
│  │      LEARNER CONTAINER           │  │       TARGET CONTAINER           ││
│  │      (can edit)                  │  │       (static - NO edit)         ││
│  │                                  │  │                                  ││
│  │  1. Copy logs/rounds/N-1/        │  │  Code unchanged                  ││
│  │     → /logs/rounds/N-1/          │  │                                  ││
│  │     (includes traces.json)       │  │                                  ││
│  │                                  │  │                                  ││
│  │  2. pre_run_hook()               │  │                                  ││
│  │     - git tag round N-1          │  │                                  ││
│  │                                  │  │                                  ││
│  │  3. run() ← LLM AGENT            │  │                                  ││
│  │     - Reads /logs/rounds/N-1/    │  │                                  ││
│  │     - Analyzes traces            │  │                                  ││
│  │     - Edits code in /workspace   │  │                                  ││
│  │                                  │  │                                  ││
│  │  4. post_run_hook()              │  │                                  ││
│  │     - git commit                 │  │                                  ││
│  │     - git tag round N            │  │                                  ││
│  └──────────────────────────────────┘  └──────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SIMULATION PHASE (Round N)                             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      GAME CONTAINER                                  │   │
│  │                                                                      │   │
│  │  1. copy_between_containers:                                         │   │
│  │     Learner /workspace → Game /learner/                              │   │
│  │     Target /workspace  → Game /target/                               │   │
│  │                                                                      │   │
│  │  2. Validate code (both agents)                                      │   │
│  │                                                                      │   │
│  │  3. execute_round():                                                 │   │
│  │     Run N simulations                                                │   │
│  │     Write to /logs/sim_0.jsonl, sim_1.jsonl, ...                     │   │
│  │                                                                      │   │
│  │  4. copy_from_container:                                             │   │
│  │     Game /logs/ → local logs/rounds/N/                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    POST-SIMULATION (Local)                 ✅ DONE   │   │
│  │                                                                      │   │
│  │  1. Parse traces: get_parser(game) + parser.get_player_actions()     │   │
│  │  2. Compute strategy recovery accuracy:                              │   │
│  │     actions_equal(learner_action, target_action)                     │   │
│  │  3. Save traces.json to logs/rounds/N/                               │   │
│  │  4. Save results.json (round stats)                                  │   │
│  │  5. Compress logs/rounds/N-1/ → round_N-1.tar.gz                     │   │
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
│  2. Save metadata.json (includes all round stats, accuracy history)         │
│  3. Cleanup containers (optional)                                           │
│  4. Close file handlers                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Container Architecture

```
┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐
│  LEARNER CONTAINER │     │  TARGET CONTAINER  │     │   GAME CONTAINER   │
│                    │     │                    │     │                    │
│  /workspace/       │     │  /workspace/       │     │  /learner/         │
│    main.py ←edit   │     │    main.py (fixed) │     │  /target/          │
│                    │     │                    │     │  /logs/            │
│  /logs/rounds/     │     │  (no logs needed)  │     │  (game engine)     │
│    N-1/traces.json │     │                    │     │                    │
└────────────────────┘     └────────────────────┘     └────────────────────┘
         │                          │                          ▲
         │                          │                          │
         └──────────────────────────┴──── copy code ───────────┘
```

## Data Flow

```
Round N-1 Simulation
        │
        ▼
   sim_*.json (in Game Container)
        │
        ▼
   copy_from_container
        │
        ▼
   logs/rounds/N-1/ (Local)
        │
        ├──► traces.json (extracted)
        │
        ▼
   copy_to_container (to Learner)
        │
        ▼
   /logs/rounds/N-1/ (in Learner Container)
        │
        ▼
   LLM Agent reads traces, edits code
        │
        ▼
   Round N Simulation...
```
