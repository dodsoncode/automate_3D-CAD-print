"""Mesh reduction (image3d/js/simplify.js, quadric edge collapse) checked by running Node snippets.

Test meshes are generated in the Node prelude (UV sphere, subdivided box, open grid, tetrahedra), so there are no
fixture files. mesh.js supplies isClosed, volume and bbox."""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, "..", "js")

PRELUDE = """
const mesh=require(@MESH@), simp=require(@SIMP@);
// box with outward CCW triangles: 8 shared vertices, 12 triangles
function box(sx,sy,sz,ox,oy,oz){
  const v=[];for(let i=0;i<8;i++)v.push(ox+(i&1)*sx,oy+((i>>1)&1)*sy,oz+((i>>2)&1)*sz);
  const t=[0,2,1, 1,2,3, 4,5,6, 5,7,6, 0,1,4, 1,5,4, 2,6,3, 3,6,7, 0,4,2, 2,4,6, 1,3,5, 3,7,5];
  return {v:v,t:t};
}
function cube(size,offset){offset=offset||[0,0,0];return box(size,size,size,offset[0],offset[1],offset[2]);}
// square tube (outer 20, inner 10, height 20) as ONE closed shell (genus 1)
function tube(){
  const o=[[-10,-10],[10,-10],[10,10],[-10,10]], n=[[-5,-5],[5,-5],[5,5],[-5,5]], v=[], t=[];
  o.forEach(p=>v.push(p[0],p[1],20)); n.forEach(p=>v.push(p[0],p[1],20));
  o.forEach(p=>v.push(p[0],p[1],0));  n.forEach(p=>v.push(p[0],p[1],0));
  for(let k=0;k<4;k++){const k1=(k+1)%4,To=k,To1=k1,Ti=4+k,Ti1=4+k1,Bo=8+k,Bo1=8+k1,Bi=12+k,Bi1=12+k1;
    t.push(To,To1,Ti1, To,Ti1,Ti); t.push(Bo,Bi1,Bo1, Bo,Bi,Bi1);
    t.push(Bo,Bo1,To1, Bo,To1,To); t.push(Bi,Ti1,Bi1, Bi,Ti,Ti1);}
  return {v:v,t:t};
}
// UV sphere, outward CCW: 2*nLon*(nLat-1) triangles, poles are single vertices
function sphere(r,nLon,nLat,c){c=c||[0,0,0];const v=[c[0],c[1],c[2]+r],t=[];
  for(let i=1;i<nLat;i++){const th=Math.PI*i/nLat;
    for(let j=0;j<nLon;j++){const ph=2*Math.PI*j/nLon;v.push(c[0]+r*Math.sin(th)*Math.cos(ph),c[1]+r*Math.sin(th)*Math.sin(ph),c[2]+r*Math.cos(th));}}
  v.push(c[0],c[1],c[2]-r);const S=v.length/3-1,ring=(i,j)=>1+(i-1)*nLon+((j%nLon)+nLon)%nLon;
  for(let j=0;j<nLon;j++)t.push(0,ring(1,j),ring(1,j+1));
  for(let i=1;i<nLat-1;i++)for(let j=0;j<nLon;j++){const a=ring(i,j),b=ring(i,j+1),c2=ring(i+1,j),d=ring(i+1,j+1);t.push(a,c2,d, a,d,b);}
  for(let j=0;j<nLon;j++)t.push(S,ring(nLat-1,j+1),ring(nLat-1,j));
  return {v:v,t:t};
}
// box size s (integer) with every face an n x n grid of quads (4*... triangles), welded
function gridBox(s,n){const soup=[],h=s/n;
  // face: origin o, axes u and w (u x w = outward normal)
  function face(o,u,w){for(let i=0;i<n;i++)for(let j=0;j<n;j++){
    const p=(a,b)=>[o[0]+u[0]*a*h+w[0]*b*h,o[1]+u[1]*a*h+w[1]*b*h,o[2]+u[2]*a*h+w[2]*b*h];
    const A=p(i,j),B=p(i+1,j),C=p(i+1,j+1),D=p(i,j+1);soup.push(...A,...B,...C,...A,...C,...D);}}
  face([0,0,s],[1,0,0],[0,1,0]); face([0,0,0],[0,1,0],[1,0,0]);
  face([0,0,0],[1,0,0],[0,0,1]); face([0,s,0],[0,0,1],[1,0,0]);
  face([0,0,0],[0,0,1],[0,1,0]); face([s,0,0],[0,1,0],[0,0,1]);
  return mesh.weld(soup);
}
// open n x n grid plane in z=0 (normal +z), size s
function plane(s,n){const v=[],t=[];for(let j=0;j<=n;j++)for(let i=0;i<=n;i++)v.push(s*i/n,s*j/n,0);
  const id=(i,j)=>j*(n+1)+i;
  for(let j=0;j<n;j++)for(let i=0;i<n;i++)t.push(id(i,j),id(i+1,j),id(i+1,j+1), id(i,j),id(i+1,j+1),id(i,j+1));
  return {v:v,t:t};
}
function tetra(sz,o){const v=[o[0],o[1],o[2], o[0]+sz,o[1],o[2], o[0],o[1]+sz,o[2], o[0],o[1],o[2]+sz];
  return {v:v,t:[0,2,1, 0,1,3, 0,3,2, 1,2,3]};}
const tris=m=>m.reduce((n,s)=>n+s.t.length/3,0);
const rel=(a,b)=>Math.abs(a-b)/Math.abs(b);
// signed volume (positive = outward)
function svol(s){let sum=0;const v=s.v,t=s.t;for(let i=0;i<t.length;i+=3){const a=3*t[i],b=3*t[i+1],c=3*t[i+2];
  sum+=v[a]*(v[b+1]*v[c+2]-v[b+2]*v[c+1])-v[a+1]*(v[b]*v[c+2]-v[b+2]*v[c])+v[a+2]*(v[b]*v[c+1]-v[b+1]*v[c]);}return sum/6;}
// every triangle's normal points away from the shell's vertex centroid
function allOutward(s){const v=s.v,t=s.t,n=v.length/3;let cx=0,cy=0,cz=0;
  for(let i=0;i<n;i++){cx+=v[3*i];cy+=v[3*i+1];cz+=v[3*i+2];}cx/=n;cy/=n;cz/=n;let bad=0;
  for(let i=0;i<t.length;i+=3){const a=3*t[i],b=3*t[i+1],c=3*t[i+2];
    const ux=v[b]-v[a],uy=v[b+1]-v[a+1],uz=v[b+2]-v[a+2],wx=v[c]-v[a],wy=v[c+1]-v[a+1],wz=v[c+2]-v[a+2];
    const nx=uy*wz-uz*wy,ny=uz*wx-ux*wz,nz=ux*wy-uy*wx;
    const gx=(v[a]+v[b]+v[c])/3-cx,gy=(v[a+1]+v[b+1]+v[c+1])/3-cy,gz=(v[a+2]+v[b+2]+v[c+2])/3-cz;
    if(nx*gx+ny*gy+nz*gz<=0)bad++;}return bad;}
// bbox of the vertices on edges used by only one triangle
function borderBox(s){const cnt=new Map(),t=s.t;
  for(let i=0;i<t.length;i+=3)for(let k=0;k<3;k++){const a=t[i+k],b=t[i+(k+1)%3],key=Math.min(a,b)+','+Math.max(a,b);cnt.set(key,(cnt.get(key)||0)+1);}
  const vs=new Set();cnt.forEach((c,key)=>{if(c===1)key.split(',').forEach(x=>vs.add(+x));});
  const sub=[];vs.forEach(i=>sub.push(s.v[3*i],s.v[3*i+1],s.v[3*i+2]));
  const b=mesh.bbox([{v:sub,t:[]}]);return {n:vs.size,min:b.min,max:b.max};}
""".replace("@MESH@", json.dumps(os.path.join(JS, "mesh.js"))).replace("@SIMP@", json.dumps(os.path.join(JS, "simplify.js")))


def node(js, timeout=120):
    r = subprocess.run(["node", "-e", PRELUDE + js], capture_output=True, text=True, cwd=HERE, timeout=timeout)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_generators_are_closed_and_outward():
    o = node("""const s=sphere(50,125,81), g=gridBox(40,40), p=plane(100,100), tt=tetra(1,[0,0,0]);
console.log(JSON.stringify({sn:s.t.length/3,sc:mesh.isClosed(s),sv:svol(s),gn:g.t.length/3,gc:mesh.isClosed(g),gv:svol(g),
 pn:p.t.length/3,pc:mesh.isClosed(p),tc:mesh.isClosed(tt),tv:svol(tt),so:allOutward(s),go:allOutward(g)}));""")
    assert o["sn"] == 20000 and o["sc"] is True and o["sv"] > 0 and o["so"] == 0
    assert o["gn"] == 19200 and o["gc"] is True and abs(o["gv"] - 64000) < 1e-6 and o["go"] == 0
    assert o["pn"] == 20000 and o["pc"] is False
    assert o["tc"] is True and o["tv"] > 0


def test_sphere_reduces_to_target():
    o = node("""const s=sphere(50,125,81), v0=s.v.slice(), t0=s.t.slice();
const r=simp.simplifyModel([s],2000), b0=mesh.bbox([s]).size, b1=mesh.bbox(r).size;
console.log(JSON.stringify({n:r.length,tris:tris(r),closed:mesh.isClosed(r[0]),dv:rel(mesh.volume(r[0]),mesh.volume(s)),
 db:[0,1,2].map(a=>rel(b1[a],b0[a])),out:allOutward(r[0]),
 untouched:JSON.stringify(v0)===JSON.stringify(s.v)&&JSON.stringify(t0)===JSON.stringify(s.t),
 plain:Array.isArray(r[0].v)&&Array.isArray(r[0].t)}));""")
    assert o["n"] == 1 and 1800 <= o["tris"] <= 2000
    assert o["closed"] is True and o["dv"] < 0.03 and all(d < 0.02 for d in o["db"])
    assert o["out"] == 0
    assert o["untouched"] is True  # input not mutated
    assert o["plain"] is True  # plain arrays, like every other shell in the page


def test_simplify_shell_direct():
    o = node("""const s=sphere(50,125,81);const r=simp.simplifyShell(s,5000);
console.log(JSON.stringify({tris:r.t.length/3,closed:mesh.isClosed(r)}));""")
    assert 4500 <= o["tris"] <= 5000 and o["closed"] is True


def test_under_target_is_unchanged():
    o = node("""const c=cube(20);const r=simp.simplifyModel([c],100), s=simp.simplifyShell(c,12);
console.log(JSON.stringify({n:r.length,v:r[0].v,t:r[0].t,sv:s.v,st:s.t,c:c}));""")
    assert o["n"] == 1
    assert o["v"] == o["c"]["v"] and o["t"] == o["c"]["t"]
    assert o["sv"] == o["c"]["v"] and o["st"] == o["c"]["t"]


def test_budget_split_by_size_and_floor_of_4():
    o = node("""const m=[sphere(50,125,81),cube(20,[200,0,0])];
for(let i=0;i<300;i++)m.push(tetra(0.5,[-100-(i%20)*2,(Math.floor(i/20))*2,0]));
const r=simp.simplifyModel(m,3000);
console.log(JSON.stringify({n:r.length,total:tris(r),each:r.map(s=>s.t.length/3),closed:r.map(s=>mesh.isClosed(s))}));""")
    assert o["n"] == 302  # shell count unchanged
    assert o["total"] <= 3000 + 4 * 302
    assert all(n >= 4 for n in o["each"]) and all(o["closed"])
    assert o["each"][0] <= 2829 and o["each"][0] >= 2500  # the sphere gets its share by size


def test_flat_faces_do_not_fold():
    o = node("""const g=gridBox(40,40);const r=simp.simplifyModel([g],500);
console.log(JSON.stringify({tris:tris(r),closed:mesh.isClosed(r[0]),dv:rel(mesh.volume(r[0]),64000),out:allOutward(r[0]),
 b:mesh.bbox(r)}));""")
    assert o["tris"] <= 500 and o["closed"] is True
    assert o["dv"] < 0.01
    assert o["out"] == 0  # no folded / flipped triangle
    assert o["b"]["min"] == [0, 0, 0] and o["b"]["max"] == [40, 40, 40]


def test_open_mesh_keeps_its_border():
    o = node("""const p=plane(100,100);const r=simp.simplifyModel([p],1000);const b0=borderBox(p),b1=borderBox(r[0]);
console.log(JSON.stringify({tris:tris(r),b0:b0,b1:b1}));""")
    assert o["tris"] <= 1000
    assert o["b1"]["min"] == o["b0"]["min"] and o["b1"]["max"] == o["b0"]["max"]


def test_tube_stays_closed():
    o = node("""const t=tube();const r=simp.simplifyModel([t],8);
console.log(JSON.stringify({tris:tris(r),closed:mesh.isClosed(r[0]),n:r.length}));""")
    assert o["n"] == 1 and o["closed"] is True and o["tris"] <= 32


def test_speed():
    o = node("""const s=sphere(50,900,501);const n0=s.t.length/3;const t0=Date.now();
const r=simp.simplifyModel([s],142500);const ms=Date.now()-t0;
console.log(JSON.stringify({n0:n0,tris:tris(r),closed:mesh.isClosed(r[0]),ms:ms}));""", timeout=300)
    print("simplify 900,000 -> 142,500 triangles: %.1f s" % (o["ms"] / 1000))
    assert o["n0"] == 900000
    assert 0.9 * 142500 <= o["tris"] <= 142500 and o["closed"] is True
    assert o["ms"] < 30000
