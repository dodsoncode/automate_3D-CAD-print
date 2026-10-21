"""Interactive servo calibration from the REPL.

    >>> from calibrate import *
    >>> center()                 # all joints to neutral - fit horns now
    >>> jog("FL_hip", 3)         # nudge trim +3 deg (repeat until straight)
    >>> test("FL_hip")           # moves +15 deg: hip should swing foot FORWARD,
                                 #                knee should LIFT the foot
    >>> flip("FL_hip")           # if it moved the wrong way
    >>> show(); save()           # writes calib.json
    >>> off()                    # relax all servos

Windmill rover (config.STYLE = "wheg"):
    >>> wheg_stop()              # send the stop pulse; turn each servo's trim screw until the horn is still
    >>> wheg_jog("FL", 8)        # or trim in software (microseconds) if the screw is out of range
    >>> wheg_test("FL")          # spins forward briefly: the hub must turn so the robot would roll FORWARD
    >>> wheg_flip("FL")          # if it turned the wrong way
    >>> show(); save()
"""
import time

from machine import I2C, Pin

import config
from pca9685 import PCA9685
from servos import Servos

_i2c = I2C(0, sda=Pin(config.I2C_SDA), scl=Pin(config.I2C_SCL), freq=config.I2C_FREQ)
print("I2C devices:", [hex(a) for a in _i2c.scan()])
_pca = PCA9685(_i2c, config.PCA_ADDR, config.SERVO_FREQ, config.PCA_OSC_HZ)
CHANNELS, _, _ = config.style_tables()
signs, offsets = config.load_calib()
wsigns = config.load_wheg_signs()
wtrim = config.load_wheg_trim()
s = Servos(_pca, CHANNELS, signs, offsets, config.LIMITS,
           config.SERVO_US_MIN, config.SERVO_US_MAX, config.SERVO_RANGE_DEG)


def center():
    s.neutral()


def jog(joint, deg):
    offsets[joint] = offsets[joint] + deg
    s.set(joint, 0.0)
    print(joint, "offset =", offsets[joint])


def test(joint, deg=15.0):
    s.set(joint, deg)
    time.sleep(0.8)
    s.set(joint, 0.0)


def flip(joint):
    signs[joint] = -signs[joint]
    print(joint, "sign =", signs[joint])


def sweep(joint, lo=-30, hi=30, step=2):
    for d in list(range(lo, hi + 1, step)) + list(range(hi, lo - 1, -step)):
        s.set(joint, d)
        time.sleep(0.03)
    s.set(joint, 0)


def _wpulse(leg, speed):
    import gait
    _pca.set_us(config.WHEG_CHANNELS[leg], gait.wheg_pulse_us(speed, wsigns[leg], wtrim[leg], config.WHEG_SPAN_US, config.WHEG_STOP_US))


def wheg_stop():
    for leg in config.WHEG_CHANNELS:
        _wpulse(leg, 0.0)


def wheg_jog(leg, us):
    wtrim[leg] = wtrim[leg] + us
    _wpulse(leg, 0.0)
    print(leg, "trim =", wtrim[leg], "us")


def wheg_test(leg, speed=0.3, secs=1.0):
    _wpulse(leg, speed)
    time.sleep(secs)
    _wpulse(leg, 0.0)


def wheg_flip(leg):
    wsigns[leg] = -wsigns[leg]
    print(leg, "wheg sign =", wsigns[leg])


def show():
    if config.STYLE == "wheg":
        for leg, ch in config.WHEG_CHANNELS.items():
            print("%-3s ch%-2d sign %+d trim %+.1f us" % (leg, ch, wsigns[leg], wtrim[leg]))
        return
    for j in CHANNELS:
        print("%-8s ch%-2d sign %+d offset %+.1f" % (j, CHANNELS[j], signs[j], offsets[j]))


def save():
    config.save_calib(signs, offsets, wheg_signs=wsigns, wheg_trim_us=wtrim)
    print("saved", config.CALIB_FILE)


def off():
    s.relax()
    for ch in config.WHEG_CHANNELS.values():
        _pca.off(ch)
