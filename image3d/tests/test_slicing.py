"""Tests of the slicer core (slicing.py): STL preparation, option tables, G-code checks and the engine call.
The unit tests use synthetic data and a faked subprocess; the two integration tests run the real OrcaSlicer
engine and are skipped when it is not installed (bash image3d/slicer/install.sh).
Run: python -m pytest -q image3d/tests/test_slicing.py"""
import os
import struct
import subprocess
import sys
import zipfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
I3D = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, I3D)
import slicing  # noqa: E402

# unit-cube corners: index bits are (x, y, z); outward CCW triangles
TRIS = [0, 2, 1, 1, 2, 3, 4, 5, 6, 5, 7, 6, 0, 1, 4, 1, 5, 4, 2, 6, 3, 3, 6, 7, 0, 4, 2, 2, 4, 6, 1, 3, 5, 3, 7, 5]


def box_tris(sx, sy, sz, ox, oy, oz):
    pts = [(ox + (i & 1) * sx, oy + ((i >> 1) & 1) * sy, oz + ((i >> 2) & 1) * sz) for i in range(8)]
    return [tuple(pts[i] for i in TRIS[k:k + 3]) for k in range(0, len(TRIS), 3)]


def stl_bytes(tris):
    out = bytearray(b"test".ljust(80, b"\0") + struct.pack("<I", len(tris)))
    for t in tris:
        out += struct.pack("<12fH", 0, 0, 0, *[c for v in t for c in v], 0)
    return bytes(out)


def read_stl(data):
    n = struct.unpack_from("<I", data, 80)[0]
    pts = []
    for k in range(n):
        vals = struct.unpack_from("<12fH", data, 84 + 50 * k)
        pts += [vals[3:6], vals[6:9], vals[9:12]]
    return n, [[p[a] for p in pts] for a in range(3)]


# ---------- prepare_stl ----------
def test_prepare_centres_model():
    out, info = slicing.prepare_stl(stl_bytes(box_tris(20, 20, 20, -10, -10, -5)))
    n, (xs, ys, zs) = read_stl(out)
    assert n == 12 and info["triangles"] == 12
    assert 118 <= min(xs) and max(xs) <= 138 and 118 <= min(ys) and max(ys) <= 138
    assert min(zs) == pytest.approx(0) and max(zs) == pytest.approx(20)
    assert info["size_mm"] == pytest.approx([20, 20, 20])


def test_prepare_rejects():
    cube = stl_bytes(box_tris(20, 20, 20, 0, 0, 0))
    big = b"\0" * 80 + struct.pack("<I", slicing.MAX_TRIANGLES + 1) + b"\0" * (50 * (slicing.MAX_TRIANGLES + 1))
    cases = [
        (b"not an stl at all", 400),
        (b"solid cube\n" + b"facet normal 0 0 1\n outer loop\n vertex 0 0 0\n endloop\nendfacet\n" * 3, 400),
        (cube[:80] + struct.pack("<I", 13) + cube[84:], 400),                       # claims 13, holds 12
        (cube[:-10], 400),                                                          # truncated
        (b"\0" * 80 + struct.pack("<I", 0), 400),                                   # no triangles
        (big, 413),
        (stl_bytes(box_tris(300, 20, 20, 0, 0, 0)), 400),
    ]
    for data, status in cases:
        with pytest.raises(slicing.SliceError) as e:
            slicing.prepare_stl(data)
        assert e.value.status == status
        assert isinstance(e.value, ValueError)
    with pytest.raises(slicing.SliceError) as e:
        slicing.prepare_stl(big)
    assert "150" in str(e.value)
    with pytest.raises(slicing.SliceError) as e:
        slicing.prepare_stl(stl_bytes(box_tris(300, 20, 20, 0, 0, 0)))
    assert "256" in str(e.value) and "does not fit the 256 mm bed" in str(e.value)


# ---------- settings_for ----------
def test_settings_defaults_and_ids():
    s = slicing.settings_for({})
    assert s["printer"] == "Bambu Lab P1S 0.4 nozzle"
    assert s["filament"] == "Bambu PLA Basic @BBL P1S 0.4 nozzle"
    assert s["process"] == "0.20mm Standard @BBL X1C"
    assert s["options"]["curr_bed_type"] == "Textured PEI Plate"
    assert s["options"]["enable_support"] == "0"
    s = slicing.settings_for({"filament": "pla_silk_plus", "quality": "fine", "plate": "cool", "supports": "tree"})
    assert s["filament"] == "Bambu PLA Silk+ @BBL P1S 0.4 nozzle"
    assert s["process"] == "0.16mm Optimal @BBL X1C"
    assert s["options"] == {"curr_bed_type": "Cool Plate", "enable_support": "1", "support_type": "tree(auto)"}
    for key in ("filament", "quality", "plate", "supports"):
        with pytest.raises(slicing.SliceError) as e:
            slicing.settings_for({key: "nope"})
        assert e.value.status == 400


def test_options_tables():
    assert [o["id"] for o in slicing.OPTIONS["filament"]] == ["pla_basic", "pla_silk_plus", "pla_matte", "petg_hf"]
    assert [o["id"] for o in slicing.OPTIONS["quality"]] == ["standard", "fine", "draft"]
    assert [o["id"] for o in slicing.OPTIONS["plate"]] == ["textured_pei", "cool", "smooth_pei"]
    assert [o["id"] for o in slicing.OPTIONS["supports"]] == ["off", "tree"]
    for rows in slicing.OPTIONS.values():
        assert all(set(r) == {"id", "label", "profile"} for r in rows)


# ---------- check_gcode ----------
def gcode(printer="Bambu Lab P1S", nozzle="0.4", filament="Bambu PLA Basic @BBL P1S 0.4 nozzle",
          process="0.20mm Standard @BBL X1C", plate="Textured PEI Plate", support="0", body=None):
    if body is None:
        body = "G1 X120 Y130 E0.5 F1800\nG1 X121.5 Y130 E0.7"
    return "\n".join([
        "; HEADER_BLOCK_START",
        "; model printing time: 1h 23m 58s; total estimated time: 1h 28m 39s",
        "; total layer number: 348",
        "; HEADER_BLOCK_END",
        "; CONFIG_BLOCK_START",
        "; printer_model = " + printer,
        "; nozzle_diameter = " + nozzle,
        '; filament_settings_id = "%s"' % filament,
        "; print_settings_id = " + process,
        "; curr_bed_type = " + plate,
        "; enable_support = " + support,
        "; machine_start_gcode = " + "G28 ; home\\n" * 400,
        "; CONFIG_BLOCK_END",
        "G1 X-10 Y-5 E0.1 F900",                      # start-up purge before the first feature
        "; FEATURE: Outer wall",
        body,
        "; filament used [g] = 51.14",
        "",
    ])


def test_check_gcode_accepts():
    r = slicing.check_gcode(gcode(), slicing.settings_for({}))
    assert r == {"print_time": "1h 28m 39s", "filament_g": pytest.approx(51.14), "layers": 348}
    s = slicing.settings_for({"filament": "pla_silk_plus", "quality": "fine", "plate": "cool", "supports": "tree"})
    g = gcode(filament="Bambu PLA Silk+ @BBL P1S 0.4 nozzle", process="0.16mm Optimal @BBL X1C",
              plate="Cool Plate", support="1")
    assert slicing.check_gcode(g, s)["layers"] == 348


def test_check_gcode_rejects_off_bed():
    for bad in ("G1 X-3.2 Y40 E0.5", "G1 X100 Y256.5 E0.5", "G1 X256.1 E1", "G1 Y-0.1 E0.2",
                "G3 X-2 Y40 I1 J1 E0.5"):
        with pytest.raises(slicing.SliceError) as e:
            slicing.check_gcode(gcode(body="G1 X10 Y10 E0.1\n" + bad), slicing.settings_for({}))
        assert e.value.status == 500 and "bed" in str(e.value)


@pytest.mark.parametrize("kwargs,choice,word", [
    ({"printer": "Bambu Lab X1 Carbon"}, {}, "printer_model"),
    ({"nozzle": "0.6"}, {}, "nozzle_diameter"),
    ({"filament": "Bambu PETG HF @BBL P1S 0.4 nozzle"}, {}, "filament_settings_id"),
    ({"process": "0.28mm Extra Draft @BBL X1C"}, {}, "print_settings_id"),
    ({"plate": "Cool Plate"}, {}, "curr_bed_type"),
    ({"support": "0"}, {"supports": "tree"}, "enable_support"),
    ({"support": "1"}, {}, "enable_support"),
])
def test_check_gcode_rejects_setting_mismatch(kwargs, choice, word):
    with pytest.raises(slicing.SliceError) as e:
        slicing.check_gcode(gcode(**kwargs), slicing.settings_for(choice))
    assert e.value.status == 500 and word in str(e.value)


def test_check_gcode_ignores_travel_and_start_moves():
    body = "G1 X-10 F9000\nG1 X300 Y300 E0 F9000\nG1 X-4 Y-4 E-0.8\nG1 X120 Y120 E0.4"
    assert slicing.check_gcode(gcode(body=body), slicing.settings_for({}))["layers"] == 348


# ---------- run_slice with a faked engine ----------
def fake_run(monkeypatch, result=None, raises=None, write_output=False):
    def run(cmd, **kw):
        if write_output:
            open(cmd[-2], "wb").write(b"partial")
        if raises:
            raise raises
        return result
    monkeypatch.setattr(slicing.subprocess, "run", run)


def test_run_slice_engine_failure(monkeypatch, tmp_path):
    out = 'DEBUG: noise\nRESULT {"ok":false,"error":"boom"}\n'
    fake_run(monkeypatch, subprocess.CompletedProcess([], 1, stdout=out, stderr=""), write_output=True)
    with pytest.raises(slicing.SliceError) as e:
        slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path))
    assert e.value.status == 500 and "boom" in str(e.value)
    assert not os.path.exists(tmp_path / "model.gcode.3mf")


def test_run_slice_timeout(monkeypatch, tmp_path):
    fake_run(monkeypatch, raises=subprocess.TimeoutExpired("node", 5), write_output=True)
    with pytest.raises(slicing.SliceError) as e:
        slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path), timeout=5)
    assert e.value.status == 500 and "time limit" in str(e.value)
    assert not os.path.exists(tmp_path / "model.gcode.3mf")


def test_run_slice_missing_output(monkeypatch, tmp_path):
    fake_run(monkeypatch, subprocess.CompletedProcess([], 0, stdout='RESULT {"ok":true}\n', stderr=""))
    with pytest.raises(slicing.SliceError) as e:
        slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path))
    assert e.value.status == 500


def test_run_slice_deletes_output_when_check_fails(monkeypatch, tmp_path):
    def run(cmd, **kw):
        with zipfile.ZipFile(cmd[-2], "w") as z:
            z.writestr("Metadata/plate_1.gcode", gcode(nozzle="0.6"))
        return subprocess.CompletedProcess([], 0, stdout='RESULT {"ok":true}\n', stderr="")
    monkeypatch.setattr(slicing.subprocess, "run", run)
    with pytest.raises(slicing.SliceError) as e:
        slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path))
    assert "nozzle_diameter" in str(e.value)
    assert not os.path.exists(tmp_path / "model.gcode.3mf")


def test_run_slice_success_summary(monkeypatch, tmp_path):
    def run(cmd, **kw):
        assert kw["cwd"] == slicing.SLICER_DIR
        with zipfile.ZipFile(cmd[-2], "w") as z:
            z.writestr("Metadata/plate_1.gcode", gcode())
        return subprocess.CompletedProcess([], 0, stdout='RESULT {"ok":true}\n', stderr="")
    monkeypatch.setattr(slicing.subprocess, "run", run)
    path, summary = slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path))
    assert path == str(tmp_path / "model.gcode.3mf") and os.path.exists(path)
    assert summary["layers"] == 348 and summary["triangles"] == 12 and summary["size_mm"] == pytest.approx([20] * 3)
    assert summary["filament"] == "PLA Basic" and summary["plate"] == "Textured PEI"


# ---------- available ----------
def test_available_false_without_engine(monkeypatch, tmp_path):
    monkeypatch.setattr(slicing, "SLICER_DIR", str(tmp_path))
    assert slicing.available() is False
    assert slicing.node_path() == "node" or slicing.node_path().startswith(str(tmp_path))


# ---------- the real engine ----------
needs_engine = pytest.mark.skipif(not slicing.available(), reason="engine not installed (bash image3d/slicer/install.sh)")


def shelf_model():
    """30 mm cube with a 20 mm wide, 15 mm tall shelf hanging off one side at the top (needs support)."""
    return stl_bytes(box_tris(30, 30, 30, -15, -15, 0) + box_tris(20, 20, 15, 15, -10, 15))


def read_gcode(path):
    with zipfile.ZipFile(path) as z:
        return z.read("Metadata/plate_1.gcode").decode()


@needs_engine
def test_real_slice_pla_silk_plus_tree(tmp_path):
    choice = {"filament": "pla_silk_plus", "quality": "fine", "plate": "textured_pei", "supports": "tree"}
    path, summary = slicing.run_slice(shelf_model(), choice, str(tmp_path))
    assert zipfile.is_zipfile(path)
    assert "Metadata/plate_1.gcode" in zipfile.ZipFile(path).namelist()
    assert summary["layers"] > 100 and summary["filament_g"] > 0
    assert summary["triangles"] == 24
    assert slicing.check_gcode(read_gcode(path), slicing.settings_for(choice))["layers"] == summary["layers"]


@needs_engine
def test_real_slice_defaults(tmp_path):
    path, summary = slicing.run_slice(stl_bytes(box_tris(20, 20, 20, -10, -10, 0)), {}, str(tmp_path))
    assert slicing.check_gcode(read_gcode(path), slicing.settings_for({}))["filament_g"] > 0
    assert summary["print_time"]
