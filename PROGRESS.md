# Progress log

Newest entries at the bottom. One entry per step, written as each step finishes (not batched at the end).
Status key: DONE / IN PROGRESS / BLOCKED / NEXT. Task IDs refer to [TASKS.md](TASKS.md).

## Current status

_(updated at the end of every step)_

- **Phase:** 0 complete; Phase 1 (prove the pipeline on the real printer) is next and needs Jacob
- **Now:** waiting on Jacob for Phase 1 (T1.1); Claude can start Phase 2 CAD
- **Next:** T1.1 - Jacob opens `examples/cube_disk_2color.3mf` in Bambu Studio. Claude can start walker CAD (Phase 2) in parallel.

## Log

### 2026-10-20 - Foundation (before this log existed, reconstructed)
- DONE: `cad/make_cube_disk_3mf.py` - 2-material 3MF (cube filament 1, disk filament 2); meshes verified closed, volumes 8000 / 39.25 mm3. Not yet opened in Bambu Studio by the user.
- DONE: `printer/bambu_send.py` - status/send/slice for P1S + AMS over LAN. Offline smoke test only; never run against the real printer.
- DONE: `design/` - architecture, BOM, wiring, mechanical docs for 4-leg / 8-servo ESP32 walker.
- DONE: `firmware/` - MicroPython (PCA9685 driver, servos, creep gait, web remote, calibration, battery cutoff); 24 desktop tests pass. Not run on hardware.
- DONE: PR #1 and PR #2 merged to `main`.

### 2026-10-20 - Step 1: merge PR #2
- DONE: PR #2 merged; local `main` updated (00c6380).
- NEXT: create PLAN.md, TASKS.md.

### 2026-10-20 - Step 2: PLAN.md
- DONE: `PLAN.md` - goal, success criteria, current state, phases 0-6, critical path, risks, working agreements.
- NEXT: `TASKS.md`.

### 2026-10-20 - Step 3: TASKS.md
- DONE: `TASKS.md` - tasks T0-T6 by phase with owner (J/C), verification level, open decisions D1-D4.
- NEXT: record the progress-update rule in `CLAUDE.md`, link the three files from README, push, open PR.

### 2026-10-20 - Step 4: CLAUDE.md and README links
- DONE: `CLAUDE.md` records the "update PROGRESS.md after every step" rule so it persists across sessions; README links PLAN/TASKS/PROGRESS.
- NEXT: push branch `project-plan`, open PR.

### 2026-10-20 - Step 5: push and PR
- DONE: branch `project-plan` pushed; PR opened (see GitHub PR #3).
- NEXT: Jacob reviews/merges; then Phase 1 (T1.1) and Phase 2 CAD.

### 2026-10-20 - Step 6: merge PR #3
- DONE: PR #3 merged; PLAN.md, TASKS.md, PROGRESS.md, CLAUDE.md are on `main`.
- NEXT: T1.1 (Jacob: open the test 3MF in Bambu Studio). Phase 2 CAD can start in parallel.

### 2026-10-20 - Kid Edition request (Jacob's 9-year-old designs, programs and assembles the robot)
Multi-step request: (1) kid-friendly hardware, (2) design doc + plan updates, (3) parametric design GUI, (4) kid programming path, (5) PR. Branch `kid-edition` (also carries the unmerged `log-merge-pr3` fix).

#### Step K1: verify kid-friendly hardware
- DONE (web-checked, not hands-on): Kitronik Compact 16 Servo Driver Board for micro:bit - PCA9685, 16 servo channels, 3-12 V supply (servos powered from the same supply), terminal block or servo-style power connector with on/off switch, board regulates 3.3 V for the micro:bit, V1+V2 compatible, 68 x 46.5 x 10.6 mm, no soldering mentioned, MakeCode extension "Kitronik I2C-16-servo". One UK retailer showed "only 3 left" and Pimoroni lists it as no longer stocked -> availability risk, alternatives needed.
- NOT VERIFIED: the board's I2C address (could not read the Kitronik source) -> our extension will auto-detect 0x40 / 0x6C instead of assuming. MakeCode dependency syntax also unconfirmed -> extension will be standalone (talks to the PCA9685 directly).
- Fact checked on the way: MakeCode extensions can be added in the editor by pasting a github.com URL (Import URL); no approval needed for exact URLs.
- NEXT: K2 - write `design/kid-edition.md`, update BOM/PLAN/TASKS.

#### Step K2: kid edition design doc and plan updates
- DONE: `design/kid-edition.md` (roles kid/adult, component swaps with reasons, kid BOM ~$70-100, power note, mechanical changes, programming ladder, first power-on rules, open items); pointer added in `design/README.md`.
- DONE: PLAN.md has a Kid Edition track; Phase 2 CAD now produced by the GUI. TASKS.md has TK1-TK9; T2.4-T2.9 marked superseded.
- Honesty: prices other than the Kitronik board (seen at 12.30 GBP) are unverified estimates; nothing here is hardware-tested.
- NEXT: K3 - Walker Designer GUI (`gui/`).
