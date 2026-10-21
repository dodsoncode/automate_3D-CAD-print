# Walker Designer (GUI)

A visual, parametric designer for the walking robot, made so a kid can reshape it and watch it walk before printing.

- **Open it:** double-click `gui/walker-designer.html` (single file, works offline; fonts fall back to system fonts without internet). It is also published as a claude.ai artifact.
- **Pages:** Body, Legs, Walking, Colors, My parts, Finish. Traffic lights show whether the motors fit, the robot stays upright when a leg lifts, hips stay in range, motors are strong enough, and every part fits the printer bed.
- **Finish:** "Make my print files" gives a zip: one Bambu Studio 3MF per print plate (each part already assigned to an AMS slot), `walker_design.json`, `robot_settings.txt` (walking numbers for `firmware/src/config.py` or MakeCode) and a read-me. Open the 3MFs in Bambu Studio, or send them with `printer/bambu_send.py`.

## Files
| File | What it is |
|---|---|
| `index.html` | the page (source; loads `js/` and `vendor/`) |
| `js/geom.js` | 2D outline to closed 3D shell kit |
| `js/model.js` | parameters to parts, checks (fit, stability, torque, stress, bed) |
| `js/gait.js` | walking gait, same maths as `firmware/src/gait.py` |
| `js/export3mf.js` | 3MF writer (same layout as `cad/make_cube_disk_3mf.py`) |
| `build_artifact.py` | inlines everything into `walker-designer.html` and `dist/artifact-fragment.html` |
| `tests/` | gait parity (Python vs JS) and browser tests (Playwright) |

Rebuild after editing: `python gui/build_artifact.py`.

## Tests
`python -m pytest -q gui/tests` (browser tests need Playwright with Chromium). `python cad/validate_3mf.py plate_1.3mf` checks an exported file independently.

## Verification status
Script-checked and browser-tested on a desktop: shells are closed, 3MFs validate, the page loads without errors, feet touch the floor, +hip moves every foot forward. NOT verified: opening the 3MFs in Bambu Studio (T1.1), the servo, board and battery dimensions against real parts, and anything on hardware or on a tablet.
