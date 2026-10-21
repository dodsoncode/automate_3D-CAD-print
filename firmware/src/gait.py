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
SWING_FRAC = 0.20          # a leg is in the air for 20% of the cycle; all 4 are down for the other 5%
SLOT_SPACING = 0.25        # legs start their swings a quarter cycle apart

# Weight shift ("sway"). A 4-legged walker with symmetric feet cannot stand on 3 legs unless its weight moves over
# them, so while leg k swings the other legs nudge their hips and the body slides away from the lifted corner.
# Same maths as gui/js/gait.js (gui/tests/test_gait_parity.py checks they agree).
CORNER = {"FL": (1, 1), "FR": (1, -1), "RL": (-1, 1), "RR": (-1, -1)}   # x forward, y left
YAW_SIGN = {"FL": -1, "FR": 1, "RL": -1, "RR": 1}                        # hip + = foot toward the front
SWAY_RAMP_IN = 0.08       # weight starts moving this much of a cycle BEFORE a leg lifts
SWAY_RAMP_OUT = 0.05      # ...and eases back this much after it lands
_SQRT_HALF = math.sqrt(0.5)


def _heading(leg, splay_deg):
    return {"FL": splay_deg, "FR": -splay_deg, "RL": 180 - splay_deg, "RR": -(180 - splay_deg)}[leg]


def foot_tangent(leg, splay_deg):
    """Direction the foot moves in the body plane for a + hip command."""
    h = math.radians(_heading(leg, splay_deg))
    return (-YAW_SIGN[leg] * math.sin(h), YAW_SIGN[leg] * math.cos(h))


def sway_envelope(phase):
    if phase < SWING_FRAC:
        return 1.0
    if phase < SWING_FRAC + SWAY_RAMP_OUT:
        return 0.5 * (1 + math.cos(math.pi * (phase - SWING_FRAC) / SWAY_RAMP_OUT))
    if phase > 1.0 - SWAY_RAMP_IN:
        return 0.5 * (1 - math.cos(math.pi * (phase - (1.0 - SWAY_RAMP_IN)) / SWAY_RAMP_IN))
    return 0.0


def sway_offset(leg, cycle_t, sway_deg, splay_deg):
    total = 0.0
    tg = foot_tangent(leg, splay_deg)
    for k in LEGS:
        if k == leg:
            continue
        dot = (tg[0] * CORNER[k][0] + tg[1] * CORNER[k][1]) * _SQRT_HALF
        total += sway_deg * dot * sway_envelope(leg_phase(cycle_t, k))
    return total


def leg_phase(cycle_t, leg):
    """Phase of one leg in [0, 1) given the body cycle phase."""
    return (cycle_t - SWING_SLOT[leg] * SLOT_SPACING) % 1.0


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
    def __init__(self, stride_deg=20.0, lift_deg=25.0, period_s=1.6, ramp_per_s=2.0, sway_deg=0.0, splay_deg=50.0):
        self.stride = stride_deg
        self.lift = lift_deg
        self.period = period_s
        self.ramp = ramp_per_s       # how fast sweep scale changes (1/s)
        self.sway = sway_deg         # weight-shift amplitude (deg of hip)
        self.splay = splay_deg       # leg heading from the body axis (deg), matches the design
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
            if self.sway:
                out[leg + "_hip"] += self.lift_scale * sway_offset(leg, self.cycle, self.sway, self.splay)
            out[leg + "_knee"] = self.lift * self.lift_scale * lift_f
        return out


def stand_pose(height_deg=0.0):
    """All legs at neutral; height_deg < 0 lowers the body (knees down = feet down)."""
    out = {}
    for leg in LEGS:
        out[leg + "_hip"] = 0.0
        out[leg + "_knee"] = -height_deg
    return out


# ============================================================ hexapod: tripod gait
HEX_LEGS = ("FL", "FR", "RL", "RR", "ML", "MR")          # channels: leg index * 2 (+1 for the knee)
HEX_SIDE = {"FL": "L", "ML": "L", "RL": "L", "FR": "R", "MR": "R", "RR": "R"}
HEX_GROUP = {"FL": 0, "MR": 0, "RL": 0, "FR": 1, "ML": 1, "RR": 1}   # tripod A swings first, tripod B half a cycle later
HEX_SWING_FRAC = 0.45        # each tripod is in the air 45% of the cycle; all six feet are down for the other 10%


def hex_leg_phase(cycle_t, leg):
    return (cycle_t - 0.5 * HEX_GROUP[leg]) % 1.0


def hex_leg_profile(phase):
    """Same shape as leg_profile() but with the hexapod's longer swing."""
    if phase < HEX_SWING_FRAC:
        s = phase / HEX_SWING_FRAC
        return -math.cos(math.pi * s), math.sin(math.pi * s)
    s = (phase - HEX_SWING_FRAC) / (1.0 - HEX_SWING_FRAC)
    return 1.0 - 2.0 * s, 0.0


class HexWalker:
    """Tripod gait for a 6-leg walker. Three feet are always down and the centre of mass sits inside them,
    so no weight shift is needed. Same command interface as Walker."""

    def __init__(self, stride_deg=20.0, lift_deg=25.0, period_s=1.4, ramp_per_s=2.0):
        self.stride = stride_deg
        self.lift = lift_deg
        self.period = period_s
        self.ramp = ramp_per_s
        self.cycle = 0.0
        self.target = {"L": 0.0, "R": 0.0}
        self.scale = {"L": 0.0, "R": 0.0}
        self.lift_scale = 0.0

    def command(self, fwd=0.0, turn=0.0):
        self.target["L"] = _clamp(fwd - turn)
        self.target["R"] = _clamp(fwd + turn)

    def stop(self):
        self.command(0.0, 0.0)

    @property
    def moving(self):
        return any(abs(v) > 1e-3 for v in self.scale.values()) or self.lift_scale > 1e-3

    def update(self, dt):
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
        for leg in HEX_LEGS:
            hip_f, lift_f = hex_leg_profile(hex_leg_phase(self.cycle, leg))
            out[leg + "_hip"] = self.stride * self.scale[HEX_SIDE[leg]] * hip_f
            out[leg + "_knee"] = self.lift * self.lift_scale * lift_f
        return out


def hex_stand_pose(height_deg=0.0):
    out = {}
    for leg in HEX_LEGS:
        out[leg + "_hip"] = 0.0
        out[leg + "_knee"] = -height_deg
    return out


# ============================================================ wheg rover: continuous-rotation windmill legs
class WhegDrive:
    """Four spinning legs. speed per wheg in [-1, 1] (+ = rolls the robot forward), scaled by max_throttle.
    Left wheels = fwd - turn, right wheels = fwd + turn, so turn=+1 spins left on the spot.
    angle[leg] is the simulated hub angle in degrees (for previews and tests; the real servo has no feedback)."""

    def __init__(self, max_throttle=0.5, rpm_full=110.0, ramp_per_s=2.0):
        self.max_throttle = max_throttle
        self.rpm_full = rpm_full
        self.ramp = ramp_per_s
        self.target = {"L": 0.0, "R": 0.0}
        self.scale = {"L": 0.0, "R": 0.0}
        self.angle = {leg: 0.0 for leg in LEGS}

    def command(self, fwd=0.0, turn=0.0):
        self.target["L"] = _clamp(fwd - turn)
        self.target["R"] = _clamp(fwd + turn)

    def stop(self):
        self.command(0.0, 0.0)

    @property
    def moving(self):
        return any(abs(v) > 1e-3 for v in self.scale.values())

    def speeds(self):
        return {leg: self.scale[SIDE[leg]] * self.max_throttle for leg in LEGS}

    def update(self, dt):
        step = self.ramp * dt
        for side in ("L", "R"):
            self.scale[side] = _approach(self.scale[side], self.target[side], step)
        sp = self.speeds()
        for leg in LEGS:
            self.angle[leg] = (self.angle[leg] + sp[leg] * self.rpm_full * 6.0 * dt) % 360.0
        return sp


def wheg_pulse_us(speed, sign=1, trim_us=0.0, span_us=500.0, center_us=1500.0):
    """Continuous-rotation servo pulse for a wheg speed in [-1, 1]. sign flips mirrored servos, trim_us is the
    per-servo stop point. speed 0 gives exactly the stop pulse."""
    speed = _clamp(speed)
    return center_us + trim_us + sign * speed * span_us
