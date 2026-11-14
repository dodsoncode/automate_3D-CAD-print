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


def test_weld_accepts_typed_array_soup():
    o = node("""const sp=soup([cube(20)]);const a=mesh.weld(new Float32Array(sp)), b=mesh.weld(new Float64Array(sp));
console.log(JSON.stringify({av:a.v.length/3,at:a.t.length/3,bv:b.v.length/3,closed:mesh.isClosed(a),vol:mesh.volume(a)}));""")
    assert o == {"av": 8, "at": 12, "bv": 8, "closed": True, "vol": o["vol"]} and abs(o["vol"] - 8000) < 1e-6


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


def test_cut_fine_wavy_cylinder_stays_closed():
    # fine cap loops (thousands of tiny, nearly flat ears) used to leave T-junctions against the walls
    o = node("""function cyl(N){const v=[],t=[],R=4,H=20;
  for(let r=0;r<R;r++)for(let i=0;i<N;i++){const a=2*Math.PI*i/N,rad=10*(1+0.3*Math.sin(5*a));v.push(rad*Math.cos(a),rad*Math.sin(a),H*r/(R-1));}
  const cb=v.length/3;v.push(0,0,0);const ct=cb+1;v.push(0,0,H);
  for(let r=0;r<R-1;r++)for(let i=0;i<N;i++){const j=(i+1)%N,a=r*N+i,b=r*N+j,c=(r+1)*N+i,d=(r+1)*N+j;t.push(a,b,d,a,d,c);}
  for(let i=0;i<N;i++){const j=(i+1)%N;t.push(cb,j,i);t.push(ct,(R-1)*N+i,(R-1)*N+j);}
  return {v:v,t:t};}
const res=[];[5000,6000].forEach(N=>{const s=cyl(N),tot=mesh.volume(s);
  const up=mesh.cut([s],'z',7,'above'),dn=mesh.cut([s],'z',7,'below');
  res.push({N:N,input:mesh.isClosed(s),up:up.every(mesh.isClosed),dn:dn.every(mesh.isClosed),
    vol:up.concat(dn).reduce((a,x)=>a+mesh.volume(x),0)-tot});});
console.log(JSON.stringify(res));""")
    for r in o:
        assert r["input"] and r["up"] and r["dn"] and abs(r["vol"]) < 1e-6 * 1e4, r


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


def test_cut_through_pinch_vertex_stays_closed():
    # two pyramids touching apex-to-apex at (0,0,5): the z=5 cross-section is a bow-tie (two triangles sharing
    # one vertex). Real generated meshes have such pinch points; each lobe must get its own cap.
    r = node("""
function pyr(sx){const A=[0,0,5],b=[[sx*10,-5,0],[sx*10,5,0],[sx*10,5,10],[sx*10,-5,10]],o=sx<0,t=[];
  for(let i=0;i<4;i++){const p=b[i],q=b[(i+1)%4];t.push(o?[A,p,q]:[A,q,p]);}
  t.push(o?[b[0],b[2],b[1]]:[b[0],b[1],b[2]]);t.push(o?[b[0],b[3],b[2]]:[b[0],b[2],b[3]]);return t.flat(2);}
const sh=mesh.weld(pyr(1).concat(pyr(-1)));const out={inClosed:mesh.isClosed(sh),inVol:mesh.volume(sh)};
for(const keep of ['below','above']){const c=mesh.cut([sh],'z',5,keep);
  out[keep]={closed:c.every(mesh.isClosed),vol:c.reduce((s,x)=>s+mesh.volume(x),0)};}
for(const axis of ['x','y']){const c=mesh.cut([sh],axis,axis==='x'?4:1,'above');out[axis]=c.every(mesh.isClosed);}
console.log(JSON.stringify(out));""")
    assert r["inClosed"] and abs(r["inVol"] - 2000 / 3) < 1e-6
    for keep in ("below", "above"):
        assert r[keep]["closed"], keep
        assert abs(r[keep]["vol"] - 1000 / 3) < 1e-6, keep
    assert r["x"] and r["y"]


def test_cut_caps_a_real_generated_cross_section():
    # fixtures/real_section.json is the mid-height cross-section of a real Hunyuan3D-2 model: a 1496-point outline
    # with a 1105-point cavity. Found on the first live run: the cap came out wrong and the cut part was not closed.
    fx = json.dumps(os.path.join(HERE, "fixtures", "real_section.json"))
    r = node("""
const F=require(%s);
function walls(loops){const v=[],t=[];loops.forEach(l=>{const o=v.length/3,n=l.length;l.forEach(p=>v.push(p[0],p[1],0));l.forEach(p=>v.push(p[0],p[1],10));
  for(let i=0;i<n;i++){const j=(i+1)%%n;t.push(o+i,o+j,o+n+j, o+i,o+n+j,o+n+i);}});return {v,t};}
function area(l){let s=0;for(let i=0;i<l.length;i++){const a=l[i],b=l[(i+1)%%l.length];s+=a[0]*b[1]-b[0]*a[1];}return s/2;}
const sh=walls([F.outer].concat(F.holes)),want=area(F.outer)+F.holes.reduce((s,h)=>s+area(h),0),out={want:want};
for(const keep of ['below','above']){let open=0,cap=0;
  mesh.cut([sh],'z',5,keep).forEach(s=>{const e=new Map();for(let i=0;i<s.t.length;i+=3){const ids=[s.t[i],s.t[i+1],s.t[i+2]];
    if(ids.every(k=>s.v[3*k+2]===5)){const q=ids.map(k=>[s.v[3*k],s.v[3*k+1]]);cap+=((q[1][0]-q[0][0])*(q[2][1]-q[0][1])-(q[1][1]-q[0][1])*(q[2][0]-q[0][0]))/2;}
    for(let k=0;k<3;k++){const a=ids[k],b=ids[(k+1)%%3];if(s.v[3*a+2]===5&&s.v[3*b+2]===5){const key=Math.min(a,b)+'_'+Math.max(a,b);e.set(key,(e.get(key)||0)+1);}}}
    for(const n of e.values()) if(n===1) open++;});
  out[keep]={open:open,cap:Math.abs(cap)};}
console.log(JSON.stringify(out));""" % fx)
    assert r["want"] > 2000
    for keep in ("below", "above"):
        assert r[keep]["open"] == 0, keep          # every edge on the cut plane is shared by wall and cap
        assert abs(r[keep]["cap"] - r["want"]) < 1e-6 * r["want"], keep   # the cap covers exactly outline minus cavity


def test_cut_cap_fuzz_grid_holes_and_pinch_points():
    # fuzz_cut.js: grid-aligned holes with exactly collinear points, and cross-sections that pinch to a point,
    # each in random triangle order. Found by review after the first live run; every cut must leave no open edge
    # on the cut plane and a cap of exactly the right area.
    r = subprocess.run(["node", os.path.join(HERE, "fuzz_cut.js"), "3", "60"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    rep = json.loads(r.stdout)
    assert set(rep) == {"gridHoles", "bowtie", "holeTouchesOutline", "holeTouchesHole", "collinearPinch"}
    for name, s in rep.items():
        assert s["runs"] == 120 and s["fails"] == 0, (name, s["first"])


# ---------- mirror ----------
MIRROR_HELPERS = """
// summary of a mirrored model: closed pieces, total volume, bbox, symmetric about the plane, no wall left in the plane
function summary(m,a,value){const A={x:0,y:1,z:2}[a];let sym=true,inPlane=0;
  m.forEach(s=>{const keys=new Set();
    for(let i=0;i<s.v.length;i+=3)keys.add([0,1,2].map(c=>Math.round(s.v[i+c]*1e6)).join(','));
    for(let i=0;i<s.t.length;i+=3)if([0,1,2].every(k=>s.v[3*s.t[i+k]+A]===value))inPlane++;});
  const all=new Set();m.forEach(s=>{for(let i=0;i<s.v.length;i+=3)all.add([0,1,2].map(c=>Math.round(s.v[i+c]*1e6)).join(','));});
  m.forEach(s=>{for(let i=0;i<s.v.length;i+=3){const p=[s.v[i],s.v[i+1],s.v[i+2]];p[A]=2*value-p[A];
    if(!all.has(p.map(c=>Math.round(c*1e6)).join(',')))sym=false;}});
  const b=mesh.bbox(m);
  return {pieces:m.length,closed:m.every(mesh.isClosed),vol:m.reduce((s,x)=>s+mesh.volume(x),0),min:b.min,max:b.max,sym:sym,inPlane:inPlane};}
// bumpy closed blob (latitude/longitude sphere with a radius that varies), centre c
function blob(n,c,seed){const v=[],t=[];let s=seed||1;const rnd=()=>{s=(s*1664525+1013904223)%4294967296;return s/4294967296;};
  const k1=1+Math.floor(rnd()*4),k2=1+Math.floor(rnd()*4),ph=rnd()*6;
  const rad=(th,fi)=>10*(1+0.25*Math.sin(k1*fi+ph)*Math.sin(th)+0.15*Math.cos(k2*th));
  v.push(c[0],c[1],c[2]+rad(0,0));
  for(let r=1;r<n;r++){const th=Math.PI*r/n;for(let i=0;i<2*n;i++){const fi=Math.PI*i/n,R=rad(th,fi);
    v.push(c[0]+R*Math.sin(th)*Math.cos(fi),c[1]+R*Math.sin(th)*Math.sin(fi),c[2]+R*Math.cos(th));}}
  const bot=v.length/3;v.push(c[0],c[1],c[2]-rad(Math.PI,0));const W=2*n,ring=r=>1+(r-1)*W;
  for(let i=0;i<W;i++){const j=(i+1)%W;t.push(0,ring(1)+i,ring(1)+j);t.push(bot,ring(n-1)+j,ring(n-1)+i);}
  for(let r=1;r<n-1;r++)for(let i=0;i<W;i++){const j=(i+1)%W,a=ring(r)+i,b=ring(r)+j,d=ring(r+1)+i,e=ring(r+1)+j;t.push(a,d,e,a,e,b);}
  return {v:v,t:t};}
"""


def test_mirror_cube_keeps_one_side_and_doubles_it():
    o = node(MIRROR_HELPERS + """const c=cube(20);
console.log(JSON.stringify({lo:summary(mesh.mirror([c],'x',15,'below'),'x',15),hi:summary(mesh.mirror([c],'x',15,'above'),'x',15),
  z:summary(mesh.mirror([c],'z',5,'above'),'z',5),same:c.v.length===24}));""")
    lo, hi, z = o["lo"], o["hi"], o["z"]
    assert lo["pieces"] == 1 and lo["closed"] and lo["sym"] and lo["inPlane"] == 0
    assert abs(lo["vol"] - 12000) < 1e-6 and lo["min"][0] == 0 and lo["max"][0] == 30
    assert hi["pieces"] == 1 and hi["closed"] and hi["sym"] and hi["inPlane"] == 0
    assert abs(hi["vol"] - 4000) < 1e-6 and hi["min"][0] == 10 and hi["max"][0] == 20
    assert z["closed"] and abs(z["vol"] - 12000) < 1e-6 and z["min"][2] == 5 - 15 and z["max"][2] == 20
    assert o["same"]  # the input is not changed


def test_mirror_hollow_frame_is_one_closed_piece_with_twice_the_kept_volume():
    o = node(MIRROR_HELPERS + """const t=tube(3);const half=mesh.cut([t],'x',2,'above').reduce((s,x)=>s+mesh.volume(x),0);
const m=mesh.mirror([t],'x',2,'above');console.log(JSON.stringify(Object.assign(summary(m,'x',2),{half:half})));""")
    assert o["pieces"] == 1 and o["closed"] and o["sym"] and o["inPlane"] == 0
    assert abs(o["vol"] - 2 * o["half"]) < 1e-6


def test_mirror_twins_pieces_on_the_kept_side_and_drops_the_other_side():
    o = node(MIRROR_HELPERS + """const m=[box(10,10,10,0,0,0),box(10,10,10,30,0,0),box(10,10,10,-30,0,0)];
const r=mesh.mirror(m,'x',5,'above');console.log(JSON.stringify(summary(r,'x',5)));""")
    # the cut cube -> one 10 mm cube again; the cube at x 30..40 -> itself and a twin at -30..-20; the third is dropped
    assert o["pieces"] == 3 and o["closed"] and o["sym"] and o["inPlane"] == 0
    assert abs(o["vol"] - 3000) < 1e-6 and o["min"][0] == -30 and o["max"][0] == 40


def test_mirror_plane_must_cross_the_model():
    o = node("""const c=cube(20), out=[];
[['x',0,'above'],['x',20,'below'],['x',-5,'above'],['x',25,'below'],['q',5,'above'],['x',5,'left']].forEach(a=>{
  try{mesh.mirror([c],a[0],a[1],a[2]);out.push('ok');}catch(e){out.push(e.message);}});
console.log(JSON.stringify(out));""")
    assert o[:4] == ["mirror plane misses the model"] * 4
    assert o[4] == "axis must be x, y or z" and o[5] == "keep must be 'above' or 'below'"


def test_mirror_plane_on_a_face_keeping_the_whole_model_is_refused():
    # plane on the far face, keeping everything: the model would just get a twin glued face to face
    o = node("""const c=cube(20);let r;try{mesh.mirror([c],'x',20,'above');r='ok';}catch(e){r=e.message;}
console.log(JSON.stringify(r));""")
    assert o == "mirror plane misses the model"


def test_mirror_bumpy_blobs_on_random_planes_stay_closed_and_symmetric():
    o = node(MIRROR_HELPERS + """let s=7;const rnd=()=>{s=(s*1664525+1013904223)%4294967296;return s/4294967296;};
const bad=[];let runs=0;
for(let k=0;k<40;k++){const b=blob(12+Math.floor(rnd()*20),[rnd()*40-20,rnd()*40-20,rnd()*40],k+1),bb=mesh.bbox([b]);
  for(const a of ['x','y','z'])for(const keep of ['above','below']){const A={x:0,y:1,z:2}[a];
    const value=bb.min[A]+bb.size[A]*(0.1+0.8*rnd());runs++;
    try{const half=mesh.cut([b],a,value,keep).reduce((q,x)=>q+mesh.volume(x),0),m=mesh.mirror([b],a,value,keep),u=summary(m,a,value);
      if(!u.closed||!u.sym||u.inPlane||Math.abs(u.vol-2*half)>1e-6*half)bad.push({k:k,a:a,keep:keep,value:value,u:u,half:half});
    }catch(e){bad.push({k:k,a:a,keep:keep,value:value,error:e.message});}}}
console.log(JSON.stringify({runs:runs,bad:bad.slice(0,3),nbad:bad.length}));""")
    assert o["runs"] == 240 and o["nbad"] == 0, o["bad"]


def test_mirror_through_existing_vertices_stays_closed():
    # plane exactly through a ring of vertices (the generator's models have many vertices; sliders land on them)
    o = node(MIRROR_HELPERS + """const b=blob(16,[0,0,0],3);const z=b.v[3*(1+7*32)+2]; // z of ring 8
const m=mesh.mirror([b],'z',z,'above');console.log(JSON.stringify(summary(m,'z',z)));""")
    assert o["closed"] and o["sym"] and o["inPlane"] == 0 and o["pieces"] == 1
