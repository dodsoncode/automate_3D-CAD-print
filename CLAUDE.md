# Instructions for Claude working in this repo

Project: Python CAD -> Bambu Studio multi-material 3MF -> Bambu P1S (AMS) over LAN, proven on a 3D-printed
ESP32 walking robot. Read `PLAN.md` (big picture), `TASKS.md` (open work) and `PROGRESS.md` (history) first.

## Progress file rule (standing request from Jacob)

- Update `PROGRESS.md` **after every step**, not once at the end. When one request has several steps, add a log
  entry (and refresh "Current status") as each step finishes, and commit it.
- Each entry: what was DONE, what is NEXT, and anything BLOCKED. State the verification level honestly:
  script-checked, desktop-tested, or confirmed on real hardware.
- Keep `TASKS.md` checkboxes in sync with what was actually finished. Change `PLAN.md` only if the plan changes.

## Workflow

- Work on a branch, open a PR to `main`; merge only when Jacob asks.
- Do not open a PR just to log a merge: put the merge's `PROGRESS.md` entry in the next working PR.
- Python 3; the 3MF writer has no dependencies. Firmware tests: `cd firmware && python -m pytest -q`.
- Never commit `printer/bambu_config.json` (printer access code) or `firmware/src/calib.json`.
