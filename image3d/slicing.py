"""Slice for P1S core: turns a binary STL into a Bambu Lab P1S print file (.gcode.3mf) with the OrcaSlicer engine.

The engine runs in a separate Node process (slicer/slice_job.js, installed by slicer/install.sh). Nothing here
raises at import when Node, the engine or the profiles are missing: available() reports it.
Every result is checked (printer, nozzle, filament, quality, plate, supports, bed bounds) before it is returned.
"""
import json
import math
import os
import re
import struct
import shutil
import subprocess
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SLICER_DIR = os.path.join(HERE, "slicer")  # tests replace this
MAX_TRIANGLES = 150_000
BED_MM = 256
PRINTER = "Bambu Lab P1S 0.4 nozzle"
TIMEOUT_S = 900
GCODE_ENTRY = "Metadata/plate_1.gcode"
OUTPUT_NAME = "model.gcode.3mf"
ENGINE_TAIL = 300


class SliceError(ValueError):
    """A slice request or result that cannot be used. status is the HTTP status the server answers with."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def _row(id_, label, profile):
    return {"id": id_, "label": label, "profile": profile}


# First entry of each list is the default.
OPTIONS = {
    "filament": [
        _row("pla_basic", "PLA Basic", "Bambu PLA Basic @BBL P1S 0.4 nozzle"),
        _row("pla_silk_plus", "PLA Silk+", "Bambu PLA Silk+ @BBL P1S 0.4 nozzle"),
        _row("pla_matte", "PLA Matte", "Bambu PLA Matte @BBL P1S 0.4 nozzle"),
        _row("petg_hf", "PETG HF", "Bambu PETG HF @BBL P1S 0.4 nozzle"),
    ],
    "quality": [
        _row("standard", "0.20 mm Standard", "0.20mm Standard @BBL X1C"),
        _row("fine", "0.16 mm Optimal", "0.16mm Optimal @BBL X1C"),
        _row("draft", "0.28 mm Extra Draft", "0.28mm Extra Draft @BBL X1C"),
    ],
    "plate": [
        _row("textured_pei", "Textured PEI", "Textured PEI Plate"),
        _row("cool", "Cool Plate", "Cool Plate"),
        _row("smooth_pei", "Smooth PEI (High Temp)", "High Temp Plate"),
    ],
    "supports": [
        _row("off", "Off", "off"),
        _row("tree", "Tree (auto)", "tree(auto)"),
    ],
}
# Engine option values must be strings: a numeric 1 is silently ignored.
SUPPORT_OPTIONS = {
    "off": {"enable_support": "0"},
    "tree": {"enable_support": "1", "support_type": "tree(auto)"},
}


# ---------- engine presence ----------
def node_path():
    local = os.path.join(SLICER_DIR, ".node", "bin", "node")
    return local if os.path.exists(local) else "node"


def _node_found():
    path = node_path()
    if os.path.sep in path:
        return os.access(path, os.X_OK)
    return any(os.access(os.path.join(d, path), os.X_OK) for d in os.environ.get("PATH", "").split(os.pathsep) if d)


def available():
    return (_node_found()
            and os.path.isdir(os.path.join(SLICER_DIR, "node_modules", "orcaslicer-addon"))
            and os.path.isfile(os.path.join(SLICER_DIR, "resources", "profiles", "BBL.json")))


# ---------- STL ----------
def prepare_stl(data):
    """Checks a binary STL and moves it to the middle of the bed (XY centre 128, 128) with its lowest point at z = 0
    (the engine does not centre the model itself). Returns (stl bytes, {"triangles", "size_mm"})."""
    if len(data) < 84:
        raise SliceError(400, "not a binary STL file")
    n = struct.unpack_from("<I", data, 80)[0]
    if len(data) < 84 + 50 * n:
        raise SliceError(400, "not a binary STL file, or it is truncated")
    if n == 0:
        raise SliceError(400, "the STL has no triangles")
    if n > MAX_TRIANGLES:
        raise SliceError(413, "model has %d triangles; the limit is %d" % (n, MAX_TRIANGLES))
    rows = list(struct.iter_unpack("<12fH", memoryview(data)[84:84 + 50 * n]))
    # NaN never wins a min/max comparison, so every vertex is tested (the sum is non-finite if any coordinate is)
    if not all(math.isfinite(sum(r[3:12])) for r in rows):
        raise SliceError(400, "the STL contains invalid coordinates")
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for r in rows:
        for v in (3, 6, 9):
            for a in range(3):
                c = r[v + a]
                if c < lo[a]:
                    lo[a] = c
                if c > hi[a]:
                    hi[a] = c
    size = [hi[a] - lo[a] for a in range(3)]
    if max(size) > BED_MM:
        raise SliceError(400, "model is %.0f x %.0f x %.0f mm and does not fit the %d mm bed" % (*size, BED_MM))
    shift = (BED_MM / 2 - (lo[0] + hi[0]) / 2, BED_MM / 2 - (lo[1] + hi[1]) / 2, -lo[2])
    out = bytearray(data[:84])
    pack = struct.Struct("<12fH").pack
    for r in rows:
        v = list(r)
        for k in (3, 6, 9):
            for a in range(3):
                v[k + a] += shift[a]
        out += pack(*v)
    return bytes(out), {"triangles": n, "size_mm": [round(s, 2) for s in size]}


# ---------- settings ----------
def settings_for(choice):
    """Option ids ({"filament","quality","plate","supports"}, missing = default) -> what the engine is given."""
    picked = {}
    for key, rows in OPTIONS.items():
        want = (choice or {}).get(key) or rows[0]["id"]
        row = next((r for r in rows if r["id"] == want), None)
        if row is None:
            raise SliceError(400, "unknown %s option: %s" % (key, want))
        picked[key] = row
    options = {"curr_bed_type": picked["plate"]["profile"]}
    options.update(SUPPORT_OPTIONS[picked["supports"]["id"]])
    return {"printer": PRINTER, "filament": picked["filament"]["profile"], "process": picked["quality"]["profile"],
            "options": options}


def _labels(choice):
    out = {}
    for key, rows in OPTIONS.items():
        want = (choice or {}).get(key) or rows[0]["id"]
        out[key] = next(r["label"] for r in rows if r["id"] == want)
    return out


# ---------- G-code check ----------
_CONFIG = re.compile(r"^; (\w+) = (.*)$")
_HEAD = re.compile(r"(?:N\d+\s*)?([GM])\s*0*(\d+)(\.\d+)?")
_WORD = re.compile(r"\s*([A-Z])\s*([+-]?(?:\d+\.?\d*|\.\d+))?")


def _config(lines):
    """First value of each '; key = value' line, from the config block when there is one."""
    start = next((i for i, ln in enumerate(lines) if ln.startswith("; CONFIG_BLOCK_START")), -1)
    cfg = {}
    for ln in lines[start + 1:]:
        if ln.startswith("; CONFIG_BLOCK_END"):
            break
        m = _CONFIG.match(ln)
        if m and m.group(1) not in cfg:
            cfg[m.group(1)] = m.group(2).strip().strip('"')
    return cfg


def _words(text, n):
    """'X10 y-5.5 E+1' -> {"X": 10.0, "Y": -5.5, "E": 1.0}. Anything unreadable in a move line -> SliceError."""
    out, pos = {}, 0
    while pos < len(text):
        m = _WORD.match(text, pos)
        if not m or m.end() == pos or (m.group(2) is None and m.group(1) in "XYEIJR"):
            raise SliceError(500, "slice check failed: unreadable move (line %d)" % n)
        if m.group(2) is not None:
            out[m.group(1)] = float(m.group(2))
        pos = m.end()
    return out


def _arc_extremes(x, y, nx, ny, cx, cy, ccw):
    """Left/right/top/bottom-most points an arc from (x, y) to (nx, ny) around (cx, cy) really sweeps through
    (G3 = counter-clockwise, G2 = clockwise; start = end means a full circle)."""
    r = max(math.hypot(x - cx, y - cy), math.hypot(nx - cx, ny - cy))
    a0, a1 = math.atan2(y - cy, x - cx), math.atan2(ny - cy, nx - cx)
    full = abs(nx - x) < 1e-6 and abs(ny - y) < 1e-6
    sweep = 2 * math.pi if full else ((a1 - a0) if ccw else (a0 - a1)) % (2 * math.pi)
    out = []
    for k, (dx, dy) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):
        t = k * math.pi / 2
        if ((t - a0) if ccw else (a0 - t)) % (2 * math.pi) <= sweep:
            out.append((cx + r * dx, cy + r * dy))
    return out


def _check_moves(lines):
    """Walks the whole G-code keeping the X/Y position, G90/G91 and the extruder mode. From the first '; FEATURE:'
    line on, every extruding move must stay inside the bed: the start and end of a line, and for an arc the whole
    part of the circle it sweeps (the start sequence before that legitimately parks and purges near the edges)."""
    x = y = None            # unknown until a move or G92 sets them; G28 forgets them
    rel_xy = False          # G91
    rel_e = False           # M83 (G91 makes E relative too); the firmware starts in absolute mode
    last_e = 0.0            # absolute extruder position (M82), reset by G92 E
    printing = False
    for n, ln in enumerate(lines, 1):
        if not printing and ln.startswith("; FEATURE:"):
            printing = True
            continue
        text = ln.split(";", 1)[0].strip().upper()
        head = _HEAD.match(text) if text else None
        if not head:
            continue
        kind, code = head.group(1), int(head.group(2))
        if kind == "M":
            if code == 82:
                rel_e = False
            elif code == 83:
                rel_e = True
            continue
        if code == 90 or code == 91:
            rel_xy = code == 91
            continue
        if code == 28:
            x = y = None
            continue
        if code not in (0, 1, 2, 3, 92):
            continue
        if head.group(3) and code != 92:
            raise SliceError(500, "slice check failed: unreadable move (line %d)" % n)
        w = _words(text[head.end():], n)
        if code == 92:   # set position
            x = w.get("X", x)
            y = w.get("Y", y)
            last_e = w.get("E", last_e)
            continue
        nx, ny = x, y
        if "X" in w:
            nx = w["X"] if not rel_xy else (x + w["X"] if x is not None else None)
        if "Y" in w:
            ny = w["Y"] if not rel_xy else (y + w["Y"] if y is not None else None)
        extruding = False
        if "E" in w:
            if rel_e or rel_xy:
                extruding = w["E"] > 0
            else:
                extruding = w["E"] > last_e
                last_e = w["E"]
        if printing and extruding:
            if x is None or y is None:
                raise SliceError(500, "slice check failed: extruding move from an unknown position (line %d)" % n)
            points = [(x, y), (nx, ny)]
            if code in (2, 3):
                if "I" not in w and "J" not in w:
                    raise SliceError(500, "slice check failed: arc cannot be bounded (line %d)" % n)
                points += _arc_extremes(x, y, nx, ny, x + w.get("I", 0.0), y + w.get("J", 0.0), code == 3)
            for px, py in points:
                if not (0 <= px <= BED_MM and 0 <= py <= BED_MM):
                    raise SliceError(500, "slice check failed: extruding move outside the bed (X%.1f Y%.1f, line %d)"
                                     % (px, py, n))
        x, y = nx, ny


def check_gcode(gcode, settings):
    """Refuses a result that does not match what was asked for or that prints off the bed.
    Returns {"print_time", "filament_g", "layers"}."""
    lines = gcode.splitlines()
    cfg = _config(lines)

    def need(key):
        if key not in cfg:
            raise SliceError(500, "slice check failed: %s missing from the G-code" % key)
        return cfg[key]

    def fail(key, got, want):
        raise SliceError(500, "slice check failed: %s is '%s', expected '%s'" % (key, got[:80], want))

    if need("printer_model") != "Bambu Lab P1S":
        fail("printer_model", cfg["printer_model"], "Bambu Lab P1S")
    if not need("nozzle_diameter").startswith("0.4"):
        fail("nozzle_diameter", cfg["nozzle_diameter"], "0.4")
    if settings["filament"] not in need("filament_settings_id"):
        fail("filament_settings_id", cfg["filament_settings_id"], settings["filament"])
    if need("print_settings_id") != settings["process"]:
        fail("print_settings_id", cfg["print_settings_id"], settings["process"])
    if need("curr_bed_type") != settings["options"]["curr_bed_type"]:
        fail("curr_bed_type", cfg["curr_bed_type"], settings["options"]["curr_bed_type"])
    if need("enable_support") != settings["options"]["enable_support"]:
        fail("enable_support", cfg["enable_support"], settings["options"]["enable_support"])

    _check_moves(lines)

    time_m = re.search(r"^; model printing time: [^;\n]*; total estimated time: ([^\n]+)$", gcode, re.M)
    grams_m = re.search(r"^; filament used \[g\] = (-?\d+\.?\d*)", gcode, re.M)
    layers_m = re.search(r"^; total layer number: (\d+)", gcode, re.M)
    if not (time_m and grams_m and layers_m):
        raise SliceError(500, "slice check failed: print time, filament or layer count missing from the G-code")
    return {"print_time": time_m.group(1).strip(), "filament_g": float(grams_m.group(1)),
            "layers": int(layers_m.group(1))}


# ---------- running the engine ----------
def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def run_slice(stl, choice, workdir, timeout=TIMEOUT_S):
    """Slices an uploaded binary STL. Returns (path of workdir/model.gcode.3mf, summary). Raises SliceError;
    the output file never survives a failure."""
    prepared, info = prepare_stl(stl)
    settings = settings_for(choice)
    src = os.path.join(workdir, "model.stl")
    out = os.path.join(workdir, OUTPUT_NAME)
    cfg_path = os.path.join(workdir, "settings.json")
    with open(src, "wb") as f:
        f.write(prepared)
    with open(cfg_path, "w") as f:
        json.dump(settings, f)
    _remove(out)
    try:
        try:
            proc = subprocess.run([node_path(), os.path.join(SLICER_DIR, "slice_job.js"), src, out, cfg_path],
                                  cwd=SLICER_DIR, capture_output=True, text=True, errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            raise SliceError(500, "slicing stopped: it went over the %d s time limit" % timeout)
        except OSError as e:
            raise SliceError(500, "the slicer could not be started: %s" % e)
        # stderr first so the RESULT line (last line of stdout) stays at the end
        output = ((proc.stderr or "") + (proc.stdout or "")).strip()
        result = None
        for ln in reversed((proc.stdout or "").splitlines()):
            if ln.startswith("RESULT "):
                try:
                    result = json.loads(ln[7:])
                except ValueError:
                    pass
                break
        if proc.returncode != 0 or (result is not None and not result.get("ok")):
            raise SliceError(500, "slicer failed: " + output[-ENGINE_TAIL:])
        if not os.path.exists(out):
            raise SliceError(500, "slicer produced no file: " + output[-ENGINE_TAIL:])
        try:
            with zipfile.ZipFile(out) as z:
                gcode = z.read(GCODE_ENTRY).decode("utf-8", "replace")
        except (zipfile.BadZipFile, KeyError) as e:
            raise SliceError(500, "slicer output is not a print file (%s)" % e)
        summary = check_gcode(gcode, settings)
        summary.update(info)
        summary.update(_labels(choice))
        return out, summary
    except BaseException:
        _remove(out)
        raise
    finally:
        shutil.rmtree(os.path.join(SLICER_DIR, ".orcaslicercli"), ignore_errors=True)  # engine scratch files
