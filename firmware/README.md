# Firmware (ESP32 + MicroPython)

Runs the 4-legged walker described in [../design/](../design/README.md): ESP32 -> I2C -> PCA9685 -> 8 servos.

```
src/config.py     pins, channel map, limits, gait defaults, Wi-Fi AP, battery thresholds
src/pca9685.py    I2C PWM driver
src/servos.py     joint angle (relative to neutral) -> pulse width, sign/offset/limits
src/gait.py       creep gait, pure math (no hardware imports)
src/webctl.py     Wi-Fi access point + phone web remote
src/main.py       boots on power-up: Wi-Fi AP, web remote, 50 Hz gait loop, battery cutoff
src/calibrate.py  REPL helper to center, trim, reverse and save servo settings
tests/            desktop pytest suite (fake PCA9685; no hardware needed)
deploy.sh         copy src/ to the board with mpremote
```

## One-time setup

```bash
pip install mpremote esptool pytest
# 1. Flash MicroPython (download the ESP32_GENERIC .bin from micropython.org/download/ESP32_GENERIC)
esptool.py --chip esp32 --port /dev/ttyUSB0 erase_flash
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash -z 0x1000 ESP32_GENERIC-<version>.bin
# 2. Copy the code
./deploy.sh
```

Port names: Linux `/dev/ttyUSB0`, macOS `/dev/cu.usbserial-*`, Windows `COM3`. Set `PORT=...` for deploy.sh if autodetect fails.
Needs MicroPython v1.20 or newer (uses `asyncio`, `ADC.read_uv`).

## Calibrate (do this before attaching the horns)

```bash
mpremote connect $PORT repl
```
```python
>>> from calibrate import *
>>> center()               # every servo to 90 deg. Fit horns/links in the neutral pose now.
>>> test("FL_hip")         # hip: foot should swing FORWARD; knee: foot should LIFT
>>> flip("FL_hip")         # reverse if it went the wrong way
>>> jog("FL_hip", 3)       # trim until the leg is straight
>>> save()                 # writes calib.json to the board
```

Repeat for all 8 joints, run `save()`, then reset the board (button or `Ctrl-D`).

## Run

After reset, `main.py` starts automatically. Join the Wi-Fi network `walker-robot`
(password in `config.py`, change it), open **http://192.168.4.1**, and use the buttons.
The LED blinks slowly while idle, quickly while walking, and very fast on low battery.

**First powered test:** put the robot on a block so the feet hang free, and make sure the
servos get power from the UBEC, not USB. Check each leg moves the right way before letting it stand.

## Desktop tests

```bash
cd firmware && python -m pytest -q
```

These cover the gait (one foot in the air at a time, symmetry, turning, smooth ramps), the
servo mapping (limits, signs, offsets, pulse widths) and the PCA9685 register writes.
They cannot check anything mechanical: motion direction, servo trim and balance
must be checked on the real robot.

## Tuning

| Symptom | Try |
|---|---|
| Robot tips over during a step | Lower `GAIT_LIFT_DEG`, or move the battery toward the middle |
| Feet slip, little progress | Rubber/TPU foot pads, bigger `GAIT_STRIDE_DEG` |
| Servos jitter or brown out | Check the UBEC rating, add the 1000 µF cap, confirm the common ground |
| All neutrals off by the same amount | Adjust `PCA_OSC_HZ` (boards vary +-5%) |
| Turning is too weak/strong | Scale `fwd_left`/`fwd_right` in `Robot.MOVES` |
