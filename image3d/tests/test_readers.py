"""File readers (image3d/js/glb.js, obj.js, readany.js) checked by running Node snippets against the committed
samples in tests/samples/ (regenerate with make_samples.py)."""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, "..", "js")
SAMPLES = os.path.join(HERE, "samples")

PRELUDE = """
const fs=require('fs'), mesh=require(@MESH@), glb=require(@GLB@), obj=require(@OBJ@), readAny=require(@READANY@);
const sample=n=>new Uint8Array(fs.readFileSync(require('path').join(@SAMPLES@,n)));
const volumes=soup=>mesh.split(mesh.weld(soup)).map(mesh.volume).map(v=>Math.round(v*1e6)/1e6);
function err(f){try{f();}catch(e){return e.message;}return null;}
""".replace("@MESH@", json.dumps(os.path.join(JS, "mesh.js"))).replace("@GLB@", json.dumps(os.path.join(JS, "glb.js"))) \
    .replace("@OBJ@", json.dumps(os.path.join(JS, "obj.js"))).replace("@READANY@", json.dumps(os.path.join(JS, "readany.js"))) \
    .replace("@SAMPLES@", json.dumps(SAMPLES))


def node(js):
    r = subprocess.run(["node", "-e", PRELUDE + js], capture_output=True, text=True, cwd=HERE)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_glb_two_cubes():
    assert node("console.log(JSON.stringify(volumes(glb.read(sample('two_cubes.glb')))))") == [8000, 1000]


def test_glb_parent_scale():
    assert node("console.log(JSON.stringify(volumes(glb.read(sample('scaled.glb')))))") == [8000, 8000]


def test_glb_y_up_to_z_up():
    size = node("const s=mesh.weld(glb.read(sample('box_yup.glb')));console.log(JSON.stringify(mesh.bbox([s]).size))")
    assert [round(x, 6) for x in size] == [10, 20, 30]


def test_glb_compressed_rejected():
    for ext in ("KHR_draco_mesh_compression", "EXT_meshopt_compression"):
        msg = node("""
        const js=Buffer.from(JSON.stringify({asset:{version:'2.0'},extensionsRequired:[%s]}));
        const pad=Buffer.alloc((4-js.length%%4)%%4,32), body=Buffer.concat([js,pad]);
        const h=Buffer.alloc(20);h.writeUInt32LE(0x46546C67,0);h.writeUInt32LE(2,4);h.writeUInt32LE(20+body.length,8);
        h.writeUInt32LE(body.length,12);h.writeUInt32LE(0x4E4F534A,16);
        console.log(JSON.stringify(err(()=>glb.read(new Uint8Array(Buffer.concat([h,body]))))));""" % json.dumps(ext))
        assert msg == "compressed"


def test_glb_bad_magic():
    msg = node("console.log(JSON.stringify(err(()=>glb.read(new Uint8Array(20).map((_,i)=>(i*37+11)&255)))))")
    assert msg == "not a GLB file"


def test_obj_quads_and_negative_indices():
    out = node("""
    const text=['# cube with quads, v/vt/vn and negative indices','v 0 0 0','v 20 0 0','v 0 20 0','v 20 20 0',
      'v 0 0 20','v 20 0 20','v 0 20 20','v 20 20 20','vt 0 0','vn 0 0 1',
      'f -8/1/1 -6/1/1 -5/1/1 -7/1/1','f -4//1 -3//1 -1//1 -2//1','f -8 -7 -3 -4','f -6 -2 -1 -5','f -8 -4 -2 -6','f -7 -5 -1 -3'].join('\\r\\n');
    const s=mesh.weld(obj.read(text));
    console.log(JSON.stringify({closed:mesh.isClosed(s),vol:mesh.volume(s),tris:s.t.length/3}));""")
    assert out == {"closed": True, "vol": 8000, "tris": 12}


def test_obj_sample():
    assert node("console.log(JSON.stringify(volumes(obj.read(Buffer.from(sample('two_cubes.obj')).toString()))))") == [8000, 1000]


def test_read_any_dispatch():
    out = node("""
    const bytes=sample('two_cubes.stl');
    console.log(JSON.stringify({stl:volumes(readAny('PART.STL',bytes)),
      glb:volumes(readAny('a.Glb',sample('two_cubes.glb'))),
      obj:volumes(readAny('a.obj',sample('two_cubes.obj'))),
      txt:err(()=>readAny('notes.txt',bytes)), none:err(()=>readAny('noext',bytes))}));""")
    assert out == {"stl": [8000, 1000], "glb": [8000, 1000], "obj": [8000, 1000],
                   "txt": "unsupported file", "none": "unsupported file"}
