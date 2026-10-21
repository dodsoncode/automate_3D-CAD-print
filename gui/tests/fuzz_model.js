// Random-parameter sweep of the design model for every style: every shell closed with positive volume, no exceptions,
// finite numbers. Usage: node fuzz_model.js [rounds]   (needs `three` and `earcut` on NODE_PATH)
const M = require('../js/model.js'), G = require('../js/geom.js');
let seed = 12345;
function rnd() { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }
const rounds = parseInt(process.argv[2] || '60', 10);
const report = { styles: {}, failures: [] };
M.STYLES.forEach(function (st) {
  const keys = Object.keys(M.RANGES), r = { runs: 0, closedFail: 0, volFail: 0, nan: 0, green: 0 };
  // defaults of every style must be all green
  const def = M.styleDefaults(st), da = M.analyze(def);
  r.defaultWorst = da.worst;
  for (let i = 0; i < rounds; i++) {
    const p = M.styleDefaults(st);
    keys.forEach(function (k) { const g = M.RANGES[k]; if (rnd() < 0.6) p[k] = g[0] + Math.round(rnd() * (g[1] - g[0]) / g[2]) * g[2]; });
    M.clampParams(p);
    try {
      const d = M.derive(p), parts = M.buildParts(p, d), objs = M.printObjects(p, d, parts), an = M.analyze(p, objs);
      objs.forEach(function (o) { o.parts.forEach(function (pt) { pt.shells.forEach(function (s) {
        if (!G.isClosed(s)) { r.closedFail++; report.failures.push(st + ' open shell ' + o.name + ' ' + JSON.stringify(p).slice(0, 200)); }
        if (!(G.volume(s) > 0)) { r.volFail++; report.failures.push(st + ' volume<=0 ' + o.name); }
      }); }); });
      if (!isFinite(an.grams) || !isFinite(an.stability.margin)) r.nan++;
      if (an.worst === 'ok') r.green++;
      r.runs++;
    } catch (e) { r.exceptions = (r.exceptions || 0) + 1; report.failures.push(st + ' exception ' + e.message + ' ' + JSON.stringify(p).slice(0, 160)); }
  }
  report.styles[st] = r;
});
console.log(JSON.stringify(report));
