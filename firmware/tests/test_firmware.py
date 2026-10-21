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
    assert leg_profile(gait.SWING_FRAC)[0] == pytest.approx(1.0)       # swing ends at front
    assert leg_profile(0.9999)[0] == pytest.approx(-1.0, abs=1e-3)
    assert leg_profile(gait.SWING_FRAC / 2)[1] == pytest.approx(1.0)      # max lift mid-swing
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
        assert len(swinging) <= 1          # never two feet in the air; brief moments with all four down


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


# ---------------- weight shift (sway) ----------------
def test_sway_zero_is_identical_to_plain_gait():
    a, b = Walker(), Walker(sway_deg=0.0)
    for w in (a, b):
        w.command(1, 0)
    for pa, pb in zip(run(a, 4.0), run(b, 4.0)):
        assert pa == pb


def test_sway_only_moves_hips_and_stays_within_limit():
    plain, swayed = Walker(), Walker(sway_deg=9.0)
    for w in (plain, swayed):
        w.command(1, 0)
    pp, ps = run(plain, 6.0), run(swayed, 6.0)
    assert any(abs(a["FL_hip"] - b["FL_hip"]) > 1.0 for a, b in zip(pp, ps))
    assert all(a[l + "_knee"] == b[l + "_knee"] for a, b in zip(pp, ps) for l in LEGS)
    assert max(abs(p[l + "_hip"]) for p in ps for l in LEGS) <= config.LIMITS["hip"][1]


def test_sway_is_off_when_standing():
    w = Walker(sway_deg=9.0)
    assert all(abs(v) < 1e-9 for v in w.update(0.02).values())


# ---------------- hexapod (tripod) ----------------
def test_hex_has_six_legs_in_two_tripods():
    assert len(gait.HEX_LEGS) == 6 and set(gait.HEX_GROUP.values()) == {0, 1}
    for g in (0, 1):
        legs = [l for l in gait.HEX_LEGS if gait.HEX_GROUP[l] == g]
        assert len(legs) == 3
        assert {gait.HEX_SIDE[l] for l in legs} == {"L", "R"}          # each tripod spans both sides
        assert sum(1 for l in legs if gait.HEX_SIDE[l] == "L") in (1, 2)


def test_hex_idle_is_neutral_and_walk_stays_in_limits():
    w = gait.HexWalker(stride_deg=20, lift_deg=25)
    assert all(v == 0 for v in w.update(0.02).values())
    w.command(1, 0)
    poses = run(w, 6.0)[200:]
    assert max(p["MR_hip"] for p in poses) == pytest.approx(20, abs=0.5)
    assert all(abs(p[l + "_hip"]) <= config.LIMITS["hip"][1] for p in poses for l in gait.HEX_LEGS)
    assert all(0 <= p[l + "_knee"] <= 25 + 1e-6 for p in poses for l in gait.HEX_LEGS)


def test_hex_spin_reverses_one_side():
    w = gait.HexWalker()
    w.command(0, 1)
    run(w, 3.0)
    assert w.scale["L"] == -1.0 and w.scale["R"] == 1.0


# ---------------- wheg rover ----------------
def test_wheg_ramps_scales_and_stops():
    w = gait.WhegDrive(max_throttle=0.5, rpm_full=110, ramp_per_s=2.0)
    w.command(1, 0)
    sp = w.update(0.1)
    assert sp["FL"] == pytest.approx(0.1) and sp["FR"] == pytest.approx(0.1)   # ramped, then times max throttle 0.5
    for _ in range(100):
        sp = w.update(0.02)
    assert all(v == pytest.approx(0.5) for v in sp.values())
    w.stop()
    for _ in range(100):
        sp = w.update(0.02)
    assert all(abs(v) < 1e-9 for v in sp.values()) and not w.moving


def test_wheg_turn_spins_in_place_and_angle_integrates():
    w = gait.WhegDrive(max_throttle=1.0, rpm_full=60, ramp_per_s=1000)
    w.command(0, 1)
    w.update(1.0)
    assert w.target["L"] == -1.0 and w.target["R"] == 1.0
    # 60 rpm for 1 s is one full turn, so the hub is back at 0 (or just under 360); the left hubs turn the other way
    assert min(w.angle["FR"], 360 - w.angle["FR"]) < 1e-6
    w2 = gait.WhegDrive(max_throttle=1.0, rpm_full=60, ramp_per_s=1000)
    w2.command(0, 1)
    w2.update(0.25)
    assert w2.angle["FR"] == pytest.approx(90.0, abs=1e-6) and w2.angle["FL"] == pytest.approx(270.0, abs=1e-6)


def test_wheg_pulse_range_and_trim():
    assert gait.wheg_pulse_us(0.0) == 1500
    assert gait.wheg_pulse_us(1.0) == 2000 and gait.wheg_pulse_us(-1.0) == 1000
    assert gait.wheg_pulse_us(5.0) == 2000                  # clamped
    assert gait.wheg_pulse_us(0.0, trim_us=-20) == 1480     # per-servo stop trim


# ---------------- styles: drive.make_rig ----------------
class Cfg:
    """config module copy with another STYLE."""
    def __init__(self, style):
        self.__dict__.update({k: getattr(config, k) for k in dir(config) if not k.startswith("__")})
        self.STYLE = style
        self.load_wheg_trim = lambda: dict(config.WHEG_TRIM_US)
        self.load_wheg_signs = lambda: dict(config.WHEG_SIGNS)
        self.load_calib = lambda style=None, _s=style: config.load_calib("/nonexistent.json", style=_s)


def test_hex_channels_unique_and_complete():
    ch, signs, offs = config.style_tables("hex")
    assert sorted(ch.values()) == list(range(12))
    assert set(ch) == {l + "_" + j for l in config.HEX_LEGS for j in config.JOINTS} == set(signs) == set(offs)
    assert {k: v for k, v in ch.items() if k in config.CHANNELS} == config.CHANNELS      # crab wiring is unchanged
    assert config.style_tables("crab")[0] == config.CHANNELS


def test_hex_rig_walks_and_mirrors_middle_legs():
    import drive
    d = FakeDriver()
    rig = drive.make_rig(Cfg("hex"), d)
    rig.stand()
    assert sorted(d.us) == list(range(12)) and all(abs(v - 1500) < 1e-6 for v in d.us.values())
    rig.command(1, 0)
    seen = set()
    for _ in range(300):
        rig.update(0.02)
        assert all(500 <= v <= 2500 for v in d.us.values())
        seen.add(round(d.us[8]))
    assert len(seen) > 20 and rig.moving                       # the middle-left hip really sweeps
    # middle legs mirror like the front legs: left = -1, right = +1 hip sign
    assert config.HEX_SIGNS["ML_hip"] == config.SIGNS["FL_hip"] and config.HEX_SIGNS["MR_hip"] == config.SIGNS["FR_hip"]
    rig.relax()
    assert d.offed == set(range(12))


def test_crab_rig_matches_plain_walker():
    import drive
    d = FakeDriver()
    rig = drive.make_rig(Cfg("crab"), d)
    rig.command(1, 0)
    w = Walker(config.GAIT_STRIDE_DEG, config.GAIT_LIFT_DEG, config.GAIT_PERIOD_S, sway_deg=config.GAIT_SWAY_DEG, splay_deg=config.GAIT_SPLAY_DEG)
    w.command(1, 0)
    s, d2 = make_servos()
    for _ in range(200):
        rig.update(0.02)
        s.apply(w.update(0.02))
    assert d.us == d2.us


def test_wheg_rig_stop_pulses_trim_and_direction():
    import drive
    d = FakeDriver()
    trims = {"FL": 12.0, "FR": -7.0, "RL": 0.0, "RR": 0.0}
    rig = drive.make_rig(Cfg("wheg"), d, trims=trims)
    rig.stand()
    assert d.us == {0: 1512.0, 1: 1493.0, 2: 1500.0, 3: 1500.0}          # still = stop pulse + trim exactly
    rig.command(1, 0)
    for _ in range(200):
        rig.update(0.02)
    top = config.WHEG_MAX_THROTTLE * config.WHEG_SPAN_US
    assert d.us[0] == pytest.approx(1512 + top) and d.us[1] == pytest.approx(1493 - top)   # right servo mirrored
    rig.command(0, 1)                                                      # spin left on the spot
    for _ in range(300):
        rig.update(0.02)
    assert d.us[0] < 1512 and d.us[2] < 1500 and d.us[1] < 1493 and d.us[3] < 1500       # FL/RL back, FR/RR (mirrored) also below stop -> forward
    rig.stop()
    for _ in range(300):
        rig.update(0.02)
    assert not rig.moving and d.us == {0: 1512.0, 1: 1493.0, 2: 1500.0, 3: 1500.0}
    rig.relax()
    assert d.offed == {0, 1, 2, 3}


def test_wheg_throttle_never_exceeds_max():
    import drive
    d = FakeDriver()
    rig = drive.make_rig(Cfg("wheg"), d, trims={k: 0.0 for k in config.LEGS})
    rig.command(5, 5)
    for _ in range(300):
        rig.update(0.02)
        assert all(abs(v - 1500) <= config.WHEG_MAX_THROTTLE * config.WHEG_SPAN_US + 1e-6 for v in d.us.values())


def test_calib_roundtrip_with_wheg(tmp_path):
    p = str(tmp_path / "c.json")
    config.save_calib(dict(config.SIGNS), dict(config.OFFSETS), p, wheg_signs={"FL": -1, "FR": -1, "RL": 1, "RR": -1}, wheg_trim_us={"FL": 9.0, "FR": 0.0, "RL": 0.0, "RR": 0.0})
    assert config.load_wheg_trim(p)["FL"] == 9.0 and config.load_wheg_signs(p)["FL"] == -1
    assert config.load_wheg_trim("/nonexistent.json") == config.WHEG_TRIM_US
