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

#### Step K3a: GUI architecture decided
- Decision: the designer GUI is the single source of geometry for the kid edition. Parts are built as extruded 2D profiles with holes (closed shells, shared vertices) - no CSG library needed; each leg part is identical for all 4 legs (rotated copies), so only 3 leg part types + body.
- Decision: files `gui/js/{gait,geom,model,export3mf}.js` (UMD, testable) + `gui/index.html` (UI, three.js preview with walking animation). three.js r128 + JSZip vendored under `gui/vendor/` (works offline; no CDN needed).
- Decision: export = zip with design JSON, one 3MF per print plate (parts packed on a 256 mm bed), README with filament slots. Uses the same 3MF structure as `cad/make_cube_disk_3mf.py` (still unconfirmed in Bambu Studio - T1.1).
- NEXT: write gait.js (port of firmware/src/gait.py) + parity test, then geom.js.

#### Step K3b: gait.js and geom.js
- DONE: `gui/js/gait.js` (JS port of `firmware/src/gait.py`). Parity test `gui/tests/test_gait_parity.py` runs both on a 14.5 s scripted sequence (forward, spin, reverse, mixed, stop) and compares: max difference < 1e-9. Desktop-tested.
- DONE: `gui/js/geom.js` - extruded polygons with holes -> closed shells, rotations/mirrors keep triangles outward, volume/bbox/closedness checks. Smoke-tested: box 1000 mm3, box with hole 880 mm3 (exact), all shells closed, volumes unchanged after rotX/mirror/extrudeUW/extrudeVW.
- DONE: vendored three.js r128, OrbitControls, JSZip 3.10.1 (both MIT) in `gui/vendor/`.
- NEXT: `gui/js/model.js` (parameters -> layout -> parts -> checks), then `export3mf.js`.

### 2026-10-20 - K3c: weight-shift gait ("sway") and robust geometry kit
- DONE: Found the design failed its own stability check (support-polygon margin about -3.5 mm): a symmetric 4-leg walker tipped when a foot lifted. Fix = (1) stance hips nudge the body away from the lifted corner ("sway", `GAIT_SWAY_DEG` = 8), (2) swing shortened from 25% to 20% of the cycle so all four feet are down briefly (`SLOT_SPACING` stays 0.25), (3) sway eases in 8% of a cycle before a lift and out 5% after landing.
- DONE: Same maths in `firmware/src/gait.py` and `gui/js/gait.js`; parity test includes a sway scenario. Firmware tests 27 pass, GUI parity tests 3 pass (script-checked).
- DONE: `gui/js/geom.js` robustness (collinear-hole perturbation, triangle orientation, triangle-count assertion); `gui/js/model.js` parametric model. All 31 shells closed with positive volume for the default and 4 presets; stability margin now +4.2 to +8.8 mm (modelled, not measured).
- Verification: script-checked only. Real servo speed (swing is now about 200 deg/s peak, MG90S limit is higher), real centre of mass and real foot friction are unverified.
- NEXT: `gui/js/export3mf.js`, then `gui/index.html` (K3 continues), then K4 MakeCode path, K5 publish + PR.

### 2026-10-20 - K3d: 3MF export + independent validator
- DONE: `gui/js/export3mf.js` - one Bambu-style 3MF per print plate (same layout as the Python writer, per-part AMS slot), plus `walker_design.json` and `README.txt`, all in one zip. Deterministic output.
- DONE: `cad/validate_3mf.py` - independent check (closed oriented meshes, positive volume, bed fit, extruder 1-4). Default design: 1 plate, 13 objects, 14 meshes, all OK; the original cube+disk example also OK. Script-checked only; still NOT opened in Bambu Studio (T1.1).
- NEXT: `gui/index.html` (3D preview, sliders, checks, finish button), then Playwright tests.

### 2026-10-20 - K3e: Walker Designer GUI built and published
- DONE: `gui/index.html` - 3D preview (walking animation, Angle/Top/Side/Front, motors on/off, print-plate view), kid-worded sliders on Body/Legs/Walking pages, 4-slot AMS color picker and per-part slot assignment, My parts (battery presets, measured motor/board sizes), Finish page (traffic-light checks, plastic/time estimate, zip of 3MF plates + design + walking numbers). Saves your design in the browser; Save/Open design file; Start over.
- DONE: defaults retuned so the starting design shows all green (sway 14 deg, corner radius 3 mm). `firmware/src/config.py` GAIT_SWAY_DEG now 14 to match.
- DONE: `gui/build_artifact.py` -> `gui/walker-designer.html` (single file for offline use) and published as a claude.ai artifact (private).
- Verification: desktop-tested in headless Chromium (6 browser tests + 3 parity tests): no console errors, feet on floor, +hip moves each foot forward, slider rebuilds, exported 3MFs pass `cad/validate_3mf.py`, no sideways scroll at 390 px. NOT tested: real tablet touch use, Bambu Studio import (T1.1), real part sizes, the artifact's download button (needs the viewer's confirmation).
- NEXT: K4 MakeCode path (`makecode-kid/`), then K5 PR.

### 2026-10-20 - K4: MakeCode path for the kid
- DONE: `makecode-kid/` - `gait.ts` (port of `gait.py`), `walker.ts` (PCA9685 driver that auto-detects 0x40 / 0x6C, blocks: start, stand, walk, walk for N seconds, stop, set leg, relax, step size, foot lift, speed, lean, nudge, flip, wiggle), `dist/custom.ts` (single file to paste into a MakeCode project), `build_custom.py`, `README.md`, lessons level 0-4.
- DONE: `makecode-kid/tests/test_ts_parity.py` - TypeScript gait equals Python gait to 1e-9 over 3 scenarios (incl. turning, sway, ramps); fake-board checks: stand = 1500 us on all 8 channels, front-left hip sign matches firmware, finds board at 0x6C, sad face if no board. 7 tests pass (needs node + the `typescript` npm package).
- Verification: script-checked only. NOT loaded into the MakeCode editor (block wording, I2C return codes on a real micro:bit are unverified) and NOT run on hardware.
- DONE: TASKS.md TK3-TK5 ticked.
- NEXT: K5 - open the PR (carries the earlier `log-merge-pr3` fix too). Do not merge until Jacob asks.

### 2026-10-20 - K5: PR opened
- DONE: PR #4 `kid-edition` -> `main` opened (includes the `log-merge-pr3` fix). Not merged; waiting for Jacob.
- Open for Jacob: TK6-TK9 in TASKS.md (buy BOM, measure parts, open a GUI 3MF in Bambu Studio, print one leg, confirm board I2C address, bench-test levels 0-3).
- NEXT: Jacob reviews / says merge.
