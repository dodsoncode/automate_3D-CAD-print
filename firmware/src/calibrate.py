"""Interactive servo calibration from the REPL.

    >>> from calibrate import *
    >>> center()                 # all joints to neutral - fit horns now
    >>> jog("FL_hip", 3)         # nudge trim +3 deg (repeat until straight)
    >>> test("FL_hip")           # moves +15 deg: hip should swing foot FORWARD,
                                 #                knee should LIFT the foot
    >>> flip("FL_hip")           # if it moved the wrong way
    >>> show(); save()           # writes calib.json
    >>> off()                    # relax all servos
"""
import time

from machine import I2C, Pin

import config
from pca9685 import PCA9685
from servos import Servos

_i2c = I2C(0, sda=Pin(config.I2C_SDA), scl=Pin(config.I2C_SCL), freq=config.I2C_FREQ)
print("I2C devices:", [hex(a) for a in _i2c.scan()])
_pca = PCA9685(_i2c, config.PCA_ADDR, config.SERVO_FREQ, config.PCA_OSC_HZ)
signs, offsets = config.load_calib()
s = Servos(_pca, config.CHANNELS, signs, offsets, config.LIMITS,
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


def show():
    for j in config.CHANNELS:
        print("%-8s ch%-2d sign %+d offset %+.1f" % (j, config.CHANNELS[j], signs[j], offsets[j]))


def save():
    config.save_calib(signs, offsets)
    print("saved", config.CALIB_FILE)


def off():
    s.relax()
