# automate_3D-CAD-print

Pipeline: Python CAD -> Bambu Studio multi-material 3MF -> slice -> send to a Bambu P1S (AMS) over LAN.
Goal project: a simple multi-piece 3D-printed walking robot driven by a microcontroller.

## Layout
- `cad/make_cube_disk_3mf.py` - writes a 2-material 3MF (20 mm cube = filament 1, 10 mm x 0.5 mm disk on top = filament 2). No dependencies.
- `printer/bambu_send.py` - `status`, `send`, `slice` for a P1S over LAN (needs `pip install paho-mqtt`).
- `examples/cube_disk_2color.3mf` - generated example.

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
