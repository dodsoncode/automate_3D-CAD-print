# Tasks

Source of truth for open work. Phases are defined in [PLAN.md](PLAN.md); history lives in [PROGRESS.md](PROGRESS.md).
Owner: **J** = Jacob (needs the printer, parts or a decision), **C** = Claude, **J+C** = together.
Verification level when done: `script` (checked by code here) / `desktop` (tests pass) / `hardware` (confirmed on real device).

Legend: `[x]` done, `[ ]` open, `[~]` in progress, `[!]` blocked

## Phase 0 - Foundation
- [x] T0.1 Two-material cube+disk 3MF generator (`cad/make_cube_disk_3mf.py`) - verified: script
- [x] T0.2 P1S LAN script: status / send / slice (`printer/bambu_send.py`) - verified: offline smoke test
- [x] T0.3 Robot architecture, BOM, wiring, mechanical docs (`design/`)
- [x] T0.4 ESP32 firmware + 24 desktop tests (`firmware/`) - verified: desktop
- [x] T0.5 Repo workflow: branches + PRs merged to `main`
- [x] T0.6 PLAN.md / TASKS.md / PROGRESS.md (merged, PR #3)

## Phase 1 - Prove the pipeline on the real printer
- [ ] T1.1 (J) Open `examples/cube_disk_2color.3mf` in Bambu Studio; report whether the cube and disk show as two parts on filaments 1 and 2
- [ ] T1.2 (C) If T1.1 fails: fix the 3MF structure (match a Studio-exported reference 3MF); regenerate
- [ ] T1.3 (J) Slice and print the cube on the P1S + AMS (two real filaments); report print quality of the 0.5 mm disk
- [ ] T1.4 (J) On the P1S: note IP, access code, serial; turn on LAN Only Mode, then Developer Mode
- [ ] T1.5 (J+C) Run `bambu_send.py status` from a computer on the home network; confirm AMS contents are read
- [ ] T1.6 (J+C) Export a sliced `.gcode.3mf` from Studio and send it with `bambu_send.py send`; fix any FTP/MQTT issues found
- [ ] T1.7 (C) Record what worked on real hardware in README/PROGRESS; mark the verified level

## Phase 2 - Walker CAD (`cad/walker/`)
- [ ] T2.1 (J) Measure the servos you buy (body, tab spacing, shaft offset, horn) with calipers; send the numbers
- [ ] T2.2 (C) Choose CAD backend (build123d/CadQuery vs mesh booleans); install and smoke-test it here
- [ ] T2.3 (C) `params.py` with all servo/part dimensions and clearances
- [ ] T2.4 (C) Chassis tray: 4 hip pockets, electronics standoffs, battery bay, switch cut-out, wire pass-throughs
- [ ] T2.5 (C) Chassis lid with vents and fasteners (+ optional accent in filament 2)
- [ ] T2.6 (C) Coxa bracket (left and mirrored right): hip horn recess, knee servo pocket
- [ ] T2.7 (C) Femur link with horn recess and foot socket
- [ ] T2.8 (C) Foot pad (filament 2 or external TPU)
- [ ] T2.9 (C) Per-part export to 3MF with correct AMS filament per part, shared with the T0.1 writer
- [ ] T2.10 (C) Automated checks: closed meshes, volumes, bounding box fits bed, servo pocket clearance, no overlaps in the assembled pose
- [ ] T2.11 (C) Assembly preview (render of the assembled robot) and exploded view for the docs
- [ ] T2.12 (J) Print one coxa + femur + a servo; confirm fit; report adjustments (feeds back to T2.3)

## Phase 3 - Slice-and-send automation
- [ ] T3.1 (C) Decide slicing approach: Studio CLI with exported profiles vs a manually exported plate
- [ ] T3.2 (C) Single entry-point script/Makefile: generate -> slice -> upload -> start, with dry-run and confirmation
- [ ] T3.3 (C) Job monitoring: progress, error codes, completion notification
- [ ] T3.4 (C) Multi-plate packing for the full robot part set
- [ ] T3.5 (J+C) Run the full chain once end to end on a test part

## Phase 4 - Electronics bring-up
- [ ] T4.1 (J) Order parts from `design/components.md` (8-10 MG90S, ESP32, PCA9685, 2S LiPo, UBEC, switch, cap, resistors)
- [ ] T4.2 (J) Check UBEC output with a multimeter (5-6 V) before connecting anything
- [ ] T4.3 (J+C) Flash MicroPython; `i2c.scan()` finds 0x40
- [ ] T4.4 (J+C) One servo through `calibrate.py`; verify sign and pulse range
- [ ] T4.5 (J+C) All 8 servos on the bench, horns off; run the web remote (`http://192.168.4.1`)
- [ ] T4.6 (J+C) Verify battery voltage reading against a multimeter; confirm low-battery cutoff

## Phase 5 - Assembly, calibration, first steps
- [ ] T5.1 (J) Print the full part set
- [ ] T5.2 (J) Assemble with every servo at neutral (`center()`), fit horns and links
- [ ] T5.3 (J+C) Calibrate offsets/signs for all 8 joints, `save()` to `calib.json`
- [ ] T5.4 (J+C) Stand test, then walk with feet off the ground, then on the floor
- [ ] T5.5 (J+C) Walk forward / backward / turn; record behavior and fix issues
- [ ] T5.6 (C) Update firmware/design docs with whatever the real robot taught us

## Phase 6 - Tune and extend (optional)
- [ ] T6.1 Gait tuning (stride, lift, period, ramp)
- [ ] T6.2 TPU or rubber foot pads
- [ ] T6.3 IMU tilt feedback (MPU6050)
- [ ] T6.4 Battery runtime test
- [ ] T6.5 3-DOF legs (12 servos on the PCA9685)
- [ ] T6.6 Build guide with photos

## Open decisions
- D1: CAD backend for the walker (build123d vs CadQuery vs own mesh code) - decided in T2.2
- D2: Where `bambu_send.py` runs (Jacob's computer vs desktop-app link to the cloud workspace)
- D3: Servo choice confirmed (MG90S assumed)
- D4: Filament types and colors available for the AMS
