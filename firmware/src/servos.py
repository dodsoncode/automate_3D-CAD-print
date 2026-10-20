"""Joint-angle layer: named joint + angle relative to neutral -> servo pulse.

Driver needs set_us(channel, us) and off(channel) (PCA9685 or a test fake).
"""


class Servos:
    def __init__(self, driver, channels, signs, offsets, limits,
                 us_min=500, us_max=2500, range_deg=180):
        self.driver = driver
        self.channels = channels
        self.signs = signs
        self.offsets = offsets
        self.limits = limits
        self.us_min = us_min
        self.us_max = us_max
        self.range_deg = range_deg
        self.last = {}          # joint -> last relative angle commanded

    def angle_to_us(self, abs_deg):
        abs_deg = max(0.0, min(float(self.range_deg), abs_deg))
        return self.us_min + abs_deg / self.range_deg * (self.us_max - self.us_min)

    def to_abs(self, joint, rel_deg):
        kind = joint.split("_")[1]
        lo, hi = self.limits[kind]
        rel = max(lo, min(hi, rel_deg))
        return rel, 90.0 + self.signs[joint] * rel + self.offsets[joint]

    def set(self, joint, rel_deg):
        rel, abs_deg = self.to_abs(joint, rel_deg)
        self.driver.set_us(self.channels[joint], self.angle_to_us(abs_deg))
        self.last[joint] = rel
        return rel

    def apply(self, pose):
        for joint, deg in pose.items():
            self.set(joint, deg)

    def neutral(self):
        for joint in self.channels:
            self.set(joint, 0.0)

    def relax(self):
        for joint in self.channels:
            self.driver.off(self.channels[joint])
        self.last = {}
