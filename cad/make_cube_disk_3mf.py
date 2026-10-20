#!/usr/bin/env python3
"""
make_cube_disk_3mf.py

Generates a Bambu Studio-compatible multi-material 3MF:
  - Part 1: 20 mm cube            -> filament / AMS slot 1
  - Part 2: 10 mm dia x 0.5 mm disk on the cube's top face -> AMS slot 2

Both parts are packed as ONE object with two parts (like Bambu Studio's
"Add part"), so they stay aligned and slice as a single multi-material print.

Usage:  python make_cube_disk_3mf.py [output.3mf] [--bed 256]
No third-party dependencies.
"""
import math
import sys
import uuid
import zipfile

# ----------------------------- parameters ---------------------------------
CUBE_SIZE = 20.0       # mm
DISK_DIAMETER = 10.0   # mm
DISK_THICKNESS = 0.5   # mm
DISK_SEGMENTS = 128    # smoothness of the circle
BED_SIZE = 256.0       # X1/P1/X1E = 256; A1 mini = 180; H2D = 350x320 (approx)

# --------------------------- mesh generation ------------------------------
def box_mesh(sx, sy, sz, cx=0.0, cy=0.0, z0=0.0):
    """Axis-aligned box centered at (cx, cy) in XY, bottom at z0.
    Triangles wound counter-clockwise when viewed from outside."""
    x0, x1 = cx - sx / 2, cx + sx / 2
    y0, y1 = cy - sy / 2, cy + sy / 2
    z1 = z0 + sz
    v = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),  # bottom 0-3
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),  # top    4-7
    ]
    t = [
        (0, 2, 1), (0, 3, 2),  # bottom (-Z)
        (4, 5, 6), (4, 6, 7),  # top    (+Z)
        (0, 1, 5), (0, 5, 4),  # front  (-Y)
        (1, 2, 6), (1, 6, 5),  # right  (+X)
        (2, 3, 7), (2, 7, 6),  # back   (+Y)
        (3, 0, 4), (3, 4, 7),  # left   (-X)
    ]
    return v, t


def cylinder_mesh(radius, height, segments, cx=0.0, cy=0.0, z0=0.0):
    """Closed cylinder (disk) with center vertices on each cap."""
    z1 = z0 + height
    v = []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        v.append((cx + radius * math.cos(a), cy + radius * math.sin(a), z0))
    for i in range(segments):
        a = 2 * math.pi * i / segments
        v.append((cx + radius * math.cos(a), cy + radius * math.sin(a), z1))
    bc = len(v); v.append((cx, cy, z0))  # bottom center
    tc = len(v); v.append((cx, cy, z1))  # top center
    t = []
    for i in range(segments):
        j = (i + 1) % segments
        b_i, b_j = i, j
        t_i, t_j = i + segments, j + segments
        t.append((bc, b_j, b_i))          # bottom cap (-Z)
        t.append((tc, t_i, t_j))          # top cap (+Z)
        t.append((b_i, b_j, t_j))         # side
        t.append((b_i, t_j, t_i))         # side
    return v, t


# ----------------------------- XML writers --------------------------------
def mesh_xml(vertices, triangles, indent="      "):
    out = [f"{indent}<mesh>", f"{indent} <vertices>"]
    for x, y, z in vertices:
        out.append(f'{indent}  <vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>')
    out.append(f"{indent} </vertices>")
    out.append(f"{indent} <triangles>")
    for a, b, c in triangles:
        out.append(f'{indent}  <triangle v1="{a}" v2="{b}" v3="{c}"/>')
    out.append(f"{indent} </triangles>")
    out.append(f"{indent}</mesh>")
    return "\n".join(out)


NS_CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
NS_PROD = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
NS_BBS = "http://schemas.bambulab.com/package/2021"

SUB_MODEL_PATH = "/3D/Objects/object_1.model"


def build_sub_model(parts):
    """parts: list of (object_id, name, vertices, triangles)."""
    objs = []
    for oid, name, v, t in parts:
        objs.append(
            f'  <object id="{oid}" p:UUID="{uuid.uuid4()}" type="model">\n'
            f"{mesh_xml(v, t)}\n"
            f"  </object>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{NS_CORE}" '
        f'xmlns:p="{NS_PROD}" requiredextensions="p">\n'
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        " <resources>\n" + "\n".join(objs) + "\n </resources>\n"
        " <build/>\n</model>\n"
    )


def build_main_model(assembly_id, part_ids, bed):
    comps = "\n".join(
        f'    <component p:path="{SUB_MODEL_PATH}" objectid="{pid}" '
        f'p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
        for pid in part_ids
    )
    cx = cy = bed / 2
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{NS_CORE}" '
        f'xmlns:BambuStudio="{NS_BBS}" xmlns:p="{NS_PROD}" requiredextensions="p">\n'
        ' <metadata name="Application">make_cube_disk_3mf.py</metadata>\n'
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        ' <metadata name="Title">Cube with disk (2 materials)</metadata>\n'
        " <resources>\n"
        f'  <object id="{assembly_id}" p:UUID="{uuid.uuid4()}" type="model">\n'
        "   <components>\n"
        f"{comps}\n"
        "   </components>\n"
        "  </object>\n"
        " </resources>\n"
        f' <build p:UUID="{uuid.uuid4()}">\n'
        f'  <item objectid="{assembly_id}" p:UUID="{uuid.uuid4()}" '
        f'transform="1 0 0 0 1 0 0 0 1 {cx:.3f} {cy:.3f} 0" printable="1"/>\n'
        " </build>\n</model>\n"
    )


def build_model_settings(assembly_id, parts_with_extruder, nfaces_total):
    """Bambu Studio per-part metadata: this is where the AMS slot is set."""
    part_xml = []
    for pid, name, extruder, nfaces in parts_with_extruder:
        part_xml.append(
            f'    <part id="{pid}" subtype="normal_part">\n'
            f'      <metadata key="name" value="{name}"/>\n'
            f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
            f'      <metadata key="extruder" value="{extruder}"/>\n'
            f'      <mesh_stat face_count="{nfaces}" edges_fixed="0" '
            f'degenerate_facets="0" facets_removed="0" facets_reversed="0" '
            f'backwards_edges="0"/>\n'
            f"    </part>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
        f'  <object id="{assembly_id}">\n'
        '    <metadata key="name" value="CubeWithDisk"/>\n'
        '    <metadata key="extruder" value="1"/>\n'
        f'    <metadata face_count="{nfaces_total}"/>\n'
        + "\n".join(part_xml) + "\n"
        "  </object>\n"
        "  <plate>\n"
        '    <metadata key="plater_id" value="1"/>\n'
        '    <metadata key="plater_name" value=""/>\n'
        '    <metadata key="locked" value="false"/>\n'
        "    <model_instance>\n"
        f'      <metadata key="object_id" value="{assembly_id}"/>\n'
        '      <metadata key="instance_id" value="0"/>\n'
        '      <metadata key="identify_id" value="1"/>\n'
        "    </model_instance>\n"
        "  </plate>\n"
        "</config>\n"
    )


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="config" ContentType="text/xml"/>
</Types>
"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""

MODEL_RELS = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="{SUB_MODEL_PATH}" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


# --------------------------------- main -----------------------------------
def main():
    args = [a for a in sys.argv[1:]]
    bed = BED_SIZE
    if "--bed" in args:
        i = args.index("--bed"); bed = float(args[i + 1]); del args[i:i + 2]
    out = args[0] if args else "cube_disk_2color.3mf"

    cube_v, cube_t = box_mesh(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE, z0=0.0)
    disk_v, disk_t = cylinder_mesh(DISK_DIAMETER / 2, DISK_THICKNESS,
                                   DISK_SEGMENTS, z0=CUBE_SIZE)

    CUBE_ID, DISK_ID, ASSEMBLY_ID = 1, 2, 3
    sub = build_sub_model([(CUBE_ID, "cube", cube_v, cube_t),
                           (DISK_ID, "disk", disk_v, disk_t)])
    main_model = build_main_model(ASSEMBLY_ID, [CUBE_ID, DISK_ID], bed)
    settings = build_model_settings(
        ASSEMBLY_ID,
        [(CUBE_ID, "cube (material 1)", 1, len(cube_t)),
         (DISK_ID, "disk (material 2)", 2, len(disk_t))],
        len(cube_t) + len(disk_t),
    )

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("3D/3dmodel.model", main_model)
        z.writestr("3D/_rels/3dmodel.model.rels", MODEL_RELS)
        z.writestr(SUB_MODEL_PATH.lstrip("/"), sub)
        z.writestr("Metadata/model_settings.config", settings)
    print(f"Wrote {out}: cube -> filament 1, disk -> filament 2")


if __name__ == "__main__":
    main()
