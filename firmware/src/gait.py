"""Creep (wave) gait for a 4-leg, 2-DOF-per-leg walker. Pure math - no hardware.

Convention (all legs): hip + = foot toward FRONT, knee + = foot UP; 0 = neutral.

Each leg runs the same cycle shifted by 1/4 period, swing order RR -> FR -> RL -> FL.
  swing  (first 1/4 of a leg's cycle): lift, hip -1 -> +1, plant
  stance (other 3/4):                  hip +1 -> -1 slowly (pushes body forward)
So at most one foot is in the air at any time.

Steering mixes per-side sweep scale:  left = fwd - turn,  right = fwd + turn.
  fwd=+1 forward, fwd=-1 backward, turn=+1 spin left (CCW), turn=-1 spin right.
"""
import math

LEGS = ("FL", "FR", "RL", "RR")
SIDE = {"FL": "L", "RL": "L", "FR": "R", "RR": "R"}
SWING_SLOT = {"RR": 0, "FR": 1, "RL": 2, "FL": 3}
SWING_FRAC = 0.25


def leg_phase(cycle_t, leg):
    """Phase of one leg in [0, 1) given the body cycle phase."""
    return (cycle_t - SWING_SLOT[leg] * SWING_FRAC) % 1.0


def leg_profile(phase):
    """(hip_fraction in [-1, 1], lift_fraction in [0, 1]) for a leg phase."""
    if phase < SWING_FRAC:
        s = phase / SWING_FRAC
        return -math.cos(math.pi * s), math.sin(math.pi * s)
    s = (phase - SWING_FRAC) / (1.0 - SWING_FRAC)
    return 1.0 - 2.0 * s, 0.0


def _clamp(x, lo=-1.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def _approach(cur, target, step):
    if cur < target:
        return min(target, cur + step)
    return max(target, cur - step)


class Walker:
    def __init__(self, stride_deg=20.0, lift_deg=25.0, period_s=1.6, ramp_per_s=2.0):
        self.stride = stride_deg
        self.lift = lift_deg
        self.period = period_s
        self.ramp = ramp_per_s       # how fast sweep scale changes (1/s)
        self.cycle = 0.0
        self.target = {"L": 0.0, "R": 0.0}
        self.scale = {"L": 0.0, "R": 0.0}
        self.lift_scale = 0.0

    # -- commands --
    def command(self, fwd=0.0, turn=0.0):
        self.target["L"] = _clamp(fwd - turn)
        self.target["R"] = _clamp(fwd + turn)

    def stop(self):
        self.command(0.0, 0.0)

    @property
    def moving(self):
        return any(abs(v) > 1e-3 for v in self.scale.values()) or self.lift_scale > 1e-3

    # -- update --
    def update(self, dt):
        """Advance by dt seconds, return pose {"FL_hip": deg, ...}."""
        step = self.ramp * dt
        for side in ("L", "R"):
            self.scale[side] = _approach(self.scale[side], self.target[side], step)
        want_lift = 1.0 if any(abs(v) > 1e-3 for v in self.target.values()) else 0.0
        self.lift_scale = _approach(self.lift_scale, want_lift, step)

        if self.moving:
            self.cycle = (self.cycle + dt / self.period) % 1.0
        return self.pose()

    def pose(self):
        out = {}
        for leg in LEGS:
            hip_f, lift_f = leg_profile(leg_phase(self.cycle, leg))
            out[leg + "_hip"] = self.stride * self.scale[SIDE[leg]] * hip_f
            out[leg + "_knee"] = self.lift * self.lift_scale * lift_f
        return out


def stand_pose(height_deg=0.0):
    """All legs at neutral; height_deg < 0 lowers the body (knees down = feet down)."""
    out = {}
    for leg in LEGS:
        out[leg + "_hip"] = 0.0
        out[leg + "_knee"] = -height_deg
    return out
