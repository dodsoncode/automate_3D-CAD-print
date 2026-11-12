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


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_prepare_rejects_non_finite_coordinates(bad):
    tris = box_tris(20, 20, 20, -10, -10, 0)
    tris[3] = ((bad, tris[3][0][1], tris[3][0][2]),) + tris[3][1:]
    with pytest.raises(slicing.SliceError) as e:
        slicing.prepare_stl(stl_bytes(tris))
    assert e.value.status == 400


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
        body = "M83\nG1 X120 Y130 E0.5 F1800\nG1 X121.5 Y130 E0.7"
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
        "G1 X110 Y110 F3000",
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
    body = "M83\nG1 X-10 F9000\nG1 X300 Y300 E0 F9000\nG1 X-4 Y-4 E-0.8\nG1 X120 Y120 F9000\nG1 X121 Y120 E0.4"
    assert slicing.check_gcode(gcode(body=body), slicing.settings_for({}))["layers"] == 348


MOVE_REJECTS = [
    # position is inherited from earlier moves
    "G1 X300 Y10 F9000\nG1 Y50 E1",
    "G1 X10 Y300 F9000\nG1 X50 E1",
    # arcs: the path bulges off the bed although the endpoint is on it; full circle without an endpoint
    "G1 X30 Y100 F9000\nG2 X10 Y120 I-20 J0 E1",     # clockwise 270 degrees round the left side
    "G1 X30 Y100 F9000\nG3 X10 Y80 I-20 J0 E1",      # counter-clockwise 270 degrees round the left side
    "G1 X100 Y100 F9000\nG2 I-400 J0 E1",
    "G1 X100 Y100 F9000\nG2 X110 Y100 R5 E1",     # R form cannot be bounded
    "G1 X100 Y100 F9000\nG2 X110 Y100 E1",        # no I/J at all
    # relative positioning
    "G1 X1 Y100 F9000\nG91\nG1 X-2 E1\nG90",
    "G28\nG91\nG1 X5 E1",                         # position unknown
    "G28\nG1 Y50 E1",                              # position unknown after homing
    # spellings
    "G1 X10 Y10 F9000\ng1 x-5 y5 e1",
    "G1 X10 Y10 F9000\nG01 X-5 Y5 E1",
    "G1 X10 Y10 F9000\nG1\tX-5 E1",
    "G1 X10 Y10 F9000\nG1X-5 E1",
    "G1 X10 Y10 F9000\nG1 X-5 E+1",
    "G1 X10 Y10 F9000\nG1 X+300 E1",
    "G1 X10 Y10 F9000\nG1 Xnan E1",
    "G1 X10 Y10 F9000\nG1 X5 E1 *71",              # junk the parser cannot read
    # extruder modes
    "M82\nG92 E-5\nG1 X-5 Y5 E-3",                # absolute E, negative but advancing
    "G1 X300 Y10 E5",                               # mode never declared (the firmware default is absolute)
    "M82\nG92 E0\nG1 X300 Y10 E5",
    "M83\nG1 X-5 Y5 E1",
    # round 2: zero-sweep arc = full circle; stale absolute E; either reading while the mode is undeclared
    "G1 X128 Y128 F9000\nG2 X129 Y128 I-200 J0 E1",
    "G1 X128 Y128 F9000\nG3 X129 Y128 I-200 J0 E1",
    "M82\nG92 E0\nG1 X101 Y100 E100\nM83\nG1 X102 Y100 E-60\nM82\nG1 X300 Y100 E50",
    "G92 E0\nG1 X101 Y100 E5\nG1 X-5 Y100 E3",
    # exponent / hex numbers
    "G1 X10 Y10 F9000\nG1 X3e2 E1",
    "G1 X10 Y10 F9000\nG1 X1e3 Y10 E1",
    "G1 X10 Y10 F9000\nG1 X0x1F E1",
    # position resets, other motion commands, several commands on one line
    "G1 X100 Y100 F9000\nG92 X0 Y0\nG1 X250 Y250 E1",
    "G1 X100 Y100 F9000\nG92 Y-300\nG1 X100 E1",
    "G5 X300 Y300 I1 J1 P1 Q1 E1",
    "G53 G1 X300 E1",
    "M83 G1 X300 Y10 E1",
    "G1 X10 Y10 G1 X300 E1",
    "G2.1 X300 Y10 I1 E1",
    # round 3: plane changes, decimal G codes, lines without a G/M command, repeated / glued words, offsets
    "G1 X128 Y128 F9000\nG18\nG2 X100 Y129 I100 E1",
    "G1 X128 Y128 F9000\nG19\nG3 X100 Y129 J100 E1",
    "G1 X128 Y128 F9000\nG91\nG90.1\nG1 X200 E1",
    "G90.1\nG2 X130 Y128 I5 J0 E1",
    "G1 X128 Y128 F9000\nG91.1\nG2 X130 Y128 I5 J0 E1",
    "G1 X128 Y128 F9000\nG1.1 X200 E1",
    "G92.1\nG1 X128 Y128 E1",
    "T0 G1 X300 E1",
    "G1 X10 Y10 F9000\nX300 E1",
    "G1 X10 Y10 F9000\nN10 X300 E1",
    "G1 X300 X128 E1",
    "G1 X300 E1 E-1",
    "G1 X300 E1G1 X100",
    "G1 X128 Y128 I1 I2 J1 E1",
    "M206 X-200",
    "M428",
    "G10 L2 X-200",
    "G53",
    "G54",
    "G55",
    "G59",
    "G59.3",
    "G54.1 P1",
]


@pytest.mark.parametrize("pre", ["G18", "G90.1", "G91.1", "G54", "G59.3", "M206 X-200", "G10", "T0 G1 X10"])
def test_check_gcode_rejects_modal_changes_before_printing(pre):
    g = gcode(body="G1 X100 Y100 E1").replace("G1 X110 Y110 F3000", pre + "\nG1 X110 Y110 F3000")
    with pytest.raises(slicing.SliceError) as e:
        slicing.check_gcode(g, slicing.settings_for({}))
    assert e.value.status == 500


@pytest.mark.parametrize("body", MOVE_REJECTS)
def test_check_gcode_rejects_unsafe_moves(body):
    with pytest.raises(slicing.SliceError) as e:
        slicing.check_gcode(gcode(body=body), slicing.settings_for({}))
    assert e.value.status == 500


def test_check_gcode_needs_print_moves():
    body = "G1 X300 Y300 E5"
    for g in (gcode(body=body).replace("; FEATURE: Outer wall\n", ""), "; printer_model = Bambu Lab P1S\n"):
        with pytest.raises(slicing.SliceError) as e:
            slicing.check_gcode(g, slicing.settings_for({}))
        assert "no print moves found" in str(e.value) or "missing" in str(e.value)
    with pytest.raises(slicing.SliceError) as e:
        slicing.check_gcode(gcode(body=body).replace("; FEATURE: Outer wall\n", ""), slicing.settings_for({}))
    assert "no print moves found" in str(e.value)


def test_check_gcode_move_messages():
    def msg(body):
        with pytest.raises(slicing.SliceError) as e:
            slicing.check_gcode(gcode(body=body), slicing.settings_for({}))
        return str(e.value)
    assert "unreadable move" in msg("G1 X10 Y10 F9000\nG1 Xnan E1")
    assert "arc cannot be bounded" in msg("G1 X100 Y100 F9000\nG2 X110 Y100 R5 E1")
    assert "position reset not allowed" in msg("G1 X100 Y100 F9000\nG92 X0 Y0")
    assert "unsupported move" in msg("G5 X300 Y300 I1 J1 P1 Q1 E1")
    assert "unsupported move" in msg("G53 G1 X300 E1")
    assert "unsupported move" in msg("G18")
    assert "unsupported move" in msg("G90.1")
    assert "unsupported move" in msg("T0 G1 X300 E1")
    assert "unsupported move" in msg("M206 X-200")
    assert "unreadable move" in msg("G1 X300 X128 E1")
    assert "unreadable move" in msg("G1 X300 E1G1 X100")
    assert "outside the bed" in msg("G1 X128 Y128 F9000\nG2 X129 Y128 I-200 J0 E1")
    assert "outside the bed" in msg("G1 X30 Y100 F9000\nG2 X10 Y120 I-20 J0 E1")


MOVE_ACCEPTS = [
    "G1 X100 Y100 F9000\nG2 X110 Y110 I10 J0 E1",                          # on-bed arc
    "G1 X30 Y100 F9000\nG3 X10 Y120 I-20 J0 E1",                           # quarter arc that stays on the bed
    "G1 X10 Y100 F9000\nG2 X30 Y100 I10 J0 E1",                            # half circle over the top, centre on bed
    "M83\nG1 X-20 Y50 F9000\nG1 X100 Y100 F9000\nG1 X120 Y100 E1",        # travel off the bed, back, then print
    "M82\nG92 E0\nG1 X120 Y120 E1\nG1 X121 Y120 E0.5\nG1 X122 Y120 E1.2",  # absolute E with a retract
    "M82\nG92 E10\nG1 X-5 Y5 E8",                                          # absolute E going backwards = retract
    "M83\nG1 X-5 Y5 E-0.8\nG1 X-5 Y5 E0",                                  # relative retract off the bed
    "G91\nG1 X5 Y5 E1\nG90\nG1 X100 Y100 E2",                             # small relative step on the bed
    "G28\nG1 X100 Y100 F9000\nG1 X110 Y100 E1",                            # homed, then positioned
    "T0\nT255\nG17\nG1 X100 Y100 F9000\nG1 X110 Y100 E1",                  # tool word on its own line, XY plane
    "G29.2 S0\nG1 X100 Y100 F9000\nG1 X110 Y100 E1",                         # decimal code without axes
    "N10 G1 X128 Y128 E1",                                                  # line number prefix
    "G4 P100\nG29\nG21\nG92 E0\nM83\nG1 X100 Y100 F9000\nG1 X110 Y100 E1",   # commands the real engine writes
    "M82\nG92 E0\nG1 X101 Y100 E10\nM83\nG1 X102 Y100 E-6\nM82\nG1 X103 Y100 E5",  # E position kept across modes
    "G1 X100 Y100 F9000\nG2 X110 Y100 I5 J0 E1",                           # half circle, centre on bed
    "G1 X128 Y128 F9000\nG2 X128.0001 Y128 I-20 J0 E1",                    # near-full circle that fits
]


REAL_LINES = ['G1 X10.1 Y20 Z0.28 F5000.0 ;Move to start position', 'M109 S205;', 'G1 X10.1 Y200.0 Z0.28 F1500.0 E15 ;Draw the first line', 'G1 X10.4 Y200.0 Z0.28 F5000.0 ;Move to side a little', 'G1 X10.4 Y20 Z0.28 F1500.0 E30 ;Draw the second line', 'G92 E0 ;Reset Extruder', 'G1 X110 Y110 Z2.0 F3000 ;Move Z Axis up', 'M73 P14 R28', 'G90', 'G21', 'M83 ; use relative distances for extrusion', '; filament start gcode', 'M106 P3 S150', 'M142 P1 R35 S40', 'M981 S1 P20000 ;open spaghetti detector', 'M106 S0', 'M106 P2 S0', '; CHANGE_LAYER', '; Z_HEIGHT: 0.2', '; LAYER_HEIGHT: 0.2', 'G1 E-.8 F1800', '; layer num/total_layer_count: 1/187', '; update layer progress', 'M73 L1', 'M991 S0 P0 ;notify layer change', ';_SET_FAN_SPEED_CHANGING_LAYER', 'M204 S500', '; printing object model.stl id:0 copy 0', '; start printing object, unique label id: 16', 'M624 AQAAAAAAAAA=', 'G1 X134.602 Y118.011 F30000', 'G1 Z.6', 'G1 Z.2', 'G1 E.8 F1800', '; FEATURE: Support', '; LINE_WIDTH: 0.5', 'G1 F3000', 'G1 X134.602 Y121.697 E.13727', 'G2 X135.11 Y122.766 I3.199 J-.865 E.04432', 'G1 X135.11 Y117.528 E.1951', 'G3 X135.618 Y116.858 I2.098 J1.065 E.03146', 'G1 X135.618 Y132.943 E.59908', 'G2 X136.126 Y133.095 I.675 J-1.323 E.01986']


def test_check_gcode_accepts_real_engine_lines():
    """44 consecutive lines copied from real engine output: start purge, M83, retract, travel, support, arcs."""
    body = "\n".join(REAL_LINES)
    assert slicing.check_gcode(gcode(body=body), slicing.settings_for({}))["layers"] == 348


@pytest.mark.parametrize("body", MOVE_ACCEPTS)
def test_check_gcode_accepts_safe_moves(body):
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


def test_run_slice_cleans_engine_scratch_folder(monkeypatch, tmp_path):
    slicer = tmp_path / "slicer"
    (slicer / ".orcaslicercli" / "tmp").mkdir(parents=True)
    monkeypatch.setattr(slicing, "SLICER_DIR", str(slicer))
    fake_run(monkeypatch, subprocess.CompletedProcess([], 1, stdout="", stderr="x"))
    with pytest.raises(slicing.SliceError):
        slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path))
    assert not (slicer / ".orcaslicercli").exists()


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
