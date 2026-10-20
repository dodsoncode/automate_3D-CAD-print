# Big-picture plan

## Goal

An automated pipeline, driven by Claude and run by Jacob, that goes from a **parametric Python CAD model** to a
**multi-material print on a Bambu P1S + AMS**, proven on a **multi-piece 3D-printed walking robot** that is
programmed and controlled by a microcontroller.

```
design intent -> Python CAD -> multi-material 3MF -> slice -> send to P1S -> printed parts
                                                                      |
                              assemble + wire + flash firmware <------+
                                       |
                              calibrate -> tune gait -> walking robot
```

## Success criteria

1. One command regenerates every printed part as a Bambu Studio-ready 3MF with the right AMS filament per part.
2. One command slices and sends a job to the P1S, with a confirmation step and a busy-printer check.
3. The robot stands, walks forward/backward, turns, and shuts down safely at low battery.
4. The whole thing is reproducible from the repo (parts list, code, print files, calibration steps).

## Where we are

| Area | State |
|---|---|
| 3MF generation (2-material proof) | Built and verified by script; not yet opened in Bambu Studio |
| Printer link (P1S LAN) | Built; never run on the real printer |
| Robot architecture + docs | Done (design/) |
| Firmware | Built, 24 desktop tests pass; never run on hardware |
| Walker CAD (printed parts) | **Not started** |
| Parts ordered / printer set up for LAN | Not started (user) |

## Phases

### Phase 0 - Foundation (done)
Cube + disk 3MF generator, P1S send script, design docs, firmware, repo + PR workflow.

### Phase 1 - Prove the pipeline on the real printer (the biggest unknown)
Open the test 3MF in Bambu Studio and confirm the two parts show as two filaments. Enable LAN + Developer
Mode on the P1S, run `status`, then slice-and-print the cube. **Exit:** a two-color cube comes off the bed.
Why first: every later step depends on it, and the 3MF layout and MQTT/FTP details are the parts most
likely to need fixes against a real printer and firmware.

### Phase 2 - Walker CAD
Parametric parts in `cad/walker/` from one `params.py`: chassis tray + lid, coxa bracket (L/R), femur, foot pad.
Needs a real mesh/CAD backend (build123d/CadQuery or an STL boolean library) since the current generator only
makes primitives. Export each part as a 3MF; multi-material accents where useful. Validate fit with checks
(volumes, bounding boxes, servo-pocket clearance) before printing.
**Exit:** all parts generate, pass checks, and a single leg test-print fits the MG90S.

### Phase 3 - Slice-and-send automation
Slicing profile handling (Bambu Studio CLI or a pre-exported plate), a `make` / single entry-point script that
goes CAD -> 3MF -> slice -> upload -> start, plus job status/monitoring. **Exit:** one command prints a part.

### Phase 4 - Electronics bring-up (in parallel with Phase 2-3 once parts arrive)
Order parts (BOM in design/components.md), verify UBEC output, flash MicroPython, I2C scan, one servo,
then all servos with horns off. **Exit:** all 8 servos move correctly on the bench from the web remote.

### Phase 5 - Assembly, calibration, first steps
Print full set, assemble at neutral, calibrate (sign/offset), stand, then walk on blocks, then on the floor.
**Exit:** robot walks forward and turns.

### Phase 6 - Tune and extend (optional)
Stride/lift/period tuning, TPU feet, IMU tilt feedback, battery runtime test, 3-DOF legs, documentation and a
build guide.

## Dependencies and critical path

```
Phase 1 (pipeline proven) --> Phase 3 (automation) --\
Phase 2 (walker CAD) ---------------------------------+--> Phase 5 (assembly/walk) --> Phase 6
Phase 4 (parts + bring-up, needs user ordering) ------/
```
Critical path: Phase 1 -> Phase 2 (CAD) -> print -> Phase 5. Parts ordering (Phase 4) has shipping lead time,
so ordering early is free schedule.

## Risks and open questions

| Risk | Impact | Mitigation |
|---|---|---|
| Bambu Studio rejects/ignores the hand-built 3MF structure (extruder metadata) | Pipeline blocked | Phase 1 test first; fallback: export a reference 3MF from Studio and match its structure |
| P1S firmware blocks third-party LAN control | Send script unusable | Use Developer Mode; fallback: manual export + SD card / Bambu Studio send |
| Cloud sandbox cannot reach the printer | Can't send from here | Run `bambu_send.py` on a local machine (or via the desktop app link) |
| Servo dimensions/horns differ from the assumed MG90S | Printed parts don't fit | Measure with calipers; print one leg first; all dims in `params.py` |
| 2-DOF legs too weak / unstable | Robot won't walk well | Creep gait keeps 3 feet down; fall back to 3-DOF using free PCA9685 channels |
| Servo power brownouts | Resets, jitter | Separate UBEC, bulk cap, common ground (in design) |
| TPU not feedable through the original AMS | No flexible feet via AMS | Print pads from external spool or use rubber/foam pads |
| Part prices/availability in BOM drift | Budget off | Re-check before ordering |

Open questions for Jacob: confirm P1S "PS1" = P1S; filament colors/types on hand; preferred servo (MG90S assumed);
local machine available to run the send script; any size/appearance preferences for the robot.

## Working agreements

- Every task is a branch + PR to `main`; Jacob merges (or asks Claude to).
- `PROGRESS.md` is updated after **each step**, including every sub-step of a multi-step request.
- `TASKS.md` is the source of truth for what is open; `PLAN.md` changes only when the plan changes.
- Be explicit about verified vs unverified: script-checked, desktop-tested, or confirmed on real hardware.
