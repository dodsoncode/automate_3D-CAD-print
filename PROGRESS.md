# Progress log

Newest entries at the bottom. One entry per step, written as each step finishes (not batched at the end).
Status key: DONE / IN PROGRESS / BLOCKED / NEXT. Task IDs refer to [TASKS.md](TASKS.md).

## Current status

_(updated at the end of every step)_

- **Phase:** 0 complete; Phase 1 (prove the pipeline on the real printer) is next and needs Jacob
- **Slice for P1S (branch `slice-send`, PR not yet opened):** final review fix wave applied (2026-11-12): PETG HF + Cool Plate refused, bed-heat and excluded-corner G-code checks, clear overhang and out-of-memory messages, a memory/time watchdog around the engine, an install step that proves the engine by slicing a test cube, and page fixes. Verification: slicer core and install step run with the real engine in Claude's workspace; server and page tested with a fake slicer in a desktop browser; real end-to-end runs through the real server. NOT verified: the slicer on Render (including its memory limit and the engine's system libraries), a real phone, any print.
- **Now:** waiting on Jacob for Phase 1 (T1.1); Claude can start Phase 2 CAD. Side tool `image3d/` (photo -> STL editor) is built and desktop-tested; the editor is published as a claude.ai artifact. TI6 and TI7 are done (Jacob reported the Render deploy and phone editor working on 2026-11-12). After the Slice for P1S PR is merged Jacob does SL4 (redeploy, check the slicer is available) and SL5 (first small watched print)
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

### 2026-10-21 - Step: merge PR #4
- DONE: PR #4 (Kid Edition) merged to `main` at Jacob's request.
- NEXT: Jacob's items TK6-TK9 in TASKS.md (open a GUI 3MF in Bambu Studio, measure parts, print one leg, confirm board I2C address, bench-test levels 0-3).

### 2026-10-21 - Styles S1: three locomotion styles planned
- Request: Jacob finds the robot crab-like; wants other styles, e.g. windmill legs for rough terrain. Chose: wheg rover (4 spoked windmill legs on continuous-rotation servos) and hexapod (6 legs, tripod gait). Scope: full (GUI, firmware, MakeCode).
- DONE: web-checked FS90R specs; wrote `design/styles.md` (comparison, wheg and hexapod design, unverified list); TASKS.md TS1-TS6 added.
- Verification: web facts only; nothing built or printed.
- NEXT: S2 gaits (hexapod tripod + wheg drive) with Python/JS parity tests.

### 2026-10-21 - Styles S2: hexapod tripod gait and wheg drive
- DONE: `firmware/src/gait.py` + `gui/js/gait.js`: `HexWalker` (tripod gait, 45% swing, three feet always down, no weight shift) and `WhegDrive` (left/right throttle, ramp, simulated hub angle, `wheg_pulse_us` pulse mapping with per-servo stop trim). Hexapod channel order: crab legs keep channels 0-7, middle legs ML 8-9, MR 10-11.
- Verification: script-checked. Firmware 33 tests pass (6 new); Python vs JS parity < 1e-9 for hexapod poses, wheg speeds and hub angles. Not run on hardware.
- NEXT: S3 model (style switch, hexapod body, wheg parts, style checks).

### 2026-10-21 - Styles S3: model supports crab, hexapod and windmill rover
- DONE: `gui/js/model.js` now takes `style` ('crab' | 'hex' | 'wheg'): hexapod = 6 legs with the middle motors beside the bays (body about 124 x 175 mm), tripod gait stability sampling, style-specific check wording; `gui/js/wheg.js` = windmill rover (floor + two motor walls, 4 identical hub-and-spoke legs with tip pads, closed shells, checks: wall thickness, spokes never touch, belly clearance, tip-over angle, climbing torque, spoke stress, pad size, speed, bed fit). Presets per style; `styleDefaults(style)`.
- DONE: fixed a foot-geometry exception found by the new random sweep (a too-small foot made the pocket cross the disc; geometry now stays valid and the red check explains).
- Tests: `gui/tests/test_model.py` (6) + `fuzz_model.js`: 300 random designs per style, all shells closed with positive volume, defaults of every style all green, hexapod/wheg behaviours (tripod margin > 12 mm, middle motors outside the bays, overlong spokes flagged, torque rises with a heavy battery, old saved designs load as crab). Exported 3MFs of each style pass `cad/validate_3mf.py`.
- Finding: the 135 g AA pack is too heavy for FS90R whegs (model says torque is short), so the rover defaults to the 4xAAA holder; hexapod default uses a shorter lower leg (45 mm) for the same reason. Modelled only, not measured.
- Verification: script-checked only.
- NEXT: S4 designer UI (style picker, previews, per-style sliders).

### 2026-10-21 - Styles S4: Walker Designer supports all three styles
- DONE: `gui/index.html` rewritten around a style picker; the panel, tabs, sliders, colour slots, parts page and finish page are built per style (kid wording: Windmill legs / Driving for the rover). Hexapod previews with the tripod gait, rover spins its four hubs and rests the body on the highest wheel, floor grid scrolls with the motion. Designs are saved per style (localStorage, try/catch) and old crab saves still load. Rebuilt `walker-designer.html` and `dist/artifact-fragment.html`; README updated.
- DONE: fixed two bugs found by the new tests: stale controller after a style switch (crash in the frame loop) and the plate picker showing in robot view.
- Tests: `gui/tests/test_gui.py` now 13 browser tests: each style loads all green, exports a zip whose 3MFs pass `cad/validate_3mf.py`, hexapod feet on the floor, wheg spin direction and ground contact, separate designs per style, no sideways scroll on a phone for each style.
- Verification: script-checked and desktop-browser-tested (headless Chromium). NOT tested on a tablet, in Bambu Studio, or on hardware. Artifact not republished yet.
- NEXT: republish the artifact, commit, then S5 firmware + MakeCode.

### 2026-10-21 - Styles S5a: firmware supports hexapod and windmill rover
- DONE: `firmware/src/drive.py` (new): `make_rig(config, driver)` builds the right controller for `config.STYLE` with one interface (command / stop / stand / relax / update / moving); `main.py` now runs through it, so the web remote works unchanged for all styles. `config.py`: `STYLE`, hexapod channels (crab 0-7 unchanged, middle legs 8-11) and signs, wheg channels 0-3, signs, per-servo stop trim in `calib.json`, `WHEG_MAX_THROTTLE` 0.4. `calibrate.py`: `wheg_stop / wheg_jog / wheg_test / wheg_flip`. `deploy.sh` copies `drive.py`.
- Tests: firmware suite 39 pass (6 new): hexapod channel map complete and crab wiring unchanged, hex rig walks within pulse limits, crab rig identical to the plain walker, wheg stop pulse = 1500 us + trim exactly, mirrored right side, throttle cap, ramp to stop, calibration save/load.
- Verification: script-checked only (fake driver). `main.py` compiles but cannot run off the board. Not run on real servos.
- NEXT: S5b MakeCode blocks for the new styles.

### 2026-10-21 - Styles S5b: MakeCode blocks for hexapod and windmill rover
- DONE: `makecode-kid/gait.ts` + `walker.ts`: new `Style` enum and block **start walker as** (crab / hexapod / windmill rover; plain **start walker** = crab as before), `Leg` enum gains middle-left / middle-right (channels 8-11), hexapod tripod gait, wheg drive with **top speed**, and wheel fix blocks (**stop-fix wheel by**, **flip spin direction of wheel**, **test spin wheel**). Blocks for a leg that the chosen robot does not have do nothing. `dist/custom.ts` rebuilt, README and new `lessons/level5-other-robots.md`.
- Tests: `makecode-kid/tests` now 13 pass (6 new): TS hexapod gait and wheg drive equal the Python versions to 1e-9 (angles with wrap), wheg pulse equals `wheg_pulse_us`, hexapod stand drives 12 channels, crab still 8, rover stand = stop pulse on channels 0-3 and the trim shifts it.
- Verification: script-checked only. NOT loaded into the MakeCode editor (block text such as the new enum labels is unverified) and not run on hardware.
- NEXT: S6 docs and PR.

### 2026-10-21 - Styles S6: docs, hermetic tests, PR
- DONE: `design/README.md` and `PLAN.md` point to `design/styles.md`. `gui/tests/test_model.py` no longer needs `three` installed (uses the vendored copy), so the whole suite runs from a clean checkout.
- Final run: firmware 39, gait parity + model + browser 25, MakeCode 13 - all pass (firmware 39 + 38 others).
- Verification overall: script-checked and desktop-browser-tested only. NOT done: open any style's 3MF in Bambu Studio (T1.1), print and fit-test a wheg or hex leg, run on real servos/micro:bit, MakeCode editor import, tablet check.
- Open for Jacob: TS6 (buy 4 FS90R, 4 more MG90S for the hexapod; trim each FS90R stop; print one windmill leg) plus the older TK6-TK9 and T1.1. PR #5 (log of PR #4) is still unmerged.
- NEXT: Jacob reviews the styles PR.

### 2026-10-21 - Step: merge PRs #6 and #5
- DONE: PR #6 (hexapod + windmill rover styles) merged to `main` at Jacob's request. PR #5 (log of PR #4) had conflicts in PROGRESS.md; resolved by keeping both sets of entries, then merged.
- NEXT: Jacob's items TS6, TK6-TK9, T1.1 in TASKS.md.

### 2026-11-11 - Image3D step 1: design spec
- DONE: `docs/superpowers/specs/2026-11-11-image3d-design.md` - design for a browser tool (`image3d/`): photo -> Hugging Face Space (Hunyuan3D / TRELLIS) -> edit (delete piece, size, orient, cut) -> STL. Web-checked: Meshy's API needs a paid plan; Hugging Face free accounts get a small daily GPU quota. Nothing built or tested yet.
- NEXT: Jacob reviews the spec; then implementation plan and build (TI2-TI6).
- BLOCKED: live Hugging Face generation cannot be tested from Claude's workspace (needs Jacob's token).

### 2026-11-11 - Image3D step 2: spec revised for phone use
- DONE: Jacob said the tool must work on a phone. Checked artifact rules: an artifact can host the editor and offer downloads but cannot call other sites. Spec now: one editor page delivered (a) as a claude.ai artifact (open GLB/OBJ/STL -> edit -> STL) and (b) from a small Render app that adds photo -> Hugging Face generation with the token kept server-side.
- NEXT: Jacob reviews the spec (TI2).

### 2026-11-11 - Image3D step 3: spec approved, implementation plan
- DONE: Jacob approved the spec (TI2) and confirmed Render free instance alongside mental_stength. Plan written: `docs/superpowers/plans/2026-11-11-image3d.md` (5 tasks: mesh maths, file readers, editor page + artifact, Render service, docs + PR).
- NEXT: Jacob glances at the plan and picks how to run it; then Task 1.

### 2026-11-11 - Image3D Task 1: mesh.js + stl.js (TI3)
- DONE: `image3d/js/mesh.js` (weld, split, bbox, volume, isClosed, scale, scaleToLongest, rotate90, layFlat, removePiece, keepLargest, dropSmall, cut) and `image3d/js/stl.js` (binary write, binary/ASCII read). Dependency-free UMD (`I3D.mesh`, `I3D.stl`). `cut` clips each shell, shares one vertex per cut edge with the cap, and ear-clips the cap with nested loops as holes; a cut that leaves a shell in separate pieces returns them as separate shells.
- Review fixes: cap ear-clipping now uses a distance tolerance (fine cap loops of thousands of vertices used to come out open), and `weld` accepts Float32Array/Float64Array soups.
- Tests: `image3d/tests/test_mesh.py` - 18 pass (~4 s) (Node snippets from pytest). Includes a skewed off-centre tube cut on all three axes (closed + volume conserved), which caught a T-junction bug in cap triangulation during development.
- Verification: script-checked only (Node under pytest). Not tried on a real generated mesh, in a browser or on a phone.
- NEXT: Task 2 (file readers: GLB/OBJ/STL into shells).
- BLOCKED: nothing.

### 2026-11-11 - Image3D Task 2: file readers (glb.js, obj.js, readany.js)
- DONE: `image3d/js/glb.js` (`I3D.glb.read`: GLB container, embedded BIN, float POSITION incl. strided, indices of any integer type or none, triangle mode only, node hierarchy with matrix or TRS, several meshes, glTF Y-up -> Z-up; throws `compressed` for Draco/meshopt and `not a GLB file` on bad magic), `image3d/js/obj.js` (`I3D.obj.read`: v/f, `v/vt/vn` forms, negative indices, fan triangulation) and `image3d/js/readany.js` (`I3D.readAny(name, bytes)` by case-insensitive extension; `module.exports = readAny` in Node; throws `unsupported file`). `image3d/tests/make_samples.py` (standard library only) writes the committed samples in `image3d/tests/samples/` (`two_cubes.glb/.obj/.stl`, `scaled.glb`, `box_yup.glb`).
- Tests: `image3d/tests/test_readers.py` - 8 pass; whole `image3d/tests` suite 26 pass (~4 s).
- Verification: script-checked only (Node under pytest, on generated samples). Not tried on a real Hunyuan3D/TRELLIS GLB, in a browser or on a phone.
- NEXT: Task 3 (editor page + artifact).
- BLOCKED: nothing.

### 2026-11-11 - Image3D Task 3: editor page, single-file build, browser tests (TI4)
- DONE: `image3d/index.html` (phone layout: 3D view on top ~45%, tools below; open GLB/OBJ/STL, piece list, tap-to-select in list or view, delete / keep largest / remove tiny bits, size, rotate, lay flat, cut with live plane preview, undo (20), closed / bed / piece-count checks, STL export via `claude.use('downloads')` then Blob link fallback, hidden `#gen-panel`, "How to get a model" note), `image3d/build.py` -> `image3d/image3d.html` (one self-contained file, committed), `image3d/README.md`, new sample `unit_box.glb`.
- Tests: `image3d/tests/test_page.py` - 8 pass (Playwright, 390 x 844, touch); whole `image3d/tests` suite 34 pass.
- Verification: desktop browser at phone size (Playwright); NOT on a real phone. The artifact downloads call (`saveViaClaude`) is a guess at the API and untested; the Blob fallback is what the tests exercise. Not yet published as an artifact (controller does that).
- NEXT: Task 4 (wire Generate button, server.py, render.yaml); publish the artifact.
- BLOCKED: nothing.
- 2026-11-11 Image3D Task 3 round-1 fixes: export saves `model.zip` via the artifact downloads API (declined = "Download cancelled", else plain `model.stl` link), cut plane only shown while cutting, size field shows current size, page scroll locked so the 3D view stays put. Browser tests 14 pass (Playwright at phone size, fake `window.claude`); NOT on a real phone and not against the real artifact API.

### 2026-11-11 - Image3D Task 4: Render service (TI5)
- DONE: `image3d/server.py` (FastAPI: `GET /` serves `image3d.html`, `GET /api/health`, `POST /api/generate` with check order 500 not configured, 401 passcode (constant-time), 400 not an image, 413 over 10 MB, 503 generator failure with the Space's reason; `generate_glb` via `gradio_client`, imported lazily, `token=` with `hf_token=` fallback; `GENERATOR` is swappable), `image3d/requirements.txt`, root `render.yaml` (free Python web service, `rootDir: image3d`, health check `/api/health`, `HF_TOKEN` / `IMAGE3D_PASSCODE` secrets), `image3d/DEPLOY.md` (phone steps + troubleshooting). Page: Generate button posts the photo, shows progress text and disables itself while running, shows the server's `detail` in the message line on errors, opens the result with `openBytes('generated.glb', ...)`; `image3d.html` rebuilt.
- Tests: `image3d/tests/test_server.py` (14, includes a fake `gradio_client`) and two new browser tests (uvicorn + fake generator); whole `image3d/tests` suite 56 pass.
- Verification: desktop-tested with a FAKE generator; live Hugging Face call and Render deploy NOT verified (endpoint auto-pick and result parsing are guesses about the Space's API until TI7).
- NEXT: controller publishes the editor as an artifact (the part of TI5 not done here); then TI6 / TI7 (Jacob).
- BLOCKED: nothing.
- 2026-11-11 Image3D Task 4 round-1 fixes: upload limit and passcode now enforced by an ASGI guard before the multipart body is read (500, then 401, then 413 on Content-Length or streamed bytes, also chunked); Hugging Face call now `submit(api_name='/shape_generation', image=handle_file(...))` against default Space `tencent/Hunyuan3D-2` (env `HF_SPACE`, `HF_API_NAME`, `HF_IMAGE_PARAM`; empty `HF_API_NAME` = auto-pick fallback); page downsizes the photo to a 1024 px JPEG before upload; docs/openapi disabled, error detail capped at 300 chars, 5-wrong-passcode throttle (429 for 10 min per IP). Tests: server + page 45 pass, FAKE generator and fake `gradio_client` only; live Hugging Face call and Render deploy still NOT verified.
- 2026-11-11 Image3D Task 4 round-2 fix: throttle key is now the LAST X-Forwarded-For entry (the one Render's proxy adds), a global backstop (more than 30 wrong passcodes from all clients in 10 minutes -> 429 for everyone, not reset by a correct passcode), and the per-key tables are swept and capped at 1000 keys. `DEPLOY.md` asks for a long passcode and explains "too many attempts". Tests: `test_server.py` 32 pass (injectable clock); NOT tried behind the real Render proxy.

### 2026-11-11 - Image3D Task 5: docs and full test run
- DONE: `image3d/README.md` updated (two ways to use it, files table, tests, verification status); root `README.md` Layout lists `image3d/`; "Current status" above mentions image3d. Full run `python -m pytest -q image3d/tests gui/tests && (cd firmware && python -m pytest -q)`: 101 passed (image3d + gui), 39 passed (firmware); nothing existing broken.
- Verification: mesh maths and readers script-checked; page tested in a desktop browser at phone size (Playwright), NOT on a real phone; server tested with a FAKE generator. NOT verified: the live Hugging Face call, the Render deploy, and the artifact's `model.zip` download inside the real Claude app.
- NEXT: Jacob does TI6 (try the artifact editor on the phone with a GLB from a Hugging Face Space page) and TI7 (Hugging Face token + Render deploy, one photo through). Controller pushes the branch and opens the PR to `main` (not merged).
- BLOCKED: nothing.

### 2026-11-11 - Image3D final fix wave (whole-branch review)
- DONE: keep the screen awake while generating (wake lock, re-requested on return, released in the end) with status "Generating... keep this screen open (about a minute or two)"; any `TypeError` from `fetch` shows the friendly "server may be waking up" message; `requirements.txt` pinned to installed majors; timed-out Space job is cancelled before the 503; 32-bit mesh indices chosen by vertex count (> 65535); Size section shows the whole model's X x Y x Z (`#model-size`); undo limit 20 up to 100,000 triangles, 5 above (`I3DApp.undoLimit()`); `DEPLOY.md` repo name `dodsoncode/automate_3d-cad-print`; `image3d/PROGRESS.md` Step 12 rewritten, Step 13 and known limits added; `image3d.html` rebuilt.
- Tests: `python -m pytest -q image3d/tests` 81 pass (5 new tests).
- Verification: desktop browser at phone size with a STUBBED wake lock, fake generator and fake `gradio_client`; NOT on a real phone, not the live Space or Render. The 32-bit index change is covered by reading only.
- NEXT: controller opens the PR to `main`; not merged until Jacob says so.
- BLOCKED: nothing.

### 2026-11-11 - Image3D: PR opened
- DONE: full run 106 passed (image3d + gui) and 39 passed (firmware); artifact republished from the final page; branch `image3d-tool` pushed; PR #7 opened to `main` (not merged).
- NEXT: Jacob - TI6 (try the artifact editor on the phone), TI7 (Hugging Face token + Render Blueprint, first real generation), then say when to merge. Render's Blueprint reads `render.yaml` from the branch it is pointed at, so either merge first or pick branch `image3d-tool`.
- BLOCKED: nothing for Claude. Still NOT verified: real phone, live Hugging Face call, Render deploy, zip download inside the Claude app.

### 2026-11-11 - Image3D: PR #7 merged
- DONE: Jacob asked for the merge; PR #7 merged to `main` (2bc9d21). `render.yaml` and `image3d/` are now on `main`, so the Render Blueprint can use branch `main`.
- NEXT: Jacob - TI7 (Hugging Face token + Render Blueprint per `image3d/DEPLOY.md`, first real generation) and TI6 (try the artifact editor on the phone).
- BLOCKED: nothing for Claude. Still NOT verified: real phone, live Hugging Face call, Render deploy.
### 2026-11-11 - Image3D: first live generation, two fixes from it
- DONE (live check): with Jacob's Hugging Face token, ran `server.generate_glb` against the real `tencent/Hunyuan3D-2` Space from Claude's workspace: valid GLB in about 10 s. This is the first real verification of the generation call (not through Render).
- FOUND 1: the default model was about 917,000 triangles (13.8 MB), too heavy for a phone. FIX: new setting `HF_EXTRA_JSON` (default `{"octree_resolution": 128}` for the default Space) -> about 115,000 triangles (3.2 MB); 96 gives about 55,000. Measured live.
- FOUND 2: cutting the real model left it not closed. Root cause: the hand-written cap triangulation (hole bridging + ear clipping) produced a wrong cap for the real cross-section (1496-point outline with a 1105-point cavity); small synthetic tests had not shown it. FIX: caps are now triangulated with earcut (vendored, `image3d/vendor/earcut.min.js`, ISC licence), with a stitch step so points on straight runs still join the walls. The failing cross-section is kept as `image3d/tests/fixtures/real_section.json` with a regression test; a bow-tie (pinch) cross-section test was added too.
- Checked: 114 cuts across x/y/z on the 917k model and 54 on the 113k model: all closed, volume conserved to 5e-12. Page opened the real model at phone size in 0.9 s and cut it watertight. `image3d/tests` + `gui/tests`: 113 passed.
- Verification level: script-checked and desktop-tested with REAL generated models. Still NOT verified: Render deploy, a real phone.
- NEXT: Jacob - deploy on Render (TI7) and try on the phone (TI6). Jacob's token appeared in the chat; suggest replacing it after setup.

### 2026-11-11 - Image3D: review of the cut fix, three more cases closed
- DONE: independent review of the earcut change found open caps in three situations not covered by the real models: boundary points on exactly straight runs when earcut's hole bridge lands on an existing edge (grid-aligned holes), cross-sections that pinch to a point (shared vertex between loops), and loop nesting probed at a shared vertex. FIX: coordinates handed to earcut are nudged by about 1e-9 of the size (same point, same nudge; real coordinates and ids unchanged); nesting is probed at a vertex no other loop shares. `image3d/tests/fuzz_cut.js` added (grid holes + four pinch shapes, random triangle order): before the fix 297 of 1000 failed, after it 0 of 9000 (three seeds). A broken `HF_EXTRA_JSON` now answers 500 "server not configured" before anything is uploaded.
- Verification level: script-checked (fuzz + regression tests) and re-checked on the two real generated models. Both real models came from one test picture and one Space, so other pictures are still untested. Render and a real phone: NOT verified.
- NEXT: PR for branch `image3d-real-mesh-fixes`; Jacob - TI7, TI6.

### 2026-11-11 - Image3D: PR #9 merged
- DONE: Jacob asked for the merge; PR #9 (cut caps on real models, lighter models from the Space) merged to `main` (c91f2fa). PR #8 was closed as superseded by #9.
- NEXT: Jacob - TI7 (Render Blueprint from branch `main` per `image3d/DEPLOY.md`), TI6 (try on the phone), then report the first real photo.
- BLOCKED: nothing for Claude. Still NOT verified: Render deploy, a real phone, pictures other than the one test picture.

### 2026-11-12 - Image3D: Render deploy and phone confirmed by Jacob; PR #10 merged
- DONE: PR #10 (merge-log entry) merged 2026-11-11. Jacob deployed the Render service and reports it "works well" on his phone (TI6, TI7) - this is the first confirmation on real hardware for the editor and for generation through Render. Details of what he tried are not recorded.
- Workflow change (Jacob, 2026-11-11): merge-log entries are folded into the next working PR instead of their own one-line PRs (now in `CLAUDE.md`).

### 2026-11-12 - Spike: slice for the P1S and send from the phone
- DONE: feasibility check, written up in `docs/2026-11-12-slice-send-feasibility.md`. Slicing is feasible: the OrcaSlicer engine (npm `orcaslicer-addon`, stock Bambu profiles) sliced a 105k-triangle test model for P1S 0.4 nozzle / Bambu PLA Basic / textured PEI into a valid `.gcode.3mf` in about 17 CPU-seconds and about 300 MB RAM. Sending: a cloud server cannot reach the printer; third-party start-print needs LAN-only + Developer Mode (loses Handy and cloud); FTPS upload to the SD card may work without that.
- Verification level: slicing script-checked in Claude's workspace only; the G-code has NOT been printed; nothing was tested on Render or on the printer; sending facts are web-checked only.
- NEXT: Jacob decides: build "Slice for P1S" into the Render app; try an FTPS app upload once at home; relay or not.
- BLOCKED: nothing.

### 2026-11-12 - P1S slicing: design approved, spec and plan written
- DONE: Jacob approved building "Slice for P1S" on the free Render instance, keeping Handy (no Developer Mode / relay), with Bambu PLA Basic and PLA Silk+ among the filaments. Spec: `docs/superpowers/specs/2026-11-12-p1s-slicing-design.md`. Plan: `docs/superpowers/plans/2026-11-12-p1s-slicing.md` (4 tasks).
- Extra spike findings (script-checked in Claude's workspace): the PLA Silk+ P1S profile slices (230 C); the engine does NOT centre an STL - an origin-centred model gave extruding moves at negative X (off the bed), fixed by moving the model to (128, 128) first; engine options must be passed as strings (a numeric `enable_support: 1` was silently ignored). The design therefore centres the model and checks every result (settings and bed bounds) before offering it.
- NEXT: Jacob reviews spec + plan; then build (subagent per task, reviewed).

### 2026-11-12 - P1S slicing: build started
- Substep: Jacob approved the spec and plan (06:20) and asked for a PROGRESS entry for every step and substep.
- Substep: controller pre-flight scan of the plan done; three small rulings recorded (error type signature, validation order, how the supports check compares values). No conflicts between tasks.
- NEXT: Task 1 (slicer core) with a builder, then independent review.

### 2026-11-12 - P1S slicing Task 1: slicer core
- Step 1 - install.sh written and run: `bash image3d/slicer/install.sh` printed `SLICER INSTALL: ok` in 6.4 s (second run 1.3 s, idempotent). Node was already on PATH, so the Node download branch is untested. Profiles fetched with a sparse clone at pinned OrcaSlicer commit 47a17ad; `package.json` (orcaslicer-addon 0.1.0 exactly), `package-lock.json` and `.gitignore` (node_modules, resources, .node) added. Script-checked in Claude's workspace.
- Step 2 - tests written: `image3d/tests/test_slicing.py` (prepare_stl, option tables, settings_for, check_gcode incl. parametrized mismatches, faked-engine run_slice cases, available, and two real-engine integration tests).
- Step 3 - red: `python -m pytest -q image3d/tests/test_slicing.py` -> collection error `ModuleNotFoundError: No module named 'slicing'` (nothing implemented yet).
- Step 4 - implemented: `image3d/slicing.py` (OPTIONS, available, prepare_stl, settings_for, check_gcode, run_slice, SliceError) and `image3d/slicer/slice_job.js`. One addition to the brief: the bed-bounds check also covers G2/G3 arc moves, because the real engine writes thousands of them (a 24-triangle test model gave 7.5k G3 and 0.8k G2 lines); `.orcaslicercli/` (scratch folder the engine creates in its working directory) added to `image3d/slicer/.gitignore`.
- Step 5 - green: `python -m pytest -q image3d/tests/test_slicing.py` -> 22 passed, 0 skipped (the two real-engine tests ran: about 1.7 s and 1.0 s on small models); whole `image3d/tests` -> 112 passed.
- Step 6 - this entry and the commit.
- DONE: slicer core. Verification level: script-checked; real OrcaSlicer engine run in Claude's workspace on small test models (PLA Silk+ / 0.16 mm / Textured PEI / tree supports, and the defaults), results passed `check_gcode`. NOT verified: the Node download branch of `install.sh` (node was already on PATH), Render, any real print, a real phone.
- NEXT: Task 2 (server job API on top of `slicing.run_slice`), then Task 3 (page panel), Task 4 (render.yaml wiring + docs).
- BLOCKED: nothing.
- Review round 1 - findings: (1) NaN vertex passed `prepare_stl`; (2) `check_gcode` kept no position, so extruding moves that inherit an off-bed X/Y, arcs that bulge off the bed, endpoint-less circles and G91 steps were accepted; (3) parsing too narrow (lowercase, `G01`, tab, no space, `E+1`, `X+300`, `Xnan` all slipped through); (4) E>0 assumed relative extrusion, wrong in M82 absolute mode. Minor: install.sh leaked a temp dir and could leave a half-extracted `.node`; engine scratch folder not cleaned.
- Review round 1 - red: 21 new tests failed on the old code (NaN, 7 spellings, inherited X/Y, arcs, G91, absolute E, scratch folder) before any fix.
- Fix round 1 - prepare_stl: every vertex tested for finiteness. check_gcode: rewritten as one `_check_moves` pass (X/Y state from the start of the file, G90/G91, M82/M83, G92, G28; bounds enforced after the first FEATURE; arcs checked over the part of the circle they sweep; unreadable move / unknown start / arc without I,J -> SliceError). install.sh: separate temp dirs cleaned by the trap, Node extracted into `slicer/.node.tmp.*` and renamed into place. run_slice removes `.orcaslicercli` after every slice.
- Fix round 1 - deviations: the real engine declares M83 only AFTER its purge line (the first FEATURE is a "Custom" start block), so "mode undeclared" cannot be an error; the extruder is treated as absolute until M82/M83, as the firmware does (an off-bed extruding move is still rejected). The conservative full-circle rule rejected the real output (large-radius arcs), so the exact swept-arc extent is used.
- Fix round 1 - green: test_slicing.py 58 passed, 0 skipped (both real-engine tests ran); whole image3d/tests 148 passed. Real 105k-triangle slice: 200k G-code lines checked in 0.88 s. Node download branch of install.sh now actually exercised (nodejs.org reachable; ran with node off PATH in a copy: ok in 10.6 s, no temp dir left). Verification level unchanged: script-checked, real engine in Claude's workspace, nothing printed.
- Review round 2 - findings: `_check_moves` still had wrong-accept paths: a zero-sweep arc (really a full circle) bounded by its endpoints only; stale absolute E after M83 moves; undeclared extruder mode read only one way; exponent/hex numbers (`X3e2` read as X3 + E2); `G92 X/Y` position resets; unrecognised motion commands (`G5`, `G53 G1`); no `; FEATURE:` line meant no bounds check at all.
- Review round 2 - red: 13 new tests failed on the round-1 code (all seven repro groups plus the message checks); an accept test built from 44 real engine lines was added at the same time.
- Fix round 2 - fail-closed rules: zero/near-zero sweep arc = full circle, radius = larger of start and end; one running E position in both modes; undeclared mode (or G91) counts a move as extruding if either reading says so; motion lines with `[0-9.][EX][0-9+-.]` are unreadable; after the first FEATURE `G92 X/Y` = "position reset not allowed", any other G command with X/Y/E (except G0-G4, G90-G92) and any line with more than one G/M command = "unsupported move"; no FEATURE line = "no print moves found". Before the first FEATURE the same cases only make the position unknown.
- Fix round 2 - real output: the 105k-triangle spike file `/tmp/orca/silk_c.gcode.3mf` (PLA Silk+, 0.16 mm, tree supports; 312,111 lines) still checks clean in 1.48 s. After its first FEATURE the G commands are G0 1, G1 160352, G2 29586, G3 48894, G92 4 (E only), G28 1, G29 1, G90 3, G21 1, G17 500; no line has two commands and none matches the exponent rule (0). Nothing real was rejected, no rule loosened.
- Fix round 2 - green: test_slicing.py 78 passed, 0 skipped (both real-engine tests ran); whole image3d/tests 168 passed. Verification level unchanged: script-checked, real engine in Claude's workspace, nothing printed.
- Review round 3 - findings: five more fail-closed gaps, none emitted by the real engine: G18/G19 plane changes (arc then bounded as XY), decimal G90.1/G91.1/G1.1/G92.1 read as their integer codes, lines not starting with a G/M command (`T0 G1 X300 E1`, modal `X300 E1`) skipped, repeated (`X300 X128`, `E1 E-1`) or glued (`E1G1 X100`) words, and coordinate offsets/systems (M206, M428, G10, G53, G54-G59).
- Review round 3 - red: 28 new tests failed on the round-2 code (the four accept cases already passed).
- Fix round 3 - rules: after the first FEATURE, G18/G19, decimal G0-G3/G90-G92 codes, M206/M428/G10/G53-G59 and any non-G/M line with an X, Y, E, I, J or G word are "unsupported move" (a bare `T0` passes, `G17` and `G29.2 S0` pass, `N10 G1 ...` still works); repeated X/Y/E/I/J/R words and G/M words glued to a number are "unreadable move". Before the first FEATURE the same lines make the position unknown and mark the modal state as changed, so the first extruding move afterwards is refused.
- Fix round 3 - real output: `/tmp/orca/silk_c.gcode.3mf` (312,111 lines) still checks clean in 1.61 s. After its first FEATURE: decimal G codes none; M codes carrying X/Y/E words: M1002 x2 (text), M17 x1 (neither is M206/M428); non-G/M lines: one `T255`; repeated words 0; glued words 0; G10/G18/G19/G53-G59 none. Nothing real rejected, nothing loosened.
- Fix round 3 - green: test_slicing.py 112 passed, 0 skipped (both real-engine tests ran); whole image3d/tests 202 passed.

### 2026-11-12 - P1S slicing Task 1: independent review closed
- Substep: first review found the model check accepted not-a-number coordinates and the G-code bed check could be fooled (inherited positions, arcs, odd spellings). Fix round 1 closed those.
- Substep: second review found six more wrong-accept paths in the rewritten check (zero-sweep arcs, extrusion-mode switches, exponent numbers, position resets, other motion commands, files with no print moves). Fix round 2 closed those.
- Substep: third review found five remaining gaps (plane changes, decimal G codes, lines without a command, repeated or glued words, coordinate offsets). Fix round 3 closed those; the final re-review confirmed all findings addressed with no new important issues.
- Result: `image3d/tests/test_slicing.py` 112 passed with both real-engine slices running; a real 312,111-line sliced file passes the check in about 1.6 s. Verification level: script-checked with the real engine in Claude's workspace; nothing printed, nothing run on Render.
- Left for later (minor): the glued-word rule is not applied to non-motion lines; only X/Y are bounds-checked (not Z).
- NEXT: Task 2 (server slice job).

### 2026-11-12 - P1S slicing Task 2: server slice job API
- Step 1 - tests written: 23 new tests in `image3d/tests/test_server.py` (a FakeSlicer that writes a small zip, can block on an Event or raise): options available/unavailable (+503, health still ok), passcode and throttle on POST/status/file, no `HF_TOKEN` needed, happy path with attachment headers, choice passed through, job survives later requests, 409 while running, failed job detail, any exception fails the job (detail capped at 300), stale running job reported failed, bad upload / unknown option rejected before queueing, 404 for unknown ids, expiry (1801 s, dir removed, swept on a new request), newer job drops the older file, oversized body rejected before read.
- Step 2 - red: with the old `server.py` restored, `python -m pytest -q image3d/tests/test_server.py` -> 1 failed, 85 errors (no `reset_jobs`, `SLICER`, `_worker`, `/api/slice` routes); the 40 old tests still passed.
- Step 3 - implemented: `image3d/server.py` - `SLICER` / `SLICER_AVAILABLE` attributes, `GenerateGuard` extended to POST `/api/slice` and every `/api/slice/<id>[/file]` (only `IMAGE3D_PASSCODE` required there; the body cap applies to the POST only; `/api/slice/options` stays public), job store (dict + lock, `secrets.token_urlsafe(8)` ids, `tempfile.mkdtemp` per job, 1800 s keep, swept on every slice request, newer finished job drops older ones, one background thread at a time, any exception marks the job failed, running past `slicing.TIMEOUT_S` + 60 s reports failed), routes options / start (503, 409, synchronous `prepare_stl` + `settings_for` errors, 202) / status / file.
- Step 4 - green: `python -m pytest -q image3d/tests/test_server.py` -> 63 passed (also with `-W error`, three runs); whole `image3d/tests` -> 226 passed.
- Step 5 - this entry and the commit.
- DONE: server slice job API. Verification level: script-checked, tested with a FAKE slicer; no real slice through the server yet (that is Task 4). NOT verified: Render, any real print, a real phone.
- NEXT: Task 3 (page panel), then Task 4 (render.yaml wiring, docs, first real slice through the server).
- BLOCKED: nothing.

### 2026-11-12 - P1S slicing Task 2: independent review closed
- Substep: review of the server slice job found no critical or important issues: passcode guard covers the slice routes with no bypass found, the one-slice-at-a-time rule is race-free, uploads are refused before the engine runs.
- Left for the final review to triage (minor): a rare overlap if a slice thread outlives its timeout, a failed thread start leaving a stuck job for 16 minutes, the result file being read into memory instead of streamed, engine error text that can include server paths.
- NEXT: Task 3 (the Slice for P1S panel on the page).

### 2026-11-12 - P1S slicing Task 3: Slice for P1S panel on the phone page
- Step 1 - tests written: 15 new browser tests in `image3d/tests/test_page.py` (390x844, touch). The server-mode fixture's script now has a FAKE slicer (sleeps 0.5 s, writes a tiny zip, records the received choice; a control file forces "unavailable" or a failure text; `SLICE_MAX_TRI` env gives a second fixture with a 10-triangle limit). Covers: hidden and no `api/slice` requests without the server, unavailable text, options listed + placement, no model / empty passcode, full flow with download and recorded choice, resume after reload, unknown saved job cleared silently, triangle limit hint, failure detail, wrong passcode, 422-list detail and TypeError wording, polling through a connection hiccup, result hidden after an edit (also while running), touch targets and single column.
- Step 2 - red: `python -m pytest -q image3d/tests/test_page.py` with the old `index.html` -> 15 failed, 23 passed.
- Step 3 - implemented: `image3d/index.html` - `#slice-panel` between Export and Generate (hidden until `api/health` succeeded and `api/slice/options` answered), four selects from the server's labels, `#btn-slice`, hint line (no model / too many triangles / not closed warning), 3 s polling with elapsed seconds, 20 minute give-up, hiccup text on network errors and 5xx, job id in `sessionStorage` and resumed on load (404 clears silently), result line + microSD note + `#btn-slice-download` (fetch -> Blob -> `<a download="model.gcode.3mf">`), result hidden on any edit/undo/open, a slice finishing after an edit is discarded with a message. Wake lock generalised (`wakeWanted()` = generating or slicing); network wording shared via `errText`. `image3d/image3d.html` rebuilt.
- Step 4 - green: `python -m pytest -q image3d/tests` -> 242 passed (three runs, no warnings).
- Step 5 - this entry and the commit.
- DONE: Slice for P1S panel. Verification level: desktop browser at phone size (Playwright) with a FAKE slicer; not on a real phone; no real slice through the page.
- NEXT: Task 4 (render.yaml wiring, docs, first real slice through the server and page).
- BLOCKED: nothing.


### 2026-11-12 - P1S slicing Task 3: independent review closed
- Substep: review of the page panel found no critical or important issues: the panel stays hidden and silent outside the Render version, the screen stays awake while slicing, a result is discarded if the model is edited or replaced mid-slice, and polling cannot double up.
- Left for the final review to triage (minor): changing a setting after a slice still shows the old file's Download button; a resumed job can be shown against a newly opened model; a wrong passcode during polling drops a finished job; no timeout on status requests.
- NEXT: Task 4 (deploy wiring, printing guide, one real slice through the real server).

### 2026-11-12 - P1S slicing Task 4: deploy wiring, docs, real end-to-end run
- Step 1 - real end-to-end run: new script `image3d/tests/e2e_slice.py` (not collected by pytest; 0 e2e items in `pytest --collect-only`). It starts uvicorn for `server:app` on a free port with `IMAGE3D_PASSCODE` set and no `HF_TOKEN`, checks `/api/slice/options` says available, POSTs a model with `pla_silk_plus` / `fine` / `textured_pei` / `tree`, polls until done, downloads the file, checks it is a zip with `Metadata/plate_1.gcode`, and re-runs `slicing.check_gcode` with the matching settings. Real OrcaSlicer engine, Claude's workspace (2 CPU cores, so NOT comparable with Render's 0.1 CPU).
  - (a) `tests/samples/two_cubes.stl` (24 triangles): done in 2.0 s wall (POST to done), 0.1 MB file, 16m 36s print time, 4.38 g, 125 layers; check passed.
  - (b) generated bumpy sphere, 124,500 triangles, about 71 x 72 x 72 mm: done in 15.6 s wall, 3.1 MB file, 1h 32m 18s print time, 52.52 g, 447 layers; check passed.
  - (c) `python image3d/tests/e2e_slice.py --direct` (`slicing.run_slice` on the same heavy model, measured with `resource.getrusage`): 14.0 s wall, peak RSS 368 MB for the node engine process, 98 MB for the Python process that called it (it holds the parsed model). Together that is about 466 MB, close to Render's 512 MB limit before the web server's own memory is counted (not measured on Render).
  - No bug found in Tasks 1-3 code.
- Step 2 - full test run: `python -m pytest -q image3d/tests gui/tests` -> 267 passed; `(cd firmware && python -m pytest -q)` -> 39 passed. The e2e script is not collected.
- Step 3 - docs and deploy wiring: `render.yaml` build command is now `pip install -r requirements.txt && bash slicer/install.sh` (nothing else changed); new `image3d/PRINTING.md`; `image3d/DEPLOY.md` section "Updating to get the slicer"; `image3d/README.md`, root `README.md`, `image3d/PROGRESS.md` (steps 17-21) and `TASKS.md` (SL4, SL5 added; SL3 stays open) updated; "Current status" refreshed.
- DONE: deploy wiring, docs, real end-to-end run. Verification level: slicer core script-checked with the real engine in Claude's workspace; server tested with a fake slicer plus the real end-to-end runs above; page tested in a desktop browser at phone size with a fake slicer. NOT verified: the slicer on Render (install step, memory, time), a real phone, any print. Concern: engine peak 368 MB plus the Python process (98 MB in the direct run) is close to Render's 512 MB for a 124,500-triangle model; a 150,000-triangle model is a bit more.
- NEXT: controller pushes and opens the PR. Jacob after merge: SL4 (redeploy, check `SLICER INSTALL: ok` and `/api/slice/options`), SL5 (first small watched print), optionally SL3.
- BLOCKED: nothing.
- Review round 1 - findings: (Important) the memory risk was only in PROGRESS/README, not in the docs a person follows (DEPLOY.md, PRINTING.md); (Important) TASKS.md ids TS1-TS5 in the slicing section collided with the finished walker tasks TS1-TS5; (Minor) PRINTING.md did not say the passcode is typed in the Generate box; (Minor) e2e script left server temp dirs and did not note `ru_maxrss` units; (Minor) README did not say the `--direct` figure is not the server's real footprint.
- Fix round 1 - docs: DEPLOY.md item 6 and a new PRINTING.md "If slicing fails" list give the measured engine memory (about 180 MB tiny; 254-263 MB 35 mm dome standard/no supports; 286 MB fine + tree; 400 MB 70 mm sphere 150k triangles fine + tree; all Claude's workspace, none on Render), say the 150,000 limit does not by itself keep memory safe, quote the page's exact strings ("Still working... (connection hiccup)", "The slice expired or was lost. Slice again.", "Enter the passcode in the Generate section first", checked in `index.html`), and list what to try; "Slicing failed" with supports off = overhangs / "floating regions" -> Tree supports or a flat base. PRINTING.md steps now tell the reader to type the passcode in the Generate box first. README `--direct` caveat added.
- Fix round 1 - ids: the slicing tasks are now SL1-SL5 in TASKS.md and in every slicing reference (PROGRESS.md, image3d/PROGRESS.md, image3d/README.md, the spec and the plan); walker TS1-TS6 untouched. (DEPLOY.md, PRINTING.md and the feasibility doc cited no task ids.)
- Fix round 1 - e2e script: server runs with `TMPDIR` in a `tempfile.TemporaryDirectory` that is cleaned in `finally`; docstring notes `ru_maxrss` is KB on Linux (bytes on macOS). Re-run: both models still OK (two_cubes 2.0 s), no new `/tmp/slice-*` dirs left; `python -m pytest -q image3d/tests` -> 242 passed.

### 2026-11-12 - P1S slicing Task 4: independent review closed; controller measurements
- Substep: review of the docs found the memory risk and the passcode step missing from the guides and the new task ids colliding with old walker tasks; all fixed (slicing tasks are now SL1-SL5) and confirmed by a re-review.
- Substep (controller, real engine in Claude's workspace): engine memory measured across model sizes and settings - about 180 MB tiny model; 254-263 MB for a 35 mm-tall dome at 56k-150k triangles, standard, no supports; 286 MB fine + tree; 400 MB for a 70 mm sphere, 150k triangles, fine + tree. The Python side peaked at 113 MB on a 150k-triangle upload (the STL preparation is memory-heavy).
- Substep (controller, real engine): with supports off, a model with overhanging parts makes the engine refuse ("floating regions ... enable support generation"); the job currently reports only the raw engine text.
- NEXT: whole-branch review, then one fix pass covering: a clear message for the overhang case, leaner STL handling, a memory guard so an oversized slice fails by itself instead of taking the server down, and the small page/server issues the task reviews deferred.

### 2026-11-12 - P1S slicing: final review fix wave
- A1 - PETG HF on the Cool Plate refused: `slicing.INCOMPATIBLE = {("petg_hf", "cool")}`; `settings_for` raises 400 'Bambu PETG HF cannot be printed on the Cool Plate - choose another plate'. All 12 filament x plate pairs run through the real engine (20 mm box): bed 35 (Cool Plate) / 55 (Textured PEI and High Temp) for the three PLAs, 70 for PETG HF on Textured PEI and High Temp, and 0 (no M190/M140 in the G-code) only for PETG HF + Cool Plate, so the table needs no other entry. `check_gcode` now also needs the chosen plate's bed temperature and its `_initial_layer` twin > 0 and an M190/M140 S>0 (last bed command) before the first FEATURE line. Tests: synthetic G-code per rule, real-engine refusal, real PLA Basic on Cool Plate passes (M190 S35). Script-checked with the real engine.
- A2 - filament_settings_id compared by equality; the output zip must hold exactly one .gcode entry and it must be Metadata/plate_1.gcode, else 500 'unexpected print data in the file'. Script-checked.
- A3 - excluded front-left corner (x<18, y<28): real engine output checked first - the start purge (X10.1-10.4, Y20-200, feature Custom) does enter the rectangle, so the rule applies only to extruding moves under a FEATURE other than Custom (start, end and arc extremes). Real box, shelf+tree and 200 mm box with brim all pass. The existing real-lines test now starts its body with '; FEATURE: Custom' as the real output does. Script-checked with the real engine.
- A4 - 'floating regions' is only in the engine's log text (not in the RESULT error line); two plain 400 messages (supports off / tree), raw tail logged at WARNING on image3d.slicing; real test with an octahedron standing on one corner. Script-checked with the real engine.
- B1 - prepare_stl memory-lean: chunked struct unpack (2000 records) for the finite check and bounding box, then the translated copy written with pack_into into one bytearray. Measured, 150,000-triangle STL: peak additional Python memory 15.3 MB (old code 81.7 MB; test bound 40 MB), CPU 0.145 s (old 0.317 s), no tracemalloc. `run_slice(stl, choice, workdir, timeout, prepared=info)`: with `prepared` (the info dict from prepare_stl) it does not parse again; it writes the STL to disk and drops its reference before starting the engine. Script-checked.
- B2 - engine run with Popen: stdout+stderr to workdir/engine.log (no pipes), os.nice(10) in preexec_fn (failure ignored), watchdog polling every POLL_S (1 s): time limit (500, time limit message) and memory limit (cgroup memory.current > memory.max - SLICE_MEM_MARGIN_MB, default 40; else engine RSS + own RSS > SLICE_MEM_LIMIT_MB, default 470) -> SIGKILL, wait, 413 with the out-of-memory message; output removed. Readers (read_cgroup_memory, read_rss, memory_exceeded) are module-level and tested with fakes (kill, timeout, normal exit, hang, start failure). RESULT is read from engine.log. DEPLOY.md lists both settings. Real engine runs pass (in this workspace there is no cgroup file, so the RSS fallback is what runs; the real-engine tests raise SLICE_MEM_LIMIT_MB because the pytest process is large). Script-checked with the real engine.
- B3 - server: new slice refused with 409 while the worker thread is alive; running jobs are failed only when their thread died unfinished ('the slice stopped unexpectedly') or, as last resort after 3600 s, 'the slice stopped responding; restart the service if this persists' (still blocks new slices and is not dropped while its thread lives); dir creation and Thread.start wrapped (500 'could not start the slice', dir and job removed); file route still reads the result into memory; options include incompatible [[petg_hf, cool]]; the POST hands the prepared bytes and info to the job. Fake-slicer tests; page-test fake slicer accepts the new keyword. Full run: 331 passed.
- C1 - install.sh proves the engine runs: uses the PATH node only if major >= 18 (else downloads the pinned Node; tested with a fake node 16 on the PATH in a scratch copy: downloaded, checksum OK, full install ok in 10 s); new step `smoke` slices `slicer/smoke_cube.stl` (12-triangle 10 mm cube, x/y 123-133, z 0-10) with slice_job.js and the default settings from `slicing.settings_for({})`, checks Metadata/plate_1.gcode, then writes `slicer/.install_ok` (orca_commit + node version); the file is removed at the start of every run. Commit in `slicer/ORCA_COMMIT`, read by install.sh and slicing.available() (which now also needs a matching .install_ok); a differing commit in the old marker (or in resources/profiles/.orca_commit) refetches the profiles. Every step's output goes to a log file; on failure the last 20 lines print before 'SLICER INSTALL: failed at <step>' (checked by removing smoke_cube.stl: 'failed at smoke', marker gone, available() False). Always exit 0; second run 0.9 s and ends ok; wrong-commit marker -> refetch (5 s) -> ok. `.install_ok` in slicer/.gitignore. Real run in this workspace; NOT run on Render.
- C2 - spec line corrected (Node >= 18, glibc >= 2.35, libstdc++ GLIBCXX_3.4.30, libcrypto.so.3, libfontconfig.so.1, libexpat, libz); DEPLOY.md explains that a missing library shows as a failed smoke step and 'Slicer unavailable on this server' while everything else keeps working.
- D1 - page: (a) a user change on any of the four slice selects hides the result and Download (filling the lists in code does not); (b) on resume, a model already open marks the resumed result stale (existing 'edited while slicing' message), no model open shows 'Result from your earlier slice: ...'; (c) 401/403 while polling (or an empty passcode, checked before every poll) keeps the saved job, stops polling and shows 'Enter the passcode in the Generate section, then reload to get your slice'; (d) status polls abort after 25 s (AbortController, covering headers and body) and count as a hiccup, the POST has no signal and is never retried; (e) the resume path has a .catch that ends the slicing state. Playwright tests with the fake slicer, one per behaviour (first run of the new tests was red: e.g. the size suffix; all green after).
- D2 - warning line #slice-float: with Supports Off, N pieces whose lowest z is more than 0.3 mm above the model's lowest z -> 'N piece(s) float above the bed - delete them or turn on Tree supports'; updates with every refresh and the supports select; Slice stays enabled. Tests: counts 2 and 1, 0.2 mm tolerance, tree clears it, deleting the piece clears it.
- D3 - the options response's `incompatible` list disables the plate option for the chosen filament; a selected plate moves to the first usable plate with '<Plate> is not available for Bambu <Filament>' in #slice-status; a server 400 for the pair still shows its detail. Tests for both.
- D4 - the result line ends with ' · 70 x 70 x 12.5 mm' from summary.size_mm (whole numbers without .0). Existing line test updated; fake-slicer size test added. image3d.html rebuilt with build.py. Verification: desktop browser (Playwright, phone size) with the fake slicer; no real phone, no Render.
- E1 - PRINTING.md: the two overhang messages replace the 'Slicing failed' quote; added the PETG HF / Cool Plate message, the out-of-memory message, the footprint-wider-than-about-240-mm note; the checks list now includes the bed temperature and bed-heat command and the excluded corner; the 'not checked' line says the actual bed/nozzle values and Z are not checked; the AMS-slot sentence is marked not verified on the printer.
- E2 - spec: finished jobs are kept up to 30 minutes (less if the free server sleeps after 15 minutes without requests, or restarts).
- E3 - image3d/README.md: licence row for the slicer engine (AGPL-3.0-only) and OrcaSlicer's Bambu profiles (AGPL-3.0): downloaded at build time, run unmodified in a separate process, nothing committed; revisit if the service is opened to others.
- E4 - root PROGRESS.md 'Current status' and image3d/PROGRESS.md 'Where it stands' reflect this wave with honest verification levels (real engine in Claude's workspace; fake slicer in a desktop browser; NOT verified: Render, a real phone, any print).
- F1 - watchdog never leaves the engine running: the wait loop is wrapped in `except BaseException: proc.kill(); proc.wait(); raise`; the OSError-to-'could not be started' mapping now covers the Popen call only. Tests: RuntimeError, MemoryError and OSError raised by a reader inside the loop -> child killed and reaped, the same exception re-raised (an OSError is not called 'could not be started'), output removed; a Popen start failure still gives 'could not be started'. Script-checked.
- F2 - the cgroup branch compares the working set: memory.current minus inactive_file from memory.stat (memory.current alone when memory.stat is unreadable or lacks the key). Fake-file tests: 500/512 MB with 150 MB inactive -> not killed; 500/512 with 5 MB inactive -> killed with the 413 message; no or garbled memory.stat -> falls back to memory.current (killed at 500/512); memory.max 'max' -> RSS fallback. Not run against Render's real cgroup.
- F3 - preexec_fn removed: the engine command is prefixed with `nice -n 10` when shutil.which('nice') finds it, else node runs directly (both branches tested with a patched which); real-engine tests still run and pass under nice. Full run: image3d/tests 332 passed; e2e_slice.py OK for both models.

### 2026-11-12 - P1S slicing: whole-branch review, fix wave re-review, controller verification
- Substep: the whole-branch review found one critical issue (PETG HF on the Cool Plate sliced with an unheated bed) and three important ones (install could report ok for an engine that cannot run; moves into the P1S's excluded corner accepted; a loose floating piece slices with supports off). All went into one fix wave (groups A-E above).
- Substep: the fix-wave re-review confirmed every item except two defects in the new memory guard (engine not killed if the watchdog itself errored; cgroup figure included reclaimable file cache). Controller ruling: patch both now (F1-F3 above) rather than ship them; this last patch is covered by tests and the runs below but was NOT independently reviewed.
- Substep (controller): full run after the patch - `image3d/tests` + `gui/tests` 357 passed (real-engine tests ran), `firmware` 39 passed; built page is current; no secrets or installed engine files in git.
- Substep (controller): the REAL page at phone size against the REAL server and REAL engine: opened a model, PETG HF greyed out the Cool Plate, sliced with PLA Silk+ (3.3 s for a 20 mm cube here), result line "Print time 13m 39s - 3.8 g - 100 layers - PLA Silk+, 0.20 mm Standard, Textured PEI - 20 x 20 x 20 mm", downloaded `model.gcode.3mf`, and the downloaded file passed `check_gcode` again.
- Verification level: real engine and real server in Claude's workspace; desktop browser at phone size. NOT verified: the slicer installing or running on Render (first deploy is the test), a real phone, any print, FTPS upload to the printer.
- NEXT: PR to `main`. Jacob: SL4 (merge, redeploy, check `/api/slice/options` says available), SL5 (first small watched print), SL3 (try the FTPS upload once).
