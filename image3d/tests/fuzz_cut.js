// Fuzz for cut caps (run by test_mesh.py): extrude random cross-sections into wall-only tubes, cut them, and check
// that every edge on the cut plane is shared by wall and cap and that the cap covers exactly outline minus holes.
// Usage: node fuzz_cut.js [seed] [runs]   -> JSON {suite: {runs, fails, first}}
const path = require('path');
const mesh = require(path.join(__dirname, '..', 'js', 'mesh.js'));
let seed = +process.argv[2] || 1;
const RUNS = +process.argv[3] || 100;
function rnd() { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; }
function shuffle(a) { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
function area(l) { let s = 0; l.forEach((p, i) => { const b = l[(i + 1) % l.length]; s += p[0] * b[1] - b[0] * p[1]; }); return s / 2; }
// wall triangles (as a shuffled soup, so the tracing order varies) for loops given in (x, y), z from 0 to 10
function tube(loops) {
  const out = [];
  loops.forEach(l => { const n = l.length; for (let i = 0; i < n; i++) { const a = l[i], b = l[(i + 1) % n];
    const A = [a[0], a[1], 0], B = [b[0], b[1], 0], C = [b[0], b[1], 10], D = [a[0], a[1], 10]; out.push([A, B, C], [A, C, D]); } });
  return mesh.weld(shuffle(out).flat(2));
}
function planeStats(shells, z) {
  let open = 0, cap = 0;
  shells.forEach(s => { const e = new Map();
    for (let i = 0; i < s.t.length; i += 3) { const ids = [s.t[i], s.t[i + 1], s.t[i + 2]];
      if (ids.every(k => s.v[3 * k + 2] === z)) { const q = ids.map(k => [s.v[3 * k], s.v[3 * k + 1]]); cap += ((q[1][0] - q[0][0]) * (q[2][1] - q[0][1]) - (q[1][1] - q[0][1]) * (q[2][0] - q[0][0])) / 2; }
      for (let k = 0; k < 3; k++) { const a = ids[k], b = ids[(k + 1) % 3]; if (s.v[3 * a + 2] === z && s.v[3 * b + 2] === z) { const key = a + '_' + b; if (e.has(key)) open += 100; e.set(key, 1); } } }
    for (const key of e.keys()) { const [a, b] = key.split('_'); if (!e.has(b + '_' + a)) open++; } });
  return { open, cap };
}
function check(loops, rep, label) {
  const want = loops.reduce((s, l) => s + area(l), 0), sh = tube(loops);
  for (const keep of ['above', 'below']) {
    rep.runs++;
    let bad = null;
    try { const s = planeStats(mesh.cut([sh], 'z', 5, keep), 5);
      if (s.open || Math.abs(Math.abs(s.cap) - Math.abs(want)) > 1e-6 * Math.abs(want)) bad = Object.assign({ label, keep, want }, s);
    } catch (err) { bad = { label, keep, error: err.message }; }
    if (bad) { rep.fails++; if (!rep.first) rep.first = bad; }
  }
}
// rectangle with extra points along its sides (exactly collinear), starting at a random corner
function rectLoop(x0, y0, x1, y1, ccw) {
  const pts = [], P = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  for (let e = 0; e < 4; e++) { const a = P[e], b = P[(e + 1) % 4], m = 1 + Math.floor(rnd() * 6); for (let k = 0; k < m; k++) pts.push([a[0] + (b[0] - a[0]) * k / m, a[1] + (b[1] - a[1]) * k / m]); }
  if (!ccw) pts.reverse();
  const r = Math.floor(rnd() * pts.length); return pts.slice(r).concat(pts.slice(0, r));
}
const report = {};
// 1. grid-aligned outline with 0-3 separate rectangular holes, all with collinear points
report.gridHoles = { runs: 0, fails: 0, first: null };
for (let it = 0; it < RUNS; it++) {
  const loops = [rectLoop(0, 0, 100, 100, true)], used = [], nh = Math.floor(rnd() * 4);
  for (let h = 0; h < nh; h++) { const x0 = 5 + Math.floor(rnd() * 70), y0 = 5 + Math.floor(rnd() * 70), w = 3 + Math.floor(rnd() * 20), hh = 3 + Math.floor(rnd() * 20);
    if (x0 + w > 95 || y0 + hh > 95 || used.some(u => !(x0 + w < u[0] || u[0] + u[2] < x0 || y0 + hh < u[1] || u[1] + u[3] < y0))) continue;
    used.push([x0, y0, w, hh]); loops.push(rectLoop(x0, y0, x0 + w, y0 + hh, false)); }
  check(loops, report.gridHoles, 'gridHoles#' + it);
}
// 2. cross-sections that pinch to a point (loops sharing one vertex), in random triangle order
const SQ = [[0, 0], [100, 0], [100, 100], [0, 100]];
const pinch = {
  bowtie: [[[0, 0], [10, 0], [10, 10]], [[0, 0], [-10, 0], [-10, -10]]],
  holeTouchesOutline: [[[0, 0], [100, 0], [100, 100], [0, 100], [0, 50]], [[0, 50], [20, 30], [40, 50], [20, 70]]],
  holeTouchesHole: [SQ, [[20, 20], [20, 40], [40, 40], [40, 20]], [[40, 40], [40, 60], [60, 60], [60, 40]]],
  collinearPinch: [SQ, [[20, 20], [20, 40], [30, 40], [40, 40], [40, 20]], [[40, 40], [40, 60], [50, 60], [60, 60], [60, 40]]],
};
Object.keys(pinch).forEach(name => {
  report[name] = { runs: 0, fails: 0, first: null };
  // outline counter-clockwise, holes clockwise (the bow-tie is two outlines)
  const loops = pinch[name].map((l, i) => ((i === 0 || name === 'bowtie') === (area(l) > 0)) ? l : l.slice().reverse());
  for (let it = 0; it < RUNS; it++) check(loops, report[name], name + '#' + it);
});
console.log(JSON.stringify(report));
