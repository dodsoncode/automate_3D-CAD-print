import config
import gait
import pytest
from gait import LEGS, Walker, leg_phase, leg_profile
from pca9685 import PCA9685
from servos import Servos


# ---------------- fakes ----------------
class FakeDriver:
    def __init__(self):
        self.us = {}
        self.offed = set()

    def set_us(self, ch, us):
        self.us[ch] = us
        self.offed.discard(ch)

    def off(self, ch):
        self.offed.add(ch)


class FakeI2C:
    def __init__(self):
        self.mem = {}
        self.writes = []

    def writeto_mem(self, addr, reg, data):
        self.writes.append((reg, bytes(data)))
        for i, b in enumerate(data):
            self.mem[reg + i] = b

    def readfrom_mem(self, addr, reg, n):
        return bytes(self.mem.get(reg + i, 0) for i in range(n))


def make_servos(**kw):
    d = FakeDriver()
    s = Servos(d, config.CHANNELS, dict(config.SIGNS), dict(config.OFFSETS), config.LIMITS, **kw)
    return s, d


def run(w, seconds, dt=0.02):
    poses = []
    for _ in range(int(seconds / dt)):
        poses.append(w.update(dt))
    return poses


# ---------------- gait ----------------
def test_profile_endpoints():
    assert leg_profile(0.0)[0] == pytest.approx(-1.0)
    assert leg_profile(0.25)[0] == pytest.approx(1.0)       # swing ends at front
    assert leg_profile(0.9999)[0] == pytest.approx(-1.0, abs=1e-3)
    assert leg_profile(0.125)[1] == pytest.approx(1.0)      # max lift mid-swing
    assert leg_profile(0.5)[1] == 0.0


def test_profile_is_continuous():
    prev = leg_profile(0.0)
    n = 4000
    for i in range(1, n + 1):
        cur = leg_profile((i / n) % 1.0)
        assert abs(cur[0] - prev[0]) < 0.02 and abs(cur[1] - prev[1]) < 0.02
        prev = cur


def test_at_most_one_leg_in_swing_at_any_time():
    for i in range(1000):
        t = i / 1000
        swinging = [l for l in LEGS if leg_phase(t, l) < gait.SWING_FRAC]
        assert len(swinging) == 1


def test_swing_order_and_even_spacing():
    starts = sorted((gait.SWING_SLOT[l], l) for l in LEGS)
    assert [l for _, l in starts] == ["RR", "FR", "RL", "FL"]


def test_idle_walker_stays_neutral():
    w = Walker()
    for pose in run(w, 1.0):
        assert all(v == 0.0 for v in pose.values())
    assert not w.moving


def test_forward_walk_limits_and_one_foot_up():
    w = Walker(stride_deg=20, lift_deg=25)
    w.command(1, 0)
    poses = run(w, 6.0)[200:]             # skip ramp-up
    assert max(p["FL_hip"] for p in poses) == pytest.approx(20, abs=0.5)
    assert min(p["FL_hip"] for p in poses) == pytest.approx(-20, abs=0.5)
    for p in poses:
        lifted = [l for l in LEGS if p[l + "_knee"] > 1.0]
        assert len(lifted) <= 1
        assert all(0.0 <= p[l + "_knee"] <= 25.0 + 1e-6 for l in LEGS)


def test_backward_reverses_sweep_direction():
    def stance_slope(fwd):               # sample FL hip motion mid-stance
        w = Walker()
        w.command(fwd, 0)
        run(w, 3.0)
        while leg_phase(w.cycle, "FL") < 0.4 or leg_phase(w.cycle, "FL") > 0.6:
            w.update(0.01)
        a = w.update(0.02)["FL_hip"]
        b = w.update(0.02)["FL_hip"]
        return b - a
    assert stance_slope(1) < 0       # stance pushes body forward by sweeping foot backward
    assert stance_slope(-1) > 0


def test_spin_in_place_opposite_sides():
    w = Walker()
    w.command(0, 1)                   # spin left: left sweep reversed vs right
    assert w.target["L"] == -1.0 and w.target["R"] == 1.0
    run(w, 3.0)
    assert w.scale["L"] == -1.0 and w.scale["R"] == 1.0
    # same phase profile, opposite sign: a left leg and a right leg at equal phase mirror each other
    for _ in range(50):
        w.update(0.02)
        pose = w.pose()
        hip_f_l, _ = leg_profile(leg_phase(w.cycle, "FL"))
        hip_f_r, _ = leg_profile(leg_phase(w.cycle, "FR"))
        assert pose["FL_hip"] == pytest.approx(-w.stride * hip_f_l)
        assert pose["FR_hip"] == pytest.approx(w.stride * hip_f_r)


def test_command_clamped_and_ramped():
    w = Walker(ramp_per_s=2.0)
    w.command(1, 1)                   # fwd+turn saturates
    assert w.target["R"] == 1.0 and w.target["L"] == 0.0
    w.update(0.1)
    assert w.scale["R"] == pytest.approx(0.2)    # ramped, not jumped


def test_stop_returns_to_neutral_smoothly():
    def max_step(poses):
        return max(abs(b[k] - a[k]) for a, b in zip(poses, poses[1:]) for k in a)

    w = Walker()
    w.command(1, 0)
    steady = max_step(run(w, 4.0)[100:])          # full-speed swing is the fastest motion
    w.stop()
    poses = run(w, 3.0)
    assert not w.moving
    assert all(abs(v) < 1e-6 for v in poses[-1].values())
    assert max_step(poses) <= steady * 1.05       # winding down never jumps harder than walking
    assert steady < 5.0                           # ~160 deg/s peak: well within MG90S speed


# ---------------- servos ----------------
def test_neutral_is_1500us_when_centered():
    s, d = make_servos(us_min=500, us_max=2500, range_deg=180)
    s.neutral()
    for ch in config.CHANNELS.values():
        assert d.us[ch] == pytest.approx(1500)


def test_sign_and_offset_applied():
    s, d = make_servos()
    s.signs["FL_hip"] = 1
    s.offsets["FL_hip"] = 5.0
    s.set("FL_hip", 10.0)
    assert d.us[0] == pytest.approx(500 + (90 + 10 + 5) / 180 * 2000)
    s.signs["FL_hip"] = -1
    s.set("FL_hip", 10.0)
    assert d.us[0] == pytest.approx(500 + (90 - 10 + 5) / 180 * 2000)


def test_limits_clamp_both_ways():
    s, d = make_servos()
    s.signs["FL_hip"] = 1
    assert s.set("FL_hip", 999) == 45.0
    assert s.set("FL_hip", -999) == -45.0
    s.signs["FL_knee"] = 1
    assert s.set("FL_knee", 999) == 60.0
    assert s.set("FL_knee", -999) == -30.0


def test_absolute_angle_clamped_to_servo_range():
    s, _ = make_servos()
    s.offsets["FL_hip"] = 80.0         # absurd trim must not exceed 180 deg
    assert s.angle_to_us(170.0) == pytest.approx(500 + 170 / 180 * 2000)
    assert s.angle_to_us(250.0) == pytest.approx(2500)
    assert s.angle_to_us(-10.0) == pytest.approx(500)


def test_relax_turns_all_channels_off():
    s, d = make_servos()
    s.neutral()
    s.relax()
    assert d.offed == set(config.CHANNELS.values())


def test_mirrored_sides_move_feet_the_same_way():
    """With default signs a +hip command must send LEFT and RIGHT servos opposite raw ways."""
    s, d = make_servos()
    s.set("FL_hip", 10)
    s.set("FR_hip", 10)
    left, right = d.us[config.CHANNELS["FL_hip"]], d.us[config.CHANNELS["FR_hip"]]
    assert (left - 1500) * (right - 1500) < 0


def test_full_gait_pose_maps_to_valid_pulses():
    s, d = make_servos()
    w = Walker()
    w.command(1, 0.5)
    for pose in run(w, 5.0):
        s.apply(pose)
        for us in d.us.values():
            assert 500 <= us <= 2500


# ---------------- PCA9685 ----------------
def test_pca_prescale_for_50hz():
    i2c = FakeI2C()
    p = PCA9685(i2c, freq=50)
    assert i2c.mem[0xFE] == 121               # datasheet value for 50 Hz at 25 MHz
    assert p.freq == pytest.approx(50.03, abs=0.05)   # integer prescale rounds 50 Hz slightly


def test_pca_ticks_and_register_write():
    i2c = FakeI2C()
    p = PCA9685(i2c, freq=50)
    assert p.us_to_ticks(1500) == pytest.approx(1500e-6 * p.freq * 4096, abs=1)
    p.set_us(3, 1500)
    base = 0x06 + 4 * 3
    off = i2c.mem[base + 2] | (i2c.mem[base + 3] << 8)
    assert off == p.us_to_ticks(1500)
    assert i2c.mem[base] == 0 and i2c.mem[base + 1] == 0


def test_pca_off_sets_full_off_bit():
    i2c = FakeI2C()
    p = PCA9685(i2c, freq=50)
    p.off(0)
    assert i2c.mem[0x06 + 3] & 0x10


def test_pca_clamps_pulse_to_register_range():
    i2c = FakeI2C()
    p = PCA9685(i2c, freq=50)
    p.set_us(0, 100000)
    assert (i2c.mem[0x06 + 2] | (i2c.mem[0x06 + 3] << 8)) == 4095


# ---------------- config ----------------
def test_config_channels_unique_and_complete():
    assert sorted(config.CHANNELS.values()) == list(range(8))
    assert set(config.CHANNELS) == {l + "_" + j for l in config.LEGS for j in config.JOINTS}
    assert set(config.SIGNS) == set(config.CHANNELS) == set(config.OFFSETS)


def test_calib_roundtrip(tmp_path):
    p = str(tmp_path / "c.json")
    signs, offs = config.load_calib(p)                  # missing file -> defaults
    assert signs == config.SIGNS
    signs["FL_hip"] = 1
    offs["FL_hip"] = 4.5
    config.save_calib(signs, offs, p)
    s2, o2 = config.load_calib(p)
    assert s2["FL_hip"] == 1 and o2["FL_hip"] == 4.5


def test_battery_divider_range():
    full = 8.4 / config.BATT_DIVIDER
    cutoff = config.BATT_CUTOFF_V / config.BATT_DIVIDER
    assert 0 < cutoff < full < 3.1             # inside ESP32 ADC range at 11 dB
