# Progress log

Newest entries at the bottom. One entry per step, written as each step finishes (not batched at the end).
Status key: DONE / IN PROGRESS / BLOCKED / NEXT. Task IDs refer to [TASKS.md](TASKS.md).

## Current status

_(updated at the end of every step)_

- **Phase:** 0 - Foundation (see PLAN.md)
- **Now:** writing PLAN.md, TASKS.md, PROGRESS.md
- **Next:** parametric CAD for the walker printed parts

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
