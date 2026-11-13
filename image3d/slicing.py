"""Slice for P1S core: turns a binary STL into a Bambu Lab P1S print file (.gcode.3mf) with the OrcaSlicer engine.

The engine runs in a separate Node process (slicer/slice_job.js, installed by slicer/install.sh). Nothing here
raises at import when Node, the engine or the profiles are missing: available() reports it.
Every result is checked (printer, nozzle, filament, quality, plate, supports, bed bounds) before it is returned.
"""
import json
import logging
import math
import os
import re
import struct
import shutil
import subprocess
import time
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
EXCLUDED_CORNER = (18.0, 28.0)   # P1S bed_exclude_area: front-left, x 0-18 mm by y 0-28 mm
BED_TEMP_KEYS = {"Cool Plate": "cool_plate_temp", "Textured PEI Plate": "textured_plate_temp",
                 "High Temp Plate": "hot_plate_temp"}
log = logging.getLogger("image3d.slicing")


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
# (filament id, plate id) pairs Bambu's profile does not support: the engine slices them anyway, with a bed that never
# heats (cool_plate_temp = 0). Checked against the real profiles: every other pair has a bed temperature above 0.
INCOMPATIBLE = {("petg_hf", "cool")}
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


def _install_commit():
    """The OrcaSlicer commit install.sh recorded after its smoke slice worked, or None."""
    try:
        with open(os.path.join(SLICER_DIR, ".install_ok")) as f:
            for ln in f:
                if ln.startswith("orca_commit="):
                    return ln.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def available():
    try:
        with open(os.path.join(SLICER_DIR, "ORCA_COMMIT")) as f:
            wanted = f.read().strip()
    except OSError:
        return False
    return (bool(wanted) and _install_commit() == wanted
            and _node_found()
            and os.path.isdir(os.path.join(SLICER_DIR, "node_modules", "orcaslicer-addon"))
            and os.path.isfile(os.path.join(SLICER_DIR, "resources", "profiles", "BBL.json")))


# ---------- STL ----------
_CHUNK = 2000   # records per struct call: a few hundred KB of temporary floats, not one Python object per vertex


def prepare_stl(data):
    """Checks a binary STL and moves it to the middle of the bed (XY centre 128, 128) with its lowest point at z = 0
    (the engine does not centre the model itself). Returns (stl bytes, {"triangles", "size_mm"}).
    Memory-lean: two passes over the records in chunks, the translated copy is built in one bytearray."""
    if len(data) < 84:
        raise SliceError(400, "not a binary STL file")
    n = struct.unpack_from("<I", data, 80)[0]
    if len(data) < 84 + 50 * n:
        raise SliceError(400, "not a binary STL file, or it is truncated")
    if n == 0:
        raise SliceError(400, "the STL has no triangles")
    if n > MAX_TRIANGLES:
        raise SliceError(413, "model has %d triangles; the limit is %d" % (n, MAX_TRIANGLES))
    view = memoryview(data)
    full = struct.Struct("<" + "12fH" * _CHUNK)
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    chunks = []          # (first record, record count, Struct)
    for first in range(0, n, _CHUNK):
        count = min(_CHUNK, n - first)
        chunks.append((first, count, full if count == _CHUNK else struct.Struct("<" + "12fH" * count)))
    for first, count, st in chunks:
        vals = st.unpack_from(view, 84 + 50 * first)
        for a in range(3):
            col = vals[3 + a::13] + vals[6 + a::13] + vals[9 + a::13]
            # NaN never wins a min/max comparison, but it makes the sum non-finite (so does an infinity)
            if not math.isfinite(sum(col)):
                raise SliceError(400, "the STL contains invalid coordinates")
            lo[a] = min(lo[a], min(col))
            hi[a] = max(hi[a], max(col))
    size = [hi[a] - lo[a] for a in range(3)]
    if max(size) > BED_MM:
        raise SliceError(400, "model is %.0f x %.0f x %.0f mm and does not fit the %d mm bed" % (*size, BED_MM))
    shift = (BED_MM / 2 - (lo[0] + hi[0]) / 2, BED_MM / 2 - (lo[1] + hi[1]) / 2, -lo[2])
    out = bytearray(84 + 50 * n)
    out[:84] = view[:84]
    for first, count, st in chunks:
        off = 84 + 50 * first
        vals = list(st.unpack_from(view, off))
        for a in range(3):
            for v in (3, 6, 9):
                vals[v + a::13] = [c + shift[a] for c in vals[v + a::13]]
        st.pack_into(out, off, *vals)
        del vals
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
    if (picked["filament"]["id"], picked["plate"]["id"]) in INCOMPATIBLE:
        raise SliceError(400, "Bambu %s cannot be printed on the %s - choose another plate"
                         % (picked["filament"]["label"], picked["plate"]["label"]))
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
_COMMAND = re.compile(r"(?<![A-Z0-9_.])[GM]\s*\d+(?![_0-9.])")
_AXIS = re.compile(r"[XYE]")
_NONCOMMAND_AXIS = re.compile(r"[XYEIJG]")         # a line that is not a G/M command must not move anything
_UNSUPPORTED = {"G": {10, 18, 19, 53, 54, 55, 56, 57, 58, 59}, "M": {206, 428}}   # planes, offsets, coordinate systems
_MODAL_DECIMAL = {0, 1, 2, 3, 90, 91, 92}         # G90.1, G91.1, G92.1, G1.1 ... change how moves are read
_GLUED = re.compile(r"[0-9.][GM]")                # a G/M word stuck to the number before it
_NUMBER_JOIN = re.compile(r"[0-9.][EX][0-9+\-.]")    # 3E2, 0X1F: read by strtof-style parsers as one number
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
    if _NUMBER_JOIN.search(text) or _GLUED.search(text):
        raise SliceError(500, "slice check failed: unreadable move (line %d)" % n)
    while pos < len(text):
        m = _WORD.match(text, pos)
        if not m or m.end() == pos or (m.group(2) is None and m.group(1) in "XYEIJR"):
            raise SliceError(500, "slice check failed: unreadable move (line %d)" % n)
        if m.group(2) is not None:
            if m.group(1) in out and m.group(1) in "XYEIJR":
                raise SliceError(500, "slice check failed: unreadable move (line %d)" % n)
            out[m.group(1)] = float(m.group(2))
        pos = m.end()
    return out


def _arc_extremes(x, y, nx, ny, cx, cy, ccw):
    """Left/right/top/bottom-most points an arc from (x, y) to (nx, ny) around (cx, cy) can reach, using the larger
    of the start and end radius. G3 = counter-clockwise, G2 = clockwise. A sweep of (nearly) zero is what a
    controller runs as a full circle, so it is bounded as one."""
    r = max(math.hypot(x - cx, y - cy), math.hypot(nx - cx, ny - cy))
    a0, a1 = math.atan2(y - cy, x - cx), math.atan2(ny - cy, nx - cx)
    sweep = ((a1 - a0) if ccw else (a0 - a1)) % (2 * math.pi)
    if sweep < 1e-9 or sweep > 2 * math.pi - 1e-9:
        sweep = 2 * math.pi
    out = []
    for k, (dx, dy) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):
        t = k * math.pi / 2
        if ((t - a0) if ccw else (a0 - t)) % (2 * math.pi) <= sweep:
            out.append((cx + r * dx, cy + r * dy))
    return out


def _check_moves(lines):
    """Walks the whole G-code keeping the X/Y position, G90/G91, the extruder mode and the extruder position. From the
    first '; FEATURE:' line on, every extruding move must stay inside the bed: the start and end of a line, and for
    an arc the part of the circle it sweeps (the start sequence before that legitimately parks and purges near the
    edges). It fails closed: anything outside the small grammar the engine writes (other motion commands, position
    resets, several commands on a line, exponent numbers) is an error once printing has started."""
    x = y = None            # unknown until a move sets them; G28 / G29 forget them
    rel_xy = False          # G91
    e_mode = None           # "abs" (M82), "rel" (M83); None until declared (the engine's purge comes before M83)
    e_pos = 0.0             # running extruder position in both modes, reset by G92 E
    printing = False
    bed_target = 0.0        # last M140 / M190 S value before the first feature
    feature = ""            # name of the current "; FEATURE:" section
    modal_ok = True         # False once a plane change, offset or modal G code has been seen before printing

    def bad(what, n):
        raise SliceError(500, "slice check failed: %s (line %d)" % (what, n))

    for n, ln in enumerate(lines, 1):
        if ln.startswith("; FEATURE:"):
            feature = ln[len("; FEATURE:"):].strip()
            if not printing:
                if bed_target <= 0:
                    raise SliceError(500, "slice check failed: bed temperature is 0 for this plate "
                                          "(no bed-heat command before printing starts)")
                printing = True
            continue
        text = ln.split(";", 1)[0].strip().upper()
        head = _HEAD.match(text) if text else None
        if not head:
            if text and _NONCOMMAND_AXIS.search(text):      # "X300 E1", "T0 G1 X300": not a command we understand
                if printing:
                    bad("unsupported move", n)
                x = y = None
                modal_ok = False
            continue
        if len(_COMMAND.findall(text)) > 1:          # e.g. "G53 G1 X300", "M83 G1 X300"
            if printing:
                bad("unsupported move", n)
            x = y = None
            continue
        kind, code = head.group(1), int(head.group(2))
        if code in _UNSUPPORTED[kind] or (kind == "G" and head.group(3) and code in _MODAL_DECIMAL):
            if printing:
                bad("unsupported move", n)
            x = y = None
            modal_ok = False
            continue
        if kind == "M":
            if code in (140, 190) and not printing:
                sm = re.search(r"S\s*([+-]?(?:\d+\.?\d*|\.\d+))", text[head.end():])
                bed_target = float(sm.group(1)) if sm else bed_target
            if code == 82:
                e_mode = "abs"
            elif code == 83:
                e_mode = "rel"
            continue
        args = text[head.end():]
        if code in (90, 91):
            rel_xy = code == 91
            continue
        if code in (28, 29) and not _AXIS.search(args):
            x = y = None
            continue
        if code not in (0, 1, 2, 3, 92):
            if code != 4 and _AXIS.search(args):     # G5, G53, G28 X ...: could move anywhere
                if printing:
                    bad("unsupported move", n)
                x = y = None
            continue
        w = _words(args, n)
        if code == 92:   # set position
            if "X" in w or "Y" in w:
                if printing:
                    bad("position reset not allowed", n)
                x = y = None
            if "E" in w:
                e_pos = w["E"]
            continue
        nx, ny = x, y
        if "X" in w:
            nx = w["X"] if not rel_xy else (x + w["X"] if x is not None else None)
        if "Y" in w:
            ny = w["Y"] if not rel_xy else (y + w["Y"] if y is not None else None)
        extruding = False
        if "E" in w:
            e = w["E"]
            if e_mode == "rel":
                extruding = e > 0
                e_pos += e
            else:
                # absolute, or ambiguous (undeclared mode, or G91): extruding if either reading says so
                extruding = e > e_pos if e_mode == "abs" and not rel_xy else (e > 0 or e > e_pos)
                e_pos = e
        if printing and extruding:
            if not modal_ok:
                bad("unsupported move", n)
            if x is None or y is None:
                bad("extruding move from an unknown position", n)
            points = [(x, y), (nx, ny)]
            if code in (2, 3):
                if "I" not in w and "J" not in w:
                    bad("arc cannot be bounded", n)
                points += _arc_extremes(x, y, nx, ny, x + w.get("I", 0.0), y + w.get("J", 0.0), code == 3)
            for px, py in points:
                if not (0 <= px <= BED_MM and 0 <= py <= BED_MM):
                    bad("extruding move outside the bed (X%.1f Y%.1f)" % (px, py), n)
                # the engine's own purge line (feature Custom) runs through this corner; nothing else may
                if feature != "Custom" and px < EXCLUDED_CORNER[0] and py < EXCLUDED_CORNER[1]:
                    bad("extruding move in the excluded bed corner (X%.1f Y%.1f)" % (px, py), n)
        x, y = nx, ny
    if not printing:
        raise SliceError(500, "slice check failed: no print moves found")


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
    if need("filament_settings_id") != settings["filament"]:
        fail("filament_settings_id", cfg["filament_settings_id"], settings["filament"])
    if need("print_settings_id") != settings["process"]:
        fail("print_settings_id", cfg["print_settings_id"], settings["process"])
    if need("curr_bed_type") != settings["options"]["curr_bed_type"]:
        fail("curr_bed_type", cfg["curr_bed_type"], settings["options"]["curr_bed_type"])
    if need("enable_support") != settings["options"]["enable_support"]:
        fail("enable_support", cfg["enable_support"], settings["options"]["enable_support"])

    temp_key = BED_TEMP_KEYS[settings["options"]["curr_bed_type"]]
    for key in (temp_key, temp_key + "_initial_layer"):
        raw = need(key)
        try:
            hot = float(raw) > 0
        except ValueError:
            hot = False
        if not hot:
            raise SliceError(500, "slice check failed: bed temperature is 0 for this plate (%s = %s)" % (key, raw[:20]))

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


def _engine_failure(output, choice):
    """The SliceError for an engine run that failed. The raw engine text goes to the log, not to the person."""
    log.warning("slicer failed: %s", output[-4000:])
    if "floating regions" in output:
        if ((choice or {}).get("supports") or "off") == "off":
            return SliceError(400, "This model has overhanging parts that would print in mid-air. Turn on Tree "
                                   "supports, cut a flat base, or delete loose pieces, then slice again.")
        return SliceError(400, "The slicer could not support this model's overhanging parts. Cut a flat base or "
                               "delete loose pieces, then slice again.")
    return SliceError(500, "slicer failed: " + output[-ENGINE_TAIL:])


# ---------- watchdog readers (module-level so the tests can replace them) ----------
POLL_S = 1.0
CGROUP_DIR = "/sys/fs/cgroup"
MEM_OUT = ("This model is too large to slice on this server (out of memory). Try a smaller or shorter model, "
           "0.28 mm Extra Draft, or supports off.")


def _env_mb(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


def read_cgroup_memory():
    """(current bytes, max bytes) of this container's cgroup, or None when it is unknown or unlimited."""
    try:
        with open(os.path.join(CGROUP_DIR, "memory.max")) as f:
            raw = f.read().strip()
        if not raw.isdigit():
            return None
        with open(os.path.join(CGROUP_DIR, "memory.current")) as f:
            return int(f.read().strip()), int(raw)
    except (OSError, ValueError):
        return None


def read_rss(pid):
    """Resident memory in bytes of a process (pid None = this process), or 0 when it cannot be read."""
    try:
        with open("/proc/%s/status" % (pid or "self")) as f:
            for ln in f:
                if ln.startswith("VmRSS:"):
                    return int(ln.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def memory_exceeded(pid):
    """True when the engine (pid) has used up the memory this container may have. Prefers the cgroup total;
    otherwise engine RSS + this process's RSS against SLICE_MEM_LIMIT_MB."""
    cg = read_cgroup_memory()
    if cg is not None:
        return cg[0] > cg[1] - _env_mb("SLICE_MEM_MARGIN_MB", 40) * 1048576
    return read_rss(pid) + read_rss(None) > _env_mb("SLICE_MEM_LIMIT_MB", 470) * 1048576


def _lower_priority():
    try:
        os.nice(10)
    except Exception:
        pass


def _log_tail(path, size=256 * 1024):
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - size))
            return f.read().decode("utf-8", "replace").strip()
    except OSError:
        return ""


def _wait_for_engine(proc, timeout):
    """Polls the engine about once a second; kills it when it goes over the time or memory limit."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            proc.wait(timeout=POLL_S)
            return
        except subprocess.TimeoutExpired:
            pass
        reason = None
        if time.monotonic() >= deadline:
            reason = SliceError(500, "slicing stopped: it went over the %d s time limit" % timeout)
        elif memory_exceeded(proc.pid):
            reason = SliceError(413, MEM_OUT)
        if reason is not None:
            proc.kill()
            proc.wait()
            raise reason


def run_slice(stl, choice, workdir, timeout=TIMEOUT_S, prepared=None):
    """Slices an uploaded binary STL. Returns (path of workdir/model.gcode.3mf, summary). Raises SliceError;
    the output file never survives a failure. prepared: the info dict from prepare_stl when stl is already its
    prepared output (the server validates first), so the STL is not parsed twice."""
    settings = settings_for(choice)
    if prepared:
        info = prepared
    else:
        stl, info = prepare_stl(stl)
    src = os.path.join(workdir, "model.stl")
    out = os.path.join(workdir, OUTPUT_NAME)
    cfg_path = os.path.join(workdir, "settings.json")
    log_path = os.path.join(workdir, "engine.log")
    with open(src, "wb") as f:
        f.write(stl)
    del stl          # the engine is the big process: do not keep the STL in this one while it runs
    with open(cfg_path, "w") as f:
        json.dump(settings, f)
    _remove(out)
    try:
        try:
            with open(log_path, "wb") as logf:
                proc = subprocess.Popen([node_path(), os.path.join(SLICER_DIR, "slice_job.js"), src, out, cfg_path],
                                        cwd=SLICER_DIR, stdout=logf, stderr=subprocess.STDOUT,
                                        preexec_fn=_lower_priority)
                _wait_for_engine(proc, timeout)
        except OSError as e:
            raise SliceError(500, "the slicer could not be started: %s" % e)
        output = _log_tail(log_path)
        result = None
        for ln in reversed(output.splitlines()):
            if ln.startswith("RESULT "):
                try:
                    result = json.loads(ln[7:])
                except ValueError:
                    pass
                break
        if proc.returncode != 0 or (result is not None and not result.get("ok")):
            raise _engine_failure(output, choice)
        if not os.path.exists(out):
            raise SliceError(500, "slicer produced no file: " + output[-ENGINE_TAIL:])
        try:
            with zipfile.ZipFile(out) as z:
                if [n for n in z.namelist() if n.endswith(".gcode")] != [GCODE_ENTRY]:
                    raise SliceError(500, "unexpected print data in the file")
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
