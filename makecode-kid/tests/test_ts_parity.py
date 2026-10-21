"""The MakeCode TypeScript gait must match firmware/src/gait.py, and the servo driver must send sane pulses.
Needs node and the `typescript` npm package (set NODE_PATH if it is not installed globally)."""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "firmware", "src"))
import gait  # noqa: E402


def node(sc):
    r = subprocess.run(["node", os.path.join(HERE, "harness.js"), json.dumps(sc)], capture_output=True, text=True)
    if "Cannot find module 'typescript'" in r.stderr:
        pytest.skip("typescript npm package not available")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


SCENARIOS = [
    ((20, 25, 1.6, 2.0, 14, 50), [(1, 0, 400, 0.02), (0, 0, 200, 0.02)]),
    ((18, 27, 1.4, 2.5, 9, 57), [(1, 0, 150, 0.02), (0, 1, 150, 0.02), (-1, 0, 150, 0.02), (0, -1, 150, 0.02), (0, 0, 200, 0.02)]),
    ((12, 15, 2.2, 2.0, 0, 70), [(1, 0.5, 300, 0.033), (0, 0, 300, 0.033)]),
]


@pytest.mark.parametrize("cfg,steps", SCENARIOS)
def test_gait_matches_python(cfg, steps):
    got = node({"mode": "gait", "cfg": list(cfg), "steps": [{"fwd": f, "turn": t, "n": n, "dt": dt} for f, t, n, dt in steps]})
    w = gait.Walker(*cfg)
    want = []
    for f, t, n, dt in steps:
        w.command(f, t)
        for _ in range(n):
            pose = w.update(dt)
            want.append([pose[l + "_hip"] for l in gait.LEGS] + [pose[l + "_knee"] for l in gait.LEGS])
    assert len(got) == len(want)
    worst = max(abs(a - b) for g, wnt in zip(got, want) for a, b in zip(g, wnt))
    assert worst < 1e-9


def test_stand_sends_1500us_to_all_eight_channels():
    out = node({"mode": "hw"})
    assert sorted(int(c) for c in out["ticks"]) == list(range(8))
    for ch, (ticks, addr) in out["ticks"].items():
        assert ticks == round(1500 * 50.03 * 4096 / 1e6) and addr == 0x40


def test_hip_sign_matches_firmware_defaults():
    # front-left hip sign is -1: +20 deg must give a SHORTER pulse than centre (abs angle 70)
    out = node({"mode": "hw", "setLeg": [0, 0, 20]})
    ch, ticks = out["after"]
    assert ch == 0 and ticks == round((500 + 70 / 180 * 2000) * 50.03 * 4096 / 1e6)


def test_finds_board_at_kitronik_address():
    out = node({"mode": "hw", "missing": [0x40]})
    assert out["addrs"][-1] == 0x6C and out["shown"] == []


def test_missing_board_shows_sad_face():
    out = node({"mode": "hw", "missing": [0x40, 0x6C]})
    assert out["shown"] == ["sad"]


# ---------------- hexapod + windmill rover ----------------
def _py_hex(cfg, steps):
    w = gait.HexWalker(*cfg)
    want = []
    for f, t, n, dt in steps:
        w.command(f, t)
        for _ in range(n):
            pose = w.update(dt)
            want.append([pose[l + "_hip"] for l in gait.HEX_LEGS] + [pose[l + "_knee"] for l in gait.HEX_LEGS])
    return want


@pytest.mark.parametrize("cfg,steps", [
    ((20, 25, 1.4, 2.0), [(1, 0, 400, 0.02), (0, 0, 200, 0.02)]),
    ((16, 20, 1.1, 2.5), [(1, 0, 150, 0.02), (0, 1, 150, 0.02), (-1, 0, 150, 0.02), (1, -0.5, 150, 0.033), (0, 0, 200, 0.02)]),
])
def test_hex_gait_matches_python(cfg, steps):
    got = node({"mode": "gait", "style": 1, "cfg": list(cfg) + [0, 50], "steps": [{"fwd": f, "turn": t, "n": n, "dt": dt} for f, t, n, dt in steps]})
    want = _py_hex(cfg, steps)
    assert len(got) == len(want)
    assert max(abs(a - b) for g, wnt in zip(got, want) for a, b in zip(g, wnt)) < 1e-9


def test_wheg_drive_matches_python():
    steps = [(1, 0, 300, 0.02), (0, 1, 200, 0.02), (-1, 0, 200, 0.02), (1, -0.5, 200, 0.033), (0, 0, 250, 0.02)]
    got = node({"mode": "gait", "style": 2, "cfg": [20, 25, 1.6, 2.0, 0, 50], "wheg": [0.6, 100.0, 2.0],
                "steps": [{"fwd": f, "turn": t, "n": n, "dt": dt} for f, t, n, dt in steps]})
    w = gait.WhegDrive(0.6, 100.0, 2.0)
    want = []
    for f, t, n, dt in steps:
        w.command(f, t)
        for _ in range(n):
            sp = w.update(dt)
            want.append([sp[l] for l in gait.LEGS] + [w.angle[l] for l in gait.LEGS])
    assert len(got) == len(want)
    for g, wnt in zip(got, want):
        assert max(abs(a - b) for a, b in zip(g[:4], wnt[:4])) < 1e-9
        for a, b in zip(g[4:], wnt[4:]):
            d = abs(a - b) % 360
            assert min(d, 360 - d) < 1e-6


def test_wheg_pulse_matches_python():
    args = [(0, 1, 0), (1, 1, 0), (-1, -1, 0), (0.3, -1, 12), (5, 1, -7), (0, 1, 12)]
    got = node({"mode": "pulse", "args": [list(a) for a in args]})
    assert got == [gait.wheg_pulse_us(s, sign, trim) for s, sign, trim in args]


def test_hexapod_stand_drives_twelve_channels_and_crab_still_eight():
    hexa = node({"mode": "hw", "style": 1})
    assert sorted(int(c) for c in hexa["ticks"]) == list(range(12))
    crab = node({"mode": "hw", "style": 0})
    assert sorted(int(c) for c in crab["ticks"]) == list(range(8))
    for ch, (ticks, addr) in hexa["ticks"].items():
        assert ticks == round(1500 * 50.03 * 4096 / 1e6)


def test_windmill_stand_is_stop_pulse_on_channels_0_to_3_with_trim():
    out = node({"mode": "hw", "style": 2, "wheelTrim": [1, 12]})
    assert sorted(int(c) for c in out["ticks"]) == [0, 1, 2, 3]
    stop = round(1500 * 50.03 * 4096 / 1e6)
    assert all(ticks == stop for c, (ticks, _) in out["ticks"].items())
    assert out["afterTrim"] == [1, round(1512 * 50.03 * 4096 / 1e6)]
