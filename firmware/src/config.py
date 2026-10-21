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

# ---- Robot style: "crab" (4 legs, creep gait), "hex" (6 legs, tripod gait) or "wheg" (4 spinning windmill legs) ----
# The Walker Designer shows the line to paste here on its Finish page.
STYLE = "crab"

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

# Hexapod: the crab channels stay put, the two middle legs use 8-11 (a second 16-channel board is NOT needed)
HEX_LEGS = ("FL", "FR", "RL", "RR", "ML", "MR")
HEX_CHANNELS = dict(CHANNELS, ML_hip=8, ML_knee=9, MR_hip=10, MR_knee=11)
HEX_SIGNS = dict(SIGNS, ML_hip=-1, ML_knee=1, MR_hip=1, MR_knee=-1)

# Windmill rover: one continuous-rotation servo (FS90R) per wheel leg.
# WHEG_SIGNS: +1 or -1 so that a positive speed rolls the robot FORWARD for every wheel. The left and right
# servos face opposite ways, so the right side starts at -1. Confirm with calibrate.py wheg_test().
WHEG_LEGS = LEGS
WHEG_CHANNELS = {"FL": 0, "FR": 1, "RL": 2, "RR": 3}
WHEG_SIGNS = {"FL": 1, "FR": -1, "RL": 1, "RR": -1}
WHEG_TRIM_US = {leg: 0.0 for leg in LEGS}     # per-servo stop point; set by calibrate.py (calib.json "wheg_trim_us")
WHEG_STOP_US = 1500
WHEG_SPAN_US = 500        # full speed = stop +- this many microseconds
WHEG_MAX_THROTTLE = 0.4   # start gentle: the rover can flip over bumps at full speed
WHEG_RPM_FULL = 110.0     # FS90R no-load speed at 4.8 V (only used for the simulated hub angle)

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


def style_tables(style=None):
    """Return (channels, signs, offsets) for a legged style ("crab" or "hex")."""
    if (style or STYLE) == "hex":
        return dict(HEX_CHANNELS), dict(HEX_SIGNS), {name: 0.0 for name in HEX_CHANNELS}
    return dict(CHANNELS), dict(SIGNS), dict(OFFSETS)


def load_wheg_signs(path=CALIB_FILE):
    signs = dict(WHEG_SIGNS)
    try:
        with open(path) as f:
            signs.update(json.load(f).get("wheg_signs", {}))
    except (OSError, ValueError):
        pass
    return signs


def load_wheg_trim(path=CALIB_FILE):
    trim = dict(WHEG_TRIM_US)
    try:
        with open(path) as f:
            trim.update(json.load(f).get("wheg_trim_us", {}))
    except (OSError, ValueError):
        pass
    return trim


def load_calib(path=CALIB_FILE, style=None):
    """Return (signs, offsets) with any saved calibration applied."""
    _, signs, offsets = style_tables(style)
    try:
        with open(path) as f:
            data = json.load(f)
        signs.update(data.get("signs", {}))
        offsets.update(data.get("offsets", {}))
    except (OSError, ValueError):
        pass
    return signs, offsets


def save_calib(signs, offsets, path=CALIB_FILE, wheg_signs=None, wheg_trim_us=None):
    data = {"signs": signs, "offsets": offsets}
    if wheg_signs is not None:
        data["wheg_signs"] = wheg_signs
    if wheg_trim_us is not None:
        data["wheg_trim_us"] = wheg_trim_us
    with open(path, "w") as f:
        json.dump(data, f)
