"""Tests of the slicer core (slicing.py): STL preparation, option tables, G-code checks and the engine call.
The unit tests use synthetic data and a faked subprocess; the two integration tests run the real OrcaSlicer
engine and are skipped when it is not installed (bash image3d/slicer/install.sh).
Run: python -m pytest -q image3d/tests/test_slicing.py"""
import os
import struct
import subprocess
import sys
import time
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
          process="0.20mm Standard @BBL X1C", plate="Textured PEI Plate", support="0", body=None,
          temps=None, heat="M190 S55 ; set bed temperature and wait for it to be reached"):
    t = {"cool_plate_temp": 35, "textured_plate_temp": 55, "hot_plate_temp": 55}
    t.update(temps or {})
    temp_lines = []
    for key, val in t.items():
        temp_lines += ["; %s = %s" % (key, val), "; %s_initial_layer = %s" % (key, val)]
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
        *temp_lines,
        "; machine_start_gcode = " + "G28 ; home\\n" * 400,
        "; CONFIG_BLOCK_END",
        *([heat] if heat else []),
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
    body = "; FEATURE: Custom\n" + "\n".join(REAL_LINES)     # the purge line sits in the engine's Custom feature
    assert slicing.check_gcode(gcode(body=body), slicing.settings_for({}))["layers"] == 348


@pytest.mark.parametrize("body", MOVE_ACCEPTS)
def test_check_gcode_accepts_safe_moves(body):
    assert slicing.check_gcode(gcode(body=body), slicing.settings_for({}))["layers"] == 348


# ---------- A1: the bed must heat ----------
def test_incompatible_pair_is_refused():
    assert slicing.INCOMPATIBLE == {("petg_hf", "cool")}
    with pytest.raises(slicing.SliceError) as e:
        slicing.settings_for({"filament": "petg_hf", "plate": "cool"})
    assert e.value.status == 400
    assert str(e.value) == "Bambu PETG HF cannot be printed on the Cool Plate - choose another plate"
    assert slicing.settings_for({"filament": "petg_hf", "plate": "textured_pei"})["filament"].startswith("Bambu PETG HF")
    assert slicing.settings_for({"filament": "pla_basic", "plate": "cool"})["options"]["curr_bed_type"] == "Cool Plate"


@pytest.mark.parametrize("plate_name,plate_id,key", [
    ("Cool Plate", "cool", "cool_plate_temp"),
    ("Textured PEI Plate", "textured_pei", "textured_plate_temp"),
    ("High Temp Plate", "smooth_pei", "hot_plate_temp"),
])
@pytest.mark.parametrize("suffix", ["", "_initial_layer"])
def test_check_gcode_rejects_zero_bed_temperature(plate_name, plate_id, key, suffix):
    g = gcode(plate=plate_name, temps={key + suffix: 0}) if not suffix else gcode(plate=plate_name)
    if suffix:
        g = g.replace("; %s_initial_layer = " % key + ("35" if key.startswith("cool") else "55"),
                      "; %s_initial_layer = 0" % key)
    with pytest.raises(slicing.SliceError) as e:
        slicing.check_gcode(g, slicing.settings_for({"plate": plate_id}))
    assert e.value.status == 500 and "bed temperature is 0 for this plate" in str(e.value) and key in str(e.value)


def test_check_gcode_only_looks_at_the_chosen_plates_temperature():
    g = gcode(temps={"cool_plate_temp": 0, "cool_plate_temp_initial_layer": 0})   # textured plate chosen
    assert slicing.check_gcode(g, slicing.settings_for({}))["layers"] == 348


def test_check_gcode_needs_bed_temperature_in_the_config():
    g = gcode().replace("; textured_plate_temp_initial_layer = 55\n", "")
    with pytest.raises(slicing.SliceError) as e:
        slicing.check_gcode(g, slicing.settings_for({}))
    assert "textured_plate_temp_initial_layer" in str(e.value) and "missing" in str(e.value)


@pytest.mark.parametrize("heat", [None, "M190 S0", "M140 S0", "M140 S55\nM140 S0", "M104 S200", "M190 R40"])
def test_check_gcode_needs_a_bed_heat_command_before_printing(heat):
    with pytest.raises(slicing.SliceError) as e:
        slicing.check_gcode(gcode(heat=heat), slicing.settings_for({}))
    assert e.value.status == 500 and "bed temperature is 0 for this plate" in str(e.value)


def test_check_gcode_bed_heat_after_the_first_feature_is_too_late():
    with pytest.raises(slicing.SliceError) as e:
        slicing.check_gcode(gcode(heat=None, body="M190 S55\nG1 X120 Y130 E0.5"), slicing.settings_for({}))
    assert "bed temperature is 0 for this plate" in str(e.value)


@pytest.mark.parametrize("heat", ["M190 S55", "M140 S60", "M140 S55\nM190 S55 ; wait", "M140 S0\nM140 S35", "M190 S35.5"])
def test_check_gcode_accepts_bed_heat_commands(heat):
    assert slicing.check_gcode(gcode(heat=heat), slicing.settings_for({}))["layers"] == 348


# ---------- A2: exact filament, exactly one gcode entry ----------
def test_check_gcode_filament_must_match_exactly():
    for bad in ("Bambu PLA Basic @BBL P1S 0.4 nozzle copy", "x Bambu PLA Basic @BBL P1S 0.4 nozzle"):
        with pytest.raises(slicing.SliceError) as e:
            slicing.check_gcode(gcode(filament=bad), slicing.settings_for({}))
        assert "filament_settings_id" in str(e.value)


def zip_run(monkeypatch, tmp_path, entries):
    def on_start(cmd, kw):
        with zipfile.ZipFile(cmd[-2], "w") as z:
            for name, data in entries.items():
                z.writestr(name, data)
    fake_engine(monkeypatch, on_start=on_start, log='RESULT {"ok":true}\n')
    return slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path))


@pytest.mark.parametrize("entries", [
    {"Metadata/plate_1.gcode": None, "Metadata/plate_2.gcode": None},
    {"Metadata/plate_2.gcode": None},
    {"Metadata/plate_1.gcode": None, "Other/evil.gcode": None},
    {"Metadata/plate_1.gcode": None, "x/plate_1.gcode": None},
])
def test_run_slice_needs_exactly_one_gcode_entry(monkeypatch, tmp_path, entries):
    entries = {k: gcode() for k in entries}
    with pytest.raises(slicing.SliceError) as e:
        zip_run(monkeypatch, tmp_path, entries)
    assert e.value.status == 500 and "unexpected print data in the file" in str(e.value)
    assert not os.path.exists(tmp_path / "model.gcode.3mf")


def test_run_slice_other_entries_are_fine(monkeypatch, tmp_path):
    path, _ = zip_run(monkeypatch, tmp_path, {"Metadata/plate_1.gcode": gcode(), "Metadata/plate_1.gcode.md5": "x",
                                              "3D/3dmodel.model": "<m/>"})
    assert os.path.exists(path)


# ---------- A3: the excluded corner ----------
@pytest.mark.parametrize("move", ["G1 X10 Y20 E1", "G1 X17.9 Y27.9 E1", "G1 X0.5 Y0.5 E1"])
def test_check_gcode_rejects_extrusion_in_the_excluded_corner(move):
    for body in ("G1 X100 Y100 F9000\n" + move,                      # end point inside
                 "G1 X10 Y20 F9000\nG1 X100 Y100 E1"):               # start point inside
        with pytest.raises(slicing.SliceError) as e:
            slicing.check_gcode(gcode(body=body), slicing.settings_for({}))
        assert e.value.status == 500 and "extruding move in the excluded bed corner" in str(e.value)


def test_check_gcode_rejects_an_arc_that_sweeps_through_the_corner():
    body = "G1 X30 Y20 F9000\nG2 X30 Y20.5 I-10 J0 E1"      # full-ish circle around (20, 20): passes (10, 20)
    with pytest.raises(slicing.SliceError) as e:
        slicing.check_gcode(gcode(body=body), slicing.settings_for({}))
    assert "excluded bed corner" in str(e.value)


@pytest.mark.parametrize("body", [
    "G1 X18 Y40 F9000\nG1 X18 Y100 E1",              # on the edge x = 18 is outside the rectangle
    "G1 X40 Y28 F9000\nG1 X100 Y28 E1",              # on the edge y = 28
    "G1 X10 Y20 F9000\nG1 X100 Y100 E0 F9000",       # travel through the corner
    "M83\nG1 X10 Y20 F9000\nG1 X10 Y20 E-0.8",        # retract inside the corner
    "G1 X10 Y10 F9000\nG1 X12 Y10 E0 F9000",
])
def test_check_gcode_corner_accepts_edges_and_travel(body):
    assert slicing.check_gcode(gcode(body=body), slicing.settings_for({}))["layers"] == 348


def test_check_gcode_corner_is_allowed_for_the_custom_feature_only():
    purge = "G1 X10.1 Y20 F5000\nG1 X10.1 Y200 E15\nG1 X10.4 Y200 F5000\nG1 X10.4 Y20 E30"
    g = gcode(body="; FEATURE: Custom\n" + purge + "\n; FEATURE: Outer wall\nG1 X100 Y100 F9000\nG1 X120 Y100 E1")
    assert slicing.check_gcode(g, slicing.settings_for({}))["layers"] == 348
    g = gcode(body="; FEATURE: Custom\n" + purge + "\n; FEATURE: Outer wall\nG1 X10.4 Y20 F9000\nG1 X10.4 Y100 E1")
    with pytest.raises(slicing.SliceError) as e:
        slicing.check_gcode(g, slicing.settings_for({}))
    assert "excluded bed corner" in str(e.value)


# ---------- A4: floating regions ----------
ENGINE_FLOATING = ("DEBUG: noise\n[warning] Print warning: It seems object m.stl has floating regions. "
                   "Please re-orient the object or enable support generation.\n"
                   "DEBUG: Exception caught: Errors\nRESULT {\"ok\":false,\"error\":\"Slicing failed\"}\n")


@pytest.mark.parametrize("supports,message", [
    ("off", "This model has overhanging parts that would print in mid-air. Turn on Tree supports, cut a flat base, "
            "or delete loose pieces, then slice again."),
    ("tree", "The slicer could not support this model's overhanging parts. Cut a flat base or delete loose pieces, "
             "then slice again."),
])
def test_floating_regions_give_a_plain_message(monkeypatch, tmp_path, caplog, supports, message):
    fake_run(monkeypatch, subprocess.CompletedProcess([], 1, stdout=ENGINE_FLOATING, stderr="x" * 400))
    with caplog.at_level("WARNING", logger="image3d.slicing"):
        with pytest.raises(slicing.SliceError) as e:
            slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {"supports": supports}, str(tmp_path))
    assert e.value.status == 400 and str(e.value) == message
    assert "floating regions" in caplog.text and "Exception caught" in caplog.text


def test_other_engine_failures_keep_the_generic_message(monkeypatch, tmp_path, caplog):
    fake_run(monkeypatch, subprocess.CompletedProcess([], 1, stdout='DEBUG: noise\nRESULT {"ok":false,"error":"boom"}\n',
                                                      stderr=""))
    with caplog.at_level("WARNING", logger="image3d.slicing"):
        with pytest.raises(slicing.SliceError) as e:
            slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path))
    assert e.value.status == 500 and str(e.value).startswith("slicer failed: ") and "boom" in str(e.value)
    assert "boom" in caplog.text


# ---------- run_slice with a faked engine ----------
class FakePopen:
    """Stands in for subprocess.Popen: writes `log` to the stdout file it is given, can write the output file,
    exits at once with `returncode`, or never exits (hang) until kill() is called."""
    instances = []
    spec = {}

    def __init__(self, cmd, **kw):
        spec = FakePopen.spec
        self.cmd, self.kw = cmd, kw
        self.pid = 4242
        self.returncode = None
        self.killed = False
        self.hang = spec.get("hang", False)
        kw["stdout"].write(spec.get("log", "").encode())
        kw["stdout"].flush()
        if spec.get("write_output"):
            open(cmd[-2], "wb").write(b"partial")
        if spec.get("on_start"):
            spec["on_start"](cmd, kw)
        self.exit_code = spec.get("returncode", 0)
        FakePopen.instances.append(self)

    def wait(self, timeout=None):
        if self.hang and not self.killed:
            time.sleep(min(timeout or 0, 0.02))
            raise subprocess.TimeoutExpired(self.cmd, timeout)
        self.returncode = -9 if self.killed else self.exit_code
        return self.returncode

    def kill(self):
        self.killed = True


def fake_engine(monkeypatch, **spec):
    FakePopen.instances = []
    FakePopen.spec = spec
    monkeypatch.setattr(slicing.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(slicing, "POLL_S", 0.01)
    monkeypatch.setattr(slicing, "read_cgroup_memory", lambda: None)
    monkeypatch.setattr(slicing, "read_rss", lambda pid: 0)


def fake_run(monkeypatch, result=None, write_output=False):
    """result: a subprocess.CompletedProcess describing the engine's exit code and output."""
    fake_engine(monkeypatch, returncode=result.returncode, log=(result.stderr or "") + (result.stdout or ""),
                write_output=write_output)


def fake_zip_run(monkeypatch, gcode_text, **kw):
    def on_start(cmd, kw_):
        with zipfile.ZipFile(cmd[-2], "w") as z:
            z.writestr("Metadata/plate_1.gcode", gcode_text)
    fake_engine(monkeypatch, on_start=on_start, log='RESULT {"ok":true}\n', **kw)


def test_run_slice_engine_failure(monkeypatch, tmp_path):
    out = 'DEBUG: noise\nRESULT {"ok":false,"error":"boom"}\n'
    fake_run(monkeypatch, subprocess.CompletedProcess([], 1, stdout=out, stderr=""), write_output=True)
    with pytest.raises(slicing.SliceError) as e:
        slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path))
    assert e.value.status == 500 and "boom" in str(e.value)
    assert not os.path.exists(tmp_path / "model.gcode.3mf")


def test_run_slice_timeout(monkeypatch, tmp_path):
    fake_engine(monkeypatch, hang=True, write_output=True)
    with pytest.raises(slicing.SliceError) as e:
        slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path), timeout=0.2)
    assert e.value.status == 500 and "time limit" in str(e.value)
    assert FakePopen.instances[0].killed
    assert not os.path.exists(tmp_path / "model.gcode.3mf")


def test_run_slice_missing_output(monkeypatch, tmp_path):
    fake_run(monkeypatch, subprocess.CompletedProcess([], 0, stdout='RESULT {"ok":true}\n', stderr=""))
    with pytest.raises(slicing.SliceError) as e:
        slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path))
    assert e.value.status == 500


def test_run_slice_deletes_output_when_check_fails(monkeypatch, tmp_path):
    fake_zip_run(monkeypatch, gcode(nozzle="0.6"))
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
    fake_zip_run(monkeypatch, gcode())
    path, summary = slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path))
    assert path == str(tmp_path / "model.gcode.3mf") and os.path.exists(path)
    assert summary["layers"] == 348 and summary["triangles"] == 12 and summary["size_mm"] == pytest.approx([20] * 3)
    assert summary["filament"] == "PLA Basic" and summary["plate"] == "Textured PEI"



# ---------- B2: Popen, log file, watchdog ----------
def test_engine_runs_niced_with_output_in_a_log_file(monkeypatch, tmp_path):
    fake_zip_run(monkeypatch, gcode())
    slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path))
    kw = FakePopen.instances[0].kw
    assert kw["cwd"] == slicing.SLICER_DIR and kw["stderr"] == subprocess.STDOUT
    assert kw["stdout"].name == str(tmp_path / "engine.log")      # a file, not a pipe
    assert kw["preexec_fn"] is slicing._lower_priority
    assert 'RESULT {"ok":true}' in (tmp_path / "engine.log").read_text()


def test_lower_priority_survives_a_failing_nice(monkeypatch):
    def boom(n):
        raise OSError("no")
    monkeypatch.setattr(slicing.os, "nice", boom)
    slicing._lower_priority()


def test_memory_kill_from_the_cgroup_total(monkeypatch, tmp_path):
    fake_engine(monkeypatch, hang=True, write_output=True)
    mb = 1048576
    monkeypatch.setattr(slicing, "read_cgroup_memory", lambda: (480 * mb, 512 * mb))     # within 40 MB of the max
    with pytest.raises(slicing.SliceError) as e:
        slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path), timeout=30)
    assert e.value.status == 413 and "too large to slice on this server (out of memory)" in str(e.value)
    assert "0.28 mm Extra Draft" in str(e.value)
    assert FakePopen.instances[0].killed and not os.path.exists(tmp_path / "model.gcode.3mf")


def test_cgroup_below_the_margin_is_fine_and_margin_is_configurable(monkeypatch):
    mb = 1048576
    monkeypatch.setattr(slicing, "read_cgroup_memory", lambda: (400 * mb, 512 * mb))
    assert slicing.memory_exceeded(1) is False
    monkeypatch.setenv("SLICE_MEM_MARGIN_MB", "200")
    assert slicing.memory_exceeded(1) is True


def test_rss_fallback_without_a_cgroup_limit(monkeypatch, tmp_path):
    fake_engine(monkeypatch, hang=True)
    mb = 1048576
    rss = {4242: 400 * mb, None: 80 * mb}
    monkeypatch.setattr(slicing, "read_rss", lambda pid: rss[pid])
    with pytest.raises(slicing.SliceError) as e:
        slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path), timeout=30)
    assert e.value.status == 413
    rss[4242] = 300 * mb
    assert slicing.memory_exceeded(4242) is False
    monkeypatch.setenv("SLICE_MEM_LIMIT_MB", "350")
    assert slicing.memory_exceeded(4242) is True


def test_cgroup_reader(monkeypatch, tmp_path):
    monkeypatch.setattr(slicing, "CGROUP_DIR", str(tmp_path))
    assert slicing.read_cgroup_memory() is None                     # files absent
    (tmp_path / "memory.max").write_text("max\n")
    (tmp_path / "memory.current").write_text("123\n")
    assert slicing.read_cgroup_memory() is None                     # unlimited
    (tmp_path / "memory.max").write_text("536870912\n")
    assert slicing.read_cgroup_memory() == (123, 536870912)


def test_read_rss_of_this_process():
    assert slicing.read_rss(None) > 1_000_000
    assert slicing.read_rss(2 ** 22 + 12345) == 0


def test_normal_exit_still_parses_result(monkeypatch, tmp_path):
    fake_run(monkeypatch, subprocess.CompletedProcess([], 1, stdout='x\nRESULT {"ok":false,"error":"boom"}\n', stderr=""))
    with pytest.raises(slicing.SliceError) as e:
        slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path))
    assert "boom" in str(e.value)


def test_engine_start_failure(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise FileNotFoundError("node")
    monkeypatch.setattr(slicing.subprocess, "Popen", boom)
    with pytest.raises(slicing.SliceError) as e:
        slicing.run_slice(stl_bytes(box_tris(20, 20, 20, 0, 0, 0)), {}, str(tmp_path))
    assert "could not be started" in str(e.value)


# ---------- B1: lean prepare_stl ----------
def big_stl(n=150_000):
    one = struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 10, 0, 0, 0, 10, 0, 0)
    body = bytearray(one * n)
    for i in range(0, n, 997):                  # vary a few coordinates so the box is not trivial
        struct.pack_into("<3f", body, 50 * i + 12, -20 + (i % 40), 5, 30)
    return b"x" * 80 + struct.pack("<I", n) + bytes(body)


def test_prepare_stl_is_memory_lean():
    import tracemalloc
    data = big_stl()
    tracemalloc.start()
    base = tracemalloc.get_traced_memory()[0]
    out, info = slicing.prepare_stl(data)
    peak = tracemalloc.get_traced_memory()[1] - base
    tracemalloc.stop()
    assert info["triangles"] == 150_000 and len(out) == len(data)
    assert peak < 40 * 1048576, peak
    assert min(struct.unpack_from("<12fH", out, 84 + 50 * k)[5] for k in range(0, 150_000, 997)) >= 0


def test_prepare_stl_chunk_edges_are_exact():
    for count in (1, slicing._CHUNK - 1, slicing._CHUNK, slicing._CHUNK + 1, 2 * slicing._CHUNK + 3):
        tris = [((i % 7, 0, 1), (i % 7 + 1, 2, 3), (i % 5, 4, 8)) for i in range(count)]
        out, info = slicing.prepare_stl(stl_bytes(tris))
        n, (xs, ys, zs) = read_stl(out)
        assert n == count and min(zs) == pytest.approx(0) and max(zs) == pytest.approx(7)
        assert (min(xs) + max(xs)) / 2 == pytest.approx(128) and (min(ys) + max(ys)) / 2 == pytest.approx(128)


def test_prepare_stl_keeps_normals_and_attributes():
    data = bytearray(stl_bytes(box_tris(10, 10, 10, 0, 0, 0)))
    struct.pack_into("<3f", data, 84, 0.25, 0.5, 0.75)
    struct.pack_into("<H", data, 84 + 48, 777)
    out, _ = slicing.prepare_stl(bytes(data))
    assert struct.unpack_from("<3f", out, 84) == (0.25, 0.5, 0.75) and struct.unpack_from("<H", out, 132)[0] == 777


def test_non_finite_in_a_later_chunk_is_found():
    tris = [((0, 0, 0), (1, 0, 0), (0, 1, 0))] * (slicing._CHUNK + 5)
    data = bytearray(stl_bytes(tris))
    struct.pack_into("<f", data, 84 + 50 * (slicing._CHUNK + 2) + 12, float("nan"))
    with pytest.raises(slicing.SliceError):
        slicing.prepare_stl(bytes(data))


def test_run_slice_prepared_skips_parsing_and_drops_the_stl(monkeypatch, tmp_path):
    import tracemalloc
    calls = []
    real = slicing.prepare_stl
    monkeypatch.setattr(slicing, "prepare_stl", lambda d: calls.append(1) or real(d))
    prepared, info = real(big_stl(20_000))
    seen = {}

    def on_start(cmd, kw):
        seen["now"] = tracemalloc.get_traced_memory()[0]
        with zipfile.ZipFile(cmd[-2], "w") as z:
            z.writestr("Metadata/plate_1.gcode", gcode())
    fake_engine(monkeypatch, on_start=on_start, log='RESULT {"ok":true}\n')
    tracemalloc.start()
    base = tracemalloc.get_traced_memory()[0]
    _, summary = slicing.run_slice(prepared, {}, str(tmp_path), prepared=info)
    tracemalloc.stop()
    assert calls == [] and summary["triangles"] == 20_000
    assert (tmp_path / "model.stl").read_bytes() == prepared
    # the caller still holds `prepared` (1 MB); the function itself must not add another copy
    assert seen["now"] - base < 300_000


def test_run_slice_without_prepared_parses_once_and_frees_the_upload(monkeypatch, tmp_path):
    import tracemalloc
    seen = {}

    def on_start(cmd, kw):
        seen["now"] = tracemalloc.get_traced_memory()[0]
        with zipfile.ZipFile(cmd[-2], "w") as z:
            z.writestr("Metadata/plate_1.gcode", gcode())
    fake_engine(monkeypatch, on_start=on_start, log='RESULT {"ok":true}\n')
    tracemalloc.start()
    base = tracemalloc.get_traced_memory()[0]
    slicing.run_slice(big_stl(20_000), {}, str(tmp_path))     # nothing else holds the upload or the prepared copy
    tracemalloc.stop()
    assert seen["now"] - base < 300_000, seen["now"] - base


# ---------- available ----------
def test_available_false_without_engine(monkeypatch, tmp_path):
    monkeypatch.setattr(slicing, "SLICER_DIR", str(tmp_path))
    assert slicing.available() is False
    assert slicing.node_path() == "node" or slicing.node_path().startswith(str(tmp_path))


# ---------- the real engine ----------
@pytest.fixture(autouse=True)
def _roomy_memory_guard_for_real_runs(request, monkeypatch):
    """The real engine runs inside a big pytest process here, so the RSS fallback of the watchdog (470 MB on the
    free instance) would fire; the guard itself is tested with fakes above."""
    if request.node.name.startswith("test_real"):
        monkeypatch.setenv("SLICE_MEM_LIMIT_MB", "8000")


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


TIP = [((0, 0, 0), (10, 0, 10), (0, 10, 10)), ((0, 0, 0), (0, 10, 10), (-10, 0, 10)),
       ((0, 0, 0), (-10, 0, 10), (0, -10, 10)), ((0, 0, 0), (0, -10, 10), (10, 0, 10)),
       ((0, 0, 20), (0, 10, 10), (10, 0, 10)), ((0, 0, 20), (-10, 0, 10), (0, 10, 10)),
       ((0, 0, 20), (0, -10, 10), (-10, 0, 10)), ((0, 0, 20), (10, 0, 10), (0, -10, 10))]


@needs_engine
def test_real_engine_floating_regions_message(tmp_path):
    """An octahedron standing on one corner: the engine warns 'floating regions' and fails."""
    with pytest.raises(slicing.SliceError) as e:
        slicing.run_slice(stl_bytes(TIP), {"supports": "off"}, str(tmp_path))
    assert e.value.status == 400 and str(e.value).startswith("This model has overhanging parts")


@needs_engine
def test_real_slice_pla_basic_on_cool_plate_passes(tmp_path):
    path, summary = slicing.run_slice(stl_bytes(box_tris(20, 20, 20, -10, -10, 0)), {"plate": "cool"}, str(tmp_path))
    assert summary["plate"] == "Cool Plate" and summary["filament_g"] > 0
    assert "M190 S35" in read_gcode(path)


@needs_engine
def test_real_engine_refuses_petg_on_cool_plate_before_slicing(tmp_path):
    with pytest.raises(slicing.SliceError) as e:
        slicing.run_slice(stl_bytes(box_tris(20, 20, 20, -10, -10, 0)), {"filament": "petg_hf", "plate": "cool"},
                          str(tmp_path))
    assert e.value.status == 400 and "cannot be printed on the Cool Plate" in str(e.value)
    assert not os.path.exists(tmp_path / "model.stl")
