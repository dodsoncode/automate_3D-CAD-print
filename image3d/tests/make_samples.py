"""Writes the committed sample models in image3d/tests/samples/ (standard library only, deterministic).
Run: python image3d/tests/make_samples.py"""
import json
import os
import struct

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")

# unit-cube corners: index bits are (x, y, z); outward CCW triangles and quads
TRIS = [0, 2, 1, 1, 2, 3, 4, 5, 6, 5, 7, 6, 0, 1, 4, 1, 5, 4, 2, 6, 3, 3, 6, 7, 0, 4, 2, 2, 4, 6, 1, 3, 5, 3, 7, 5]
QUADS = [[0, 2, 3, 1], [4, 5, 7, 6], [0, 1, 5, 4], [2, 6, 7, 3], [0, 4, 6, 2], [1, 3, 7, 5]]


def corners(sx, sy, sz, ox, oy, oz):
    return [(ox + (i & 1) * sx, oy + ((i >> 1) & 1) * sy, oz + ((i >> 2) & 1) * sz) for i in range(8)]


def glb(nodes, meshes, name):
    """meshes: list of (corner list, index struct format char). Indices are written as that integer type."""
    bin_ = b""
    views, accs, prims = [], [], []
    for pts, fmt in meshes:
        pos = b"".join(struct.pack("<3f", *p) for p in pts)
        views.append({"buffer": 0, "byteOffset": len(bin_), "byteLength": len(pos)})
        xs = list(zip(*pts))
        accs.append({"bufferView": len(views) - 1, "componentType": 5126, "count": 8, "type": "VEC3",
                     "min": [min(c) for c in xs], "max": [max(c) for c in xs]})
        bin_ += pos
        pa = len(accs) - 1
        idx = struct.pack("<%d%s" % (len(TRIS), fmt), *TRIS)
        views.append({"buffer": 0, "byteOffset": len(bin_), "byteLength": len(idx)})
        accs.append({"bufferView": len(views) - 1, "componentType": {"B": 5121, "H": 5123, "I": 5125}[fmt],
                     "count": len(TRIS), "type": "SCALAR"})
        bin_ += idx + b"\0" * (-len(idx) % 4)
        prims.append({"primitives": [{"attributes": {"POSITION": pa}, "indices": len(accs) - 1, "mode": 4}]})
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": nodes, "meshes": prims,
           "buffers": [{"byteLength": len(bin_)}], "bufferViews": views, "accessors": accs}
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(bin_)
    data = struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
    data += struct.pack("<II", len(bin_), 0x004E4942) + bin_
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(data)


def obj(cubes, name):
    lines, base = [], 0
    for k, pts in enumerate(cubes):
        lines.append("o cube%d" % k)
        lines += ["v %g %g %g" % p for p in pts]
        lines += ["f " + " ".join(str(base + i + 1) for i in q) for q in QUADS]
        base += 8
    with open(os.path.join(OUT, name), "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def stl(cubes, name):
    tris = [[pts[i] for i in TRIS[j:j + 3]] for pts in cubes for j in range(0, len(TRIS), 3)]
    data = b"image3d sample".ljust(80, b"\0") + struct.pack("<I", len(tris))
    for t in tris:
        data += struct.pack("<3f", 0, 0, 0) + b"".join(struct.pack("<3f", *p) for p in t) + b"\0\0"
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(data)


def main():
    os.makedirs(OUT, exist_ok=True)
    big, small = corners(20, 20, 20, 0, 0, 0), corners(10, 10, 10, 0, 0, 0)
    # big cube via an identity matrix node, small cube on a child node translated 50 along glTF x
    glb([{"mesh": 0, "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], "children": [1]},
         {"mesh": 1, "translation": [50, 0, 0]}], [(big, "H"), (small, "I")], "two_cubes.glb")
    # same, but the small cube hangs off a parent with scale 2 (so it becomes a 20 mm cube at x=50..70)
    glb([{"mesh": 0, "children": [1]}, {"scale": [2, 2, 2], "translation": [50, 0, 0], "children": [2]},
         {"mesh": 1}], [(big, "H"), (small, "B")], "scaled.glb")
    # box 10 (x) by 30 (y, up) by 20 (z) -> 10 x 20 x 30 after the Y-up to Z-up conversion
    glb([{"mesh": 0}], [(corners(10, 30, 20, 0, 0, 0), "H")], "box_yup.glb")
    # 1 unit cube (Y-up height 1): too small, so the editor rescales it to 100 mm
    glb([{"mesh": 0}], [(corners(1, 1, 1, 0, 0, 0), "H")], "unit_box.glb")
    both = [big, corners(10, 10, 10, 50, 0, 0)]
    obj(both, "two_cubes.obj")
    stl(both, "two_cubes.stl")


if __name__ == "__main__":
    main()
