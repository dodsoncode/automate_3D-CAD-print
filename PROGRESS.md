# Progress log

Newest entries at the bottom. One entry per step, written as each step finishes (not batched at the end).
Status key: DONE / IN PROGRESS / BLOCKED / NEXT. Task IDs refer to [TASKS.md](TASKS.md).

## Current status

_(updated at the end of every step)_

- **Phase:** 0 complete; Phase 1 (prove the pipeline on the real printer) is next and needs Jacob
- **Now:** waiting on Jacob for Phase 1 (T1.1); Claude can start Phase 2 CAD. Side tool `image3d/` (photo -> STL editor): spec written, awaiting Jacob's review
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
