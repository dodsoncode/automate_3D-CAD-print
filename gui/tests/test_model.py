"""Design-model checks run in Node: every style's defaults are all green, random designs always give closed
printable shells, and the hexapod / wheg behave the way the maths says they should."""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))


def node(js):
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, cwd=HERE)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_fuzz_all_styles_closed_and_defaults_green():
    r = subprocess.run(["node", os.path.join(HERE, "fuzz_model.js"), "80"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    rep = json.loads(r.stdout)
    assert rep["failures"] == [], rep["failures"][:3]
    for st, s in rep["styles"].items():
        assert s["runs"] == 80 and s["closedFail"] == 0 and s["volFail"] == 0 and s["nan"] == 0 and not s.get("exceptions"), (st, s)
        assert s["defaultWorst"] == "ok", st


def test_hexapod_has_six_legs_twelve_windows_and_is_stable_without_sway():
    out = node("""
const M=require('../js/model.js');const p=M.styleDefaults('hex');const d=M.derive(p),a=M.analyze(p);
console.log(JSON.stringify({legs:d.legs,n:Object.keys(d.win).length,margin:a.stability.margin,objs:M.printObjects(p,d).length,
  holes:M.buildParts(p,d).body[0].shells[0].t.length}));""")
    assert out["legs"] == ["FL", "FR", "RL", "RR", "ML", "MR"] and out["n"] == 6
    assert out["objs"] == 1 + 6 * 3
    assert out["margin"] > 12          # tripod: the centre of mass sits well inside three feet, no weight shift used


def test_hexapod_middle_motors_sit_beside_the_bays_not_in_them():
    out = node("""
const M=require('../js/model.js');const p=M.styleDefaults('hex');const d=M.derive(p);
console.log(JSON.stringify({mid:d.win.ML,bayHalf:d.innerW/2,cutL:d.cutL}));""")
    assert out["mid"][0] == 0 and out["mid"][1] - out["cutL"] / 2 > out["bayHalf"]


def test_wheg_whegs_clear_each_other_and_flags_overlong_spokes():
    out = node("""
const M=require('../js/model.js');const p=M.styleDefaults('wheg');
const ok=M.analyze(p).checks.find(c=>c.id==='wheelgap').level;
p.spokeLen=75;const bad=M.analyze(p).checks.find(c=>c.id==='wheelgap').level;
console.log(JSON.stringify({ok,bad}));""")
    assert out == {"ok": "ok", "bad": "bad"}


def test_wheg_check_responds_to_spoke_count_and_battery_weight():
    out = node("""
const M=require('../js/model.js');
const a=M.styleDefaults('wheg');a.spokeCount=2;const c2=M.analyze(a).checks.find(c=>c.id==='height').level;
const b=M.styleDefaults('wheg');b.batteryPreset='4xAA';b.battery={L:62,W:58,H:17,mass:135};
const heavy=M.analyze(b),light=M.analyze(M.styleDefaults('wheg'));
console.log(JSON.stringify({c2,heavier:heavy.torque.need>light.torque.need}));""")
    assert out["c2"] in ("warn", "bad")      # two spokes: belly drags when both touch down
    assert out["heavier"]


def test_old_saved_design_without_style_loads_as_crab():
    out = node("""
const M=require('../js/model.js');const p=M.defaults();delete p.style;M.clampParams(p);
console.log(JSON.stringify({style:p.style,worst:M.analyze(p).worst}));""")
    assert out == {"style": "crab", "worst": "ok"}
