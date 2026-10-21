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
