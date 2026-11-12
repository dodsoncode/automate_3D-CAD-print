"""Real end-to-end check of "Slice for P1S": the real server (uvicorn) and the real OrcaSlicer engine.

NOT a pytest test (the name does not start with test_, so pytest never collects it). Needs the engine installed
(`bash slicer/install.sh`). Usage, from the repo root:

    python image3d/tests/e2e_slice.py            # (a) two_cubes.stl and (b) a ~120k-triangle bumpy sphere via the server
    python image3d/tests/e2e_slice.py --direct   # (c) slicing.run_slice on the heavy model in a child process, peak memory

Peak memory: `ru_maxrss` is in KB on Linux (bytes on macOS), and the script assumes Linux.

Prints the summary, wall seconds and (for --direct) peak RSS in MB; exits non-zero on any failed check.
"""
import io
import math
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE3D = os.path.dirname(HERE)
PASSCODE = "e2e-passcode-not-secret"
CHOICE = {"filament": "pla_silk_plus", "quality": "fine", "plate": "textured_pei", "supports": "tree"}


def bumpy_sphere_stl(rings=250, segments=250, radius=35.0):
    """Binary STL of a bumpy sphere about 70 mm across (about 2 * rings * segments triangles)."""
    def point(i, j):
        th = math.pi * i / rings
        ph = 2 * math.pi * (j % segments) / segments
        r = radius * (1 + 0.04 * math.sin(7 * th) * math.cos(9 * ph))
        return (r * math.sin(th) * math.cos(ph), r * math.sin(th) * math.sin(ph), r * math.cos(th))

    tris = []
    for i in range(rings):
        for j in range(segments):
            a, b, c, d = point(i, j), point(i, j + 1), point(i + 1, j + 1), point(i + 1, j)
            if i > 0:
                tris.append((a, d, b))   # outward-facing winding
            if i < rings - 1:
                tris.append((b, d, c))
    out = bytearray(b"bumpy sphere".ljust(80, b"\0") + struct.pack("<I", len(tris)))
    for a, b, c in tris:
        out += struct.pack("<12fH", 0, 0, 0, *a, *b, *c, 0)
    return bytes(out)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check(cond, msg):
    if not cond:
        print("FAIL:", msg)
        sys.exit(1)


def run_through_server(name, stl):
    import httpx
    sys.path.insert(0, IMAGE3D)
    import slicing
    port = free_port()
    env = dict(os.environ, IMAGE3D_PASSCODE=PASSCODE)
    env.pop("HF_TOKEN", None)
    tmp = tempfile.TemporaryDirectory()  # the server's slice folders live here and go when the script ends
    env["TMPDIR"] = tmp.name
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(port),
                               "--log-level", "warning"], cwd=IMAGE3D, env=env)
    base = "http://127.0.0.1:%d" % port
    hdr = {"X-Passcode": PASSCODE}
    try:
        with httpx.Client(base_url=base, trust_env=False, timeout=60) as c:
            for _ in range(100):
                try:
                    if c.get("/api/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.2)
            else:
                check(False, "server did not start")
            opts = c.get("/api/slice/options").json()
            check(opts["available"] is True, "options say unavailable: %r" % opts)
            t0 = time.time()
            r = c.post("/api/slice", headers=hdr, files={"model": ("model.stl", stl)}, data=CHOICE)
            check(r.status_code == 202, "POST /api/slice -> %d %s" % (r.status_code, r.text))
            job = r.json()["job"]
            while True:
                st = c.get("/api/slice/" + job, headers=hdr).json()
                if st["state"] != "running":
                    break
                time.sleep(1)
            wall = time.time() - t0
            check(st["state"] == "done", "job %s: %s" % (st["state"], st["detail"]))
            f = c.get("/api/slice/%s/file" % job, headers=hdr)
            check(f.status_code == 200, "file -> %d" % f.status_code)
            with zipfile.ZipFile(io.BytesIO(f.content)) as z:
                check(z.testzip() is None, "zip is damaged")
                check("Metadata/plate_1.gcode" in z.namelist(), "no Metadata/plate_1.gcode in %s" % z.namelist()[:10])
                gcode = z.read("Metadata/plate_1.gcode").decode("utf-8", "replace")
            summary = slicing.check_gcode(gcode, slicing.settings_for(CHOICE))
            print("%s: OK  wall %.1f s  file %.1f MB  server summary %s  re-check %s"
                  % (name, wall, len(f.content) / 1e6, st["summary"], summary))
    finally:
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            server.kill()
        tmp.cleanup()


def direct(stl):
    """Child process: slicing.run_slice on its own, then peak RSS of this process and of the node child."""
    import resource
    sys.path.insert(0, IMAGE3D)
    import slicing
    with tempfile.TemporaryDirectory() as d:
        t0 = time.time()
        _, summary = slicing.run_slice(stl, CHOICE, d)
        wall = time.time() - t0
    self_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    node_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    print("direct run_slice: wall %.1f s  peak RSS node child %.0f MB  python %.0f MB  summary %s"
          % (wall, node_mb, self_mb, summary))


def main():
    if "--direct" in sys.argv:
        direct(bumpy_sphere_stl())
        return
    with open(os.path.join(HERE, "samples", "two_cubes.stl"), "rb") as f:
        run_through_server("two_cubes.stl", f.read())
    heavy = bumpy_sphere_stl()
    print("heavy model: %d triangles" % struct.unpack_from("<I", heavy, 80)[0])
    run_through_server("bumpy sphere", heavy)


if __name__ == "__main__":
    main()
