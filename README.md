# automate_3D-CAD-print

Pipeline: Python CAD -> Bambu Studio multi-material 3MF -> slice -> send to a Bambu P1S (AMS) over LAN.
Goal project: a simple multi-piece 3D-printed walking robot driven by a microcontroller.

## Project docs
- [PLAN.md](PLAN.md) - big-picture plan, phases, risks
- [TASKS.md](TASKS.md) - task list by phase (owner, verification level)
- [PROGRESS.md](PROGRESS.md) - step-by-step progress log, updated as work happens

## Layout
- `design/` - robot architecture, bill of materials, wiring/pin map/power budget, mechanical design.
- `firmware/` - MicroPython for the ESP32 (gait, servo driver, Wi-Fi remote, calibration) with desktop tests.
- `cad/make_cube_disk_3mf.py` - writes a 2-material 3MF (20 mm cube = filament 1, 10 mm x 0.5 mm disk on top = filament 2). No dependencies.
- `printer/bambu_send.py` - `status`, `send`, `slice` for a P1S over LAN (needs `pip install paho-mqtt`).
- `examples/cube_disk_2color.3mf` - generated example.
- `image3d/` - phone-friendly mesh editor (open GLB/OBJ/STL, delete pieces, resize, cut, export STL) plus a small Render service that turns a photo into a model via Hugging Face. It also has a "Slice for P1S" section that makes a `.gcode.3mf` for the P1S (OrcaSlicer engine, stock Bambu profiles; not yet run on Render, nothing printed yet). See [image3d/README.md](image3d/README.md) and [image3d/PRINTING.md](image3d/PRINTING.md).

## Printer setup (P1S)
1. Settings > WLAN: note IP and Access Code. Serial: Settings > Device.
2. Enable LAN Only Mode, then Developer Mode.
3. Copy `printer/bambu_config.example.json` to `printer/bambu_config.json` and fill it in (it is git-ignored).

## Workflow
```
python cad/make_cube_disk_3mf.py examples/cube_disk_2color.3mf
# open in Bambu Studio > Slice > File > Export > Export plate sliced file
python printer/bambu_send.py status
python printer/bambu_send.py send examples/cube_disk_2color.gcode.3mf --ams-map 0,1
```
