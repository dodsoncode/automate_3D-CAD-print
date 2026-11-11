"""Pure mesh maths (image3d/js/mesh.js, stl.js) checked by running Node snippets: weld, split, delete, scale,
orient, cut-with-caps, closed check and the STL round trip. No three.js needed."""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, "..", "js")

PRELUDE = """
const mesh=require(@MESH@), stl=require(@STL@);
// box with outward CCW triangles: 8 shared vertices, 12 triangles
function box(sx,sy,sz,ox,oy,oz){
  const v=[];for(let i=0;i<8;i++)v.push(ox+(i&1)*sx,oy+((i>>1)&1)*sy,oz+((i>>2)&1)*sz);
  const t=[0,2,1, 1,2,3, 4,5,6, 5,7,6, 0,1,4, 1,5,4, 2,6,3, 3,6,7, 0,4,2, 2,4,6, 1,3,5, 3,7,5];
  return {v:v,t:t};
}
function cube(size,offset){offset=offset||[0,0,0];return box(size,size,size,offset[0],offset[1],offset[2]);}
function soup(shells){const out=[];shells.forEach(s=>{for(let i=0;i<s.t.length;i++){const k=s.t[i]*3;out.push(s.v[k],s.v[k+1],s.v[k+2]);}});return out;}
// square tube (outer 20, inner 10, height 20) as ONE closed shell
function tube(ho){ho=ho||0; // ho: hole offset in x
  const o=[[-10,-10],[10,-10],[10,10],[-10,10]], n=[[-5+ho,-5],[5+ho,-5],[5+ho,5],[-5+ho,5]], v=[], t=[];
  o.forEach(p=>v.push(p[0],p[1],20)); n.forEach(p=>v.push(p[0],p[1],20));
  o.forEach(p=>v.push(p[0],p[1],0));  n.forEach(p=>v.push(p[0],p[1],0));
  for(let k=0;k<4;k++){const k1=(k+1)%4,To=k,To1=k1,Ti=4+k,Ti1=4+k1,Bo=8+k,Bo1=8+k1,Bi=12+k,Bi1=12+k1;
    t.push(To,To1,Ti1, To,Ti1,Ti);
    t.push(Bo,Bi1,Bo1, Bo,Bi,Bi1);
    t.push(Bo,Bo1,To1, Bo,To1,To);
    t.push(Bi,Ti1,Bi1, Bi,Ti,Ti1);}
  return {v:v,t:t};
}
const near=(a,b,e)=>Math.abs(a-b)<=(e||1e-6);
""".replace("@MESH@", json.dumps(os.path.join(JS, "mesh.js"))).replace("@STL@", json.dumps(os.path.join(JS, "stl.js")))


def node(js):
    r = subprocess.run(["node", "-e", PRELUDE + js], capture_output=True, text=True, cwd=HERE)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_weld_and_closed():
    o = node("""const s=mesh.weld(soup([cube(20)]));
console.log(JSON.stringify({nv:s.v.length/3,nt:s.t.length/3,closed:mesh.isClosed(s),vol:mesh.volume(s)}));""")
    assert o["nv"] == 8 and o["nt"] == 12 and o["closed"] is True
    assert abs(o["vol"] - 8000) < 1e-6


def test_weld_indexed_input_and_degenerate_dropped():
    o = node("""const c=cube(20);const sp=soup([c]);sp.push(0,0,0, 0,0,0, 5,5,5); // one degenerate triangle
const a=mesh.weld(sp), b=mesh.weld({v:c.v.concat(c.v),t:c.t.concat(c.t.map(i=>i+8))});
console.log(JSON.stringify({a:a.t.length/3,b:b.v.length/3,bt:b.t.length/3}));""")
    assert o["a"] == 12 and o["b"] == 8 and o["bt"] == 24


def test_split_two_cubes():
    o = node("""const s=mesh.weld(soup([cube(20),cube(10,[50,0,0])]));const p=mesh.split(s);
console.log(JSON.stringify({n:p.length,vols:p.map(mesh.volume)}));""")
    assert o["n"] == 2 and abs(o["vols"][0] - 8000) < 1e-6 and abs(o["vols"][1] - 1000) < 1e-6


def test_remove_and_keep_largest():
    o = node("""const m=mesh.split(mesh.weld(soup([cube(20),cube(10,[50,0,0])])));
const r=mesh.removePiece(m,0), k=mesh.keepLargest([m[1],m[0]]);
console.log(JSON.stringify({rn:r.length,rv:mesh.volume(r[0]),kn:k.length,kv:mesh.volume(k[0]),still:m.length}));""")
    assert o["rn"] == 1 and abs(o["rv"] - 1000) < 1e-6
    assert o["kn"] == 1 and abs(o["kv"] - 8000) < 1e-6 and o["still"] == 2


def test_scale_to_longest_and_layflat():
    o = node("""const m=[cube(20,[5,5,5])];const s=mesh.scaleToLongest(m,100);const f=mesh.layFlat(s);const b=mesh.bbox(f);
console.log(JSON.stringify({size:mesh.bbox(s).size,omin:mesh.bbox(m).min,bmin:b.min,bmax:b.max}));""")
    assert all(abs(x - 100) < 1e-9 for x in o["size"])
    assert o["omin"] == [5, 5, 5]  # input untouched (pure)
    assert abs(o["bmin"][2]) < 1e-9 and abs(o["bmin"][0] + 50) < 1e-9 and abs(o["bmax"][1] - 50) < 1e-9


def test_rotate90_keeps_volume_and_closed():
    o = node("""const m=[box(10,20,30,0,0,0)];const out={};
['x','y','z'].forEach(a=>{const r=mesh.rotate90(m,a);out[a]={size:mesh.bbox(r).size,closed:mesh.isClosed(r[0]),vol:mesh.volume(r[0])};});
console.log(JSON.stringify(out));""")
    assert o["x"]["size"] == [10, 30, 20] and o["y"]["size"] == [30, 20, 10] and o["z"]["size"] == [20, 10, 30]
    for a in "xyz":
        assert o[a]["closed"] is True and abs(o[a]["vol"] - 6000) < 1e-6


def test_cut_cube_capped():
    o = node("""const m=[cube(20)];const r={};
['above','below'].forEach(k=>{const c=mesh.cut(m,'z',5,k);r[k]={n:c.length,closed:mesh.isClosed(c[0]),vol:mesh.volume(c[0]),b:mesh.bbox(c)};});
console.log(JSON.stringify(r));""")
    a, b = o["above"], o["below"]
    assert a["n"] == 1 and a["closed"] is True and abs(a["vol"] - 6000) < 1e-6
    assert abs(a["b"]["min"][2] - 5) < 1e-9 and abs(a["b"]["max"][2] - 20) < 1e-9
    assert b["closed"] is True and abs(b["vol"] - 2000) < 1e-6


def test_cut_on_an_existing_face_and_other_axes():
    o = node("""const m=[cube(20)];
const a=mesh.cut(m,'z',0,'above'), b=mesh.cut(m,'x',10,'below'), c=mesh.cut(m,'y',10,'above');
console.log(JSON.stringify([a,b,c].map(x=>({closed:mesh.isClosed(x[0]),vol:mesh.volume(x[0])}))));""")
    assert all(x["closed"] for x in o)
    assert [round(x["vol"], 6) for x in o] == [8000, 4000, 4000]


def test_cut_hollow_frame_caps_with_hole():
    o = node("""const t=tube();const r=mesh.cut([t],'z',10,'below');
console.log(JSON.stringify({full:mesh.volume(t),closed:mesh.isClosed(t),n:r.length,rc:mesh.isClosed(r[0]),vol:mesh.volume(r[0])}));""")
    assert o["closed"] is True and abs(o["full"] - 6000) < 1e-6
    assert o["n"] == 1 and o["rc"] is True and abs(o["vol"] - 3000) < 1e-6


def test_cut_skewed_off_centre_frame_stays_closed_and_conserves_volume():
    # a sheared tube with an off-centre hole puts cut vertices on a diagonal through other loop vertices
    o = node("""const t=tube(1.5), v=t.v.slice();
for(let i=0;i<v.length;i+=3){v[i]+=0.2*v[i+2];v[i+1]+=0.06*v[i];}
const m=[{v:v,t:t.t}], tot=mesh.volume(m[0]), bad=[];
['x','y','z'].forEach(ax=>{const a='xyz'.indexOf(ax),b=mesh.bbox(m);
  for(let f=1;f<10;f++){const val=b.min[a]+(b.max[a]-b.min[a])*f/10;
    const up=mesh.cut(m,ax,val,'above'),dn=mesh.cut(m,ax,val,'below');
    const vol=up.concat(dn).reduce((s,x)=>s+mesh.volume(x),0);
    if(!up.concat(dn).every(mesh.isClosed)||Math.abs(vol-tot)>1e-6*tot)bad.push([ax,val]);}});
console.log(JSON.stringify({bad:bad}));""")
    assert o["bad"] == []


def test_cut_drops_pieces_entirely_removed():
    o = node("""const m=mesh.split(mesh.weld(soup([box(10,10,10,0,0,0),box(10,10,10,30,0,0)])));
const c=mesh.cut(m,'x',20,'above'), d=mesh.cut(m,'x',5,'above');
console.log(JSON.stringify({cn:c.length,cb:mesh.bbox(c).min[0],cv:mesh.volume(c[0]),dn:d.length,dv:d.map(mesh.volume).sort((x,y)=>x-y)}));""")
    assert o["cn"] == 1 and o["cb"] == 30 and abs(o["cv"] - 1000) < 1e-6
    assert o["dn"] == 2 and abs(o["dv"][0] - 500) < 1e-6 and abs(o["dv"][1] - 1000) < 1e-6


def test_cut_removes_everything_throws():
    o = node("""let msg=null;try{mesh.cut([cube(20)],'z',100,'above');}catch(e){msg=e.message;}
console.log(JSON.stringify({msg:msg}));""")
    assert o["msg"] == "cut removes everything"


def test_cut_open_mesh_no_throw():
    o = node("""const c=cube(20);c.t.splice(12,3); // drop one triangle of the -y wall: now open
let err=null,r=null;try{r=mesh.cut([c],'z',10,'above');}catch(e){err=e.message;}
console.log(JSON.stringify({err:err,open:!mesh.isClosed(c),closed:r?mesh.isClosed(r[0]):null,n:r?r.length:0}));""")
    assert o["err"] is None and o["open"] is True and o["closed"] is False and o["n"] == 1


def test_drop_small_pieces():
    o = node("""const sh=[cube(20)];for(let i=0;i<200;i++)sh.push(cube(0.05,[30+(i%20),Math.floor(i/20),0]));
const m=mesh.split(mesh.weld(soup(sh)));const d=mesh.dropSmall(m);
console.log(JSON.stringify({before:m.length,after:d.length,vol:mesh.volume(d[0])}));""")
    assert o["before"] == 201 and o["after"] == 1 and abs(o["vol"] - 8000) < 1e-6


def test_stl_round_trip():
    o = node("""const m=mesh.split(mesh.weld(soup([cube(20),cube(10,[50,0,0])])));
const bytes=stl.write(m,'demo');const tris=m.reduce((a,s)=>a+s.t.length/3,0);
const back=mesh.split(mesh.weld(stl.read(bytes)));
console.log(JSON.stringify({len:bytes.length,tris:tris,pieces:back.length,vol:back.reduce((a,s)=>a+mesh.volume(s),0),
  isU8:bytes instanceof Uint8Array,soup:stl.read(bytes).length}));""")
    assert o["isU8"] is True and o["len"] == 84 + 50 * o["tris"] and o["tris"] == 24
    assert o["pieces"] == 2 and abs(o["vol"] - 9000) < 1e-6 and o["soup"] == 24 * 9


def test_stl_reads_ascii_and_writes_unit_normals():
    o = node("""const txt='solid x\\n facet normal 0 0 1\\n  outer loop\\n   vertex 0 0 0\\n   vertex 1 0 0\\n   vertex 0 1 0\\n  endloop\\n endfacet\\nendsolid x\\n';
const a=stl.read(new TextEncoder().encode(txt));
const b=stl.write([mesh.weld(soup([cube(2)]))]);const dv=new DataView(b.buffer,b.byteOffset,b.byteLength);
const nz=[];for(let i=0;i<12;i++){const o=84+50*i;nz.push([dv.getFloat32(o,true),dv.getFloat32(o+4,true),dv.getFloat32(o+8,true)]);}
console.log(JSON.stringify({a:a,nz:nz,hdr:String.fromCharCode.apply(null,b.subarray(0,7)),cnt:dv.getUint32(80,true)}));""")
    assert o["a"] == [0, 0, 0, 1, 0, 0, 0, 1, 0]
    assert o["cnt"] == 12 and o["hdr"] == "image3d"
    assert all(abs(sum(c * c for c in n) - 1) < 1e-6 for n in o["nz"])
