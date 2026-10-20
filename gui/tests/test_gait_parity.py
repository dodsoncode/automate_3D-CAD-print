"""The browser designer (gui/js/gait.js) and the ESP32 firmware (firmware/src/gait.py) must produce the
same poses for the same commands. Runs both on a scripted sequence and compares."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "firmware", "src"))
import gait as pygait  # noqa: E402

# (command fwd, turn, seconds) segments, stepped at dt = 0.02 s
SCRIPT = [(1, 0, 3.0), (0, 1, 2.0), (-1, 0, 2.5), (1, -0.5, 2.0), (0, 0, 3.0), (1, 1, 1.0)]
DT = 0.02
PARAMS = (18.0, 27.0, 1.4, 2.5)   # stride, lift, period, ramp
SWAY_PARAMS = (18.0, 27.0, 1.4, 2.5, 9.0, 57.0)   # ... + sway, splay


def run_python(params=PARAMS):
    w = pygait.Walker(*params)
    out = []
    for fwd, turn, secs in SCRIPT:
        w.command(fwd, turn)
        for _ in range(int(round(secs / DT))):
            out.append(w.update(DT))
    return out


JS_RUNNER = r"""
const g = require(process.argv[1]);
const script = %s, dt = %s, P = %s;
const w = new g.Walker(...P);
const out = [];
for (const [fwd, turn, secs] of script) {
  w.command(fwd, turn);
  const n = Math.round(secs / dt);
  for (let i = 0; i < n; i++) out.push(w.update(dt));
}
console.log(JSON.stringify(out));
""" % (json.dumps(SCRIPT), DT, json.dumps(PARAMS))


def run_js(params=PARAMS):
    res = subprocess.run(["node", "-e", JS_RUNNER.replace(json.dumps(PARAMS), json.dumps(params)), os.path.join(ROOT, "gui", "js", "gait.js")],
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def test_js_gait_matches_python_gait():
    py, js = run_python(), run_js()
    assert len(py) == len(js) > 500
    worst = 0.0
    for a, b in zip(py, js):
        assert a.keys() == b.keys()
        for k in a:
            worst = max(worst, abs(a[k] - b[k]))
    assert worst < 1e-9, worst


def test_js_gait_with_sway_matches_python_gait():
    py, js = run_python(SWAY_PARAMS), run_js(SWAY_PARAMS)
    worst = max(abs(a[k] - b[k]) for a, b in zip(py, js) for k in a)
    assert worst < 1e-9, worst
    plain = run_python(PARAMS)
    # sway really changes the hips (and only the hips)
    assert any(abs(a["FL_hip"] - b["FL_hip"]) > 1.0 for a, b in zip(py, plain))
    assert all(abs(a["FL_knee"] - b["FL_knee"]) < 1e-9 for a, b in zip(py, plain))


def test_js_swing_order_matches():
    js = json.loads(subprocess.run(
        ["node", "-e", "const g=require(process.argv[1]);console.log(JSON.stringify([g.SWING_SLOT,g.SWING_FRAC,g.LEGS]))",
         os.path.join(ROOT, "gui", "js", "gait.js")], capture_output=True, text=True, check=True).stdout)
    assert js[0] == pygait.SWING_SLOT and js[1] == pygait.SWING_FRAC and js[2] == list(pygait.LEGS)
