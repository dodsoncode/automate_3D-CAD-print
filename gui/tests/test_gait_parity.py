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


# ---------------- hexapod + wheg rover ----------------
def _run_both(py_expr, js_expr, args):
    """py_expr builds a controller from `args`; js_expr is its JS twin. Both are driven with SCRIPT."""
    w = py_expr(*args)
    py = []
    for fwd, turn, secs in SCRIPT:
        w.command(fwd, turn)
        for _ in range(int(round(secs / DT))):
            r = w.update(DT)
            py.append((r, dict(getattr(w, "angle", {}))))
    code = ("const g=require(process.argv[1]);const S=%s,dt=%s;const w=new g.%s(...%s);const o=[];"
            "for(const [f,t,s] of S){w.command(f,t);const n=Math.round(s/dt);"
            "for(let i=0;i<n;i++){const r=w.update(dt);o.push([r,Object.assign({},w.angle||{})]);}}"
            "console.log(JSON.stringify(o));") % (json.dumps(SCRIPT), DT, js_expr, json.dumps(list(args)))
    res = subprocess.run(["node", "-e", code, os.path.join(ROOT, "gui", "js", "gait.js")], capture_output=True, text=True, check=True)
    return py, json.loads(res.stdout)


def test_hex_gait_matches_python():
    py, js = _run_both(pygait.HexWalker, "HexWalker", (17.0, 22.0, 1.3, 2.5))
    assert len(py) == len(js) > 500
    worst = max(abs(a[0][k] - b[0][k]) for a, b in zip(py, js) for k in a[0])
    assert worst < 1e-9, worst


def test_hex_tripods_alternate_and_three_feet_always_down():
    w = pygait.HexWalker()
    w.command(1, 0)
    for _ in range(2000):
        pose = w.update(0.01)
        up = [l for l in pygait.HEX_LEGS if pose[l + "_knee"] > 1.0]
        assert len(up) <= 3
        assert all(pygait.HEX_GROUP[l] == pygait.HEX_GROUP[up[0]] for l in up)   # only one tripod lifts at a time


def test_wheg_drive_matches_python_and_pulse_maps():
    py, js = _run_both(pygait.WhegDrive, "WhegDrive", (0.6, 100.0, 2.0))
    assert len(py) == len(js) > 500
    worst = max(max(abs(a[0][k] - b[0][k]) for k in a[0]) for a, b in zip(py, js))
    worst_ang = max(min(abs(a[1][k] - b[1][k]) % 360, 360 - abs(a[1][k] - b[1][k]) % 360) for a, b in zip(py, js) for k in a[1])   # angles wrap at 360
    assert worst < 1e-9 and worst_ang < 1e-6, (worst, worst_ang)
    assert pygait.wheg_pulse_us(0) == 1500 and pygait.wheg_pulse_us(1) == 2000 and pygait.wheg_pulse_us(-1, sign=-1) == 2000
    assert pygait.wheg_pulse_us(0, trim_us=12) == 1512
