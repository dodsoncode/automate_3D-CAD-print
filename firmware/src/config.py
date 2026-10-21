"""Robot configuration. Hardware wiring lives here; per-servo trim lives in calib.json.

See design/wiring.md for the channel map and design/mechanical.md for joint limits.
"""
import json

# ---- I2C / PCA9685 ----
I2C_SDA = 21
I2C_SCL = 22
I2C_FREQ = 400_000
PCA_ADDR = 0x40
SERVO_FREQ = 50          # Hz
# PCA9685 internal oscillator is nominally 25 MHz but varies ~+-5% per board.
# If neutral is off for *every* servo by the same amount, tune this.
PCA_OSC_HZ = 25_000_000

# ---- Servos (MG90S) ----
SERVO_US_MIN = 500       # pulse at 0 deg
SERVO_US_MAX = 2500      # pulse at 180 deg
SERVO_RANGE_DEG = 180

LEGS = ("FL", "FR", "RL", "RR")
JOINTS = ("hip", "knee")

# PCA9685 channel for each joint
CHANNELS = {
    "FL_hip": 0, "FL_knee": 1,
    "FR_hip": 2, "FR_knee": 3,
    "RL_hip": 4, "RL_knee": 5,
    "RR_hip": 6, "RR_knee": 7,
}

# Direction: +1 or -1 so that, for EVERY leg,
#   hip  + = foot swings toward the FRONT of the robot
#   knee + = foot LIFTS
# Left/right servos are mirror-mounted, so these defaults are a starting guess.
# Confirm each with calibrate.py and save; calib.json overrides these.
SIGNS = {
    "FL_hip": -1, "FL_knee": 1,
    "FR_hip": 1, "FR_knee": -1,
    "RL_hip": -1, "RL_knee": 1,
    "RR_hip": 1, "RR_knee": -1,
}

# Trim (deg) added to 90 deg neutral. Set by calibrate.py; calib.json overrides.
OFFSETS = {name: 0.0 for name in CHANNELS}

# Joint limits relative to neutral (deg) - protect printed parts and wiring
LIMITS = {"hip": (-45.0, 45.0), "knee": (-30.0, 60.0)}

# ---- Gait defaults ----
GAIT_STRIDE_DEG = 20.0   # hip sweep amplitude (+-)
GAIT_LIFT_DEG = 25.0     # knee lift during swing
GAIT_PERIOD_S = 1.6      # one full 4-leg cycle
GAIT_SWAY_DEG = 14.0     # weight shift: stance hips nudge so the body leans over the 3 standing feet
GAIT_SPLAY_DEG = 50.0    # leg heading from the body axis; must match the printed design (legSplay)
LOOP_HZ = 50

# ---- Battery (2S LiPo through 100k/47k divider on GPIO34) ----
BATT_PIN = 34
BATT_DIVIDER = (100 + 47) / 47
BATT_WARN_V = 7.0
BATT_CUTOFF_V = 6.6

# ---- Wi-Fi access point ----
WIFI_SSID = "walker-robot"
WIFI_PASSWORD = "walkwalk123"   # >= 8 chars; change it
HTTP_PORT = 80

STATUS_LED = 2

CALIB_FILE = "calib.json"


def load_calib(path=CALIB_FILE):
    """Return (signs, offsets) with any saved calibration applied."""
    signs = dict(SIGNS)
    offsets = dict(OFFSETS)
    try:
        with open(path) as f:
            data = json.load(f)
        signs.update(data.get("signs", {}))
        offsets.update(data.get("offsets", {}))
    except (OSError, ValueError):
        pass
    return signs, offsets


def save_calib(signs, offsets, path=CALIB_FILE):
    with open(path, "w") as f:
        json.dump({"signs": signs, "offsets": offsets}, f)
