#!/usr/bin/env python3
"""Independent check of a Bambu-style 3MF (the Python writer's or the Walker Designer's).

Usage: python cad/validate_3mf.py file.3mf [--bed 256]
Checks: every mesh is closed + consistently oriented (each directed edge used once, its reverse once), positive
volume, every build item fits on the bed, every part has an extruder 1-4. Exit code 1 on any failure.
"""
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

NS = {"c": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def mesh_of(obj):
    verts = [(float(v.get("x")), float(v.get("y")), float(v.get("z"))) for v in obj.iterfind(".//c:vertex", NS)]
    tris = [(int(t.get("v1")), int(t.get("v2")), int(t.get("v3"))) for t in obj.iterfind(".//c:triangle", NS)]
    return verts, tris


def check_mesh(verts, tris):
    edges = Counter()
    vol = 0.0
    for a, b, c in tris:
        for e in ((a, b), (b, c), (c, a)):
            edges[e] += 1
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = verts[a], verts[b], verts[c]
        vol += (x1 * (y2 * z3 - y3 * z2) - y1 * (x2 * z3 - x3 * z2) + z1 * (x2 * y3 - x3 * y2)) / 6.0
    bad = [e for e, n in edges.items() if n != 1 or edges.get((e[1], e[0]), 0) != 1]
    return len(bad), vol


def main():
    args = sys.argv[1:]
    bed = 256.0
    if "--bed" in args:
        i = args.index("--bed")
        bed = float(args[i + 1])
        del args[i:i + 2]
    path = args[0]
    problems = []
    with zipfile.ZipFile(path) as z:
        sub = ET.fromstring(z.read("3D/Objects/object_1.model"))
        main_m = ET.fromstring(z.read("3D/3dmodel.model"))
        settings = ET.fromstring(z.read("Metadata/model_settings.config"))
    meshes = {}
    for o in sub.iterfind(".//c:object", NS):
        v, t = mesh_of(o)
        open_edges, vol = check_mesh(v, t)
        meshes[o.get("id")] = (v, t)
        if open_edges:
            problems.append("mesh %s: %d open/inconsistent edges" % (o.get("id"), open_edges))
        if vol <= 0:
            problems.append("mesh %s: volume %.3f <= 0" % (o.get("id"), vol))
    comps = {}
    for o in main_m.iterfind(".//c:resources/c:object", NS):
        comps[o.get("id")] = [c.get("objectid") for c in o.iterfind(".//c:component", NS)]
    items = 0
    for it in main_m.iterfind(".//c:build/c:item", NS):
        items += 1
        t = [float(x) for x in it.get("transform").split()]
        for pid in comps[it.get("objectid")]:
            v, _ = meshes[pid]
            xs = [p[0] + t[9] for p in v]
            ys = [p[1] + t[10] for p in v]
            if min(xs) < 0 or min(ys) < 0 or max(xs) > bed or max(ys) > bed:
                problems.append("item %s part %s outside %g mm bed" % (it.get("objectid"), pid, bed))
    ext = Counter()
    for p in settings.iterfind(".//part"):
        e = p.find("metadata[@key='extruder']").get("value")
        ext[e] += 1
        if e not in ("1", "2", "3", "4"):
            problems.append("part %s extruder %s not in 1-4" % (p.get("id"), e))
    print("%s: %d meshes, %d build items, extruder use %s" % (path, len(meshes), items, dict(sorted(ext.items()))))
    for pr in problems:
        print("PROBLEM:", pr)
    print("OK" if not problems else "FAILED")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
