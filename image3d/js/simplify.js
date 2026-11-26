/* Mesh reduction for the image3d editor: quadric-error edge collapse (Garland-Heckbert).
 *
 * A shell is {v: [x,y,z, ...], t: [i,j,k, ...]} with shared (welded) vertices and outward CCW triangles; a model is
 * an array of shells (same as js/mesh.js). Inputs are never changed; results are new plain arrays.
 *
 *   simplifyModel(model, target) -> model   each shell gets max(4, round(target x shellTris / totalTris))
 *   simplifyShell(shell, target) -> shell
 *
 * Kept safe: a collapse is refused if it would break the link condition (the mesh stays manifold, so a closed shell
 * stays closed), turn any neighbouring triangle by more than ~78 degrees (normal dot < 0.2), or take a closed shell
 * below a tetrahedron. Border edges of open shells carry a heavy penalty plane, so the outline stays put.
 * Typed arrays and a binary heap with lazy invalidation keep it fast enough for ~900k triangles on a phone.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.I3DSimplify = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  var MIN_TRIS = 4;          // a closed shell never goes below a tetrahedron
  var FLIP_DOT = 0.2;        // refuse a collapse that turns a neighbour's normal this far (cos ~78 degrees)
  var BORDER_WEIGHT = 1000;  // penalty plane on open borders, times edge length squared
  var COND = 1e-12;          // |det| / trace^3 below this: the 3x3 solve is ill conditioned

  function copyShell(s) { return { v: Array.prototype.slice.call(s.v), t: Array.prototype.slice.call(s.t) }; }

  function grownF64(a, need) { var b = new Float64Array(Math.max(need, a.length * 2)); b.set(a); return b; }
  function grownI32(a, need) { var b = new Int32Array(Math.max(need, a.length * 2)); b.set(a); return b; }

  function simplifyShell(shell, target) {
    target = Math.max(MIN_TRIS, Math.round(target) || 0);
    var nt = shell.t.length / 3;
    if (nt <= target) return copyShell(shell);
    var nv = shell.v.length / 3, i, k, f;

    var P = new Float64Array(shell.v);   // positions
    var T = new Int32Array(shell.t);     // triangles (vertex triples); a collapse rewrites b -> a in place
    var tdead = new Uint8Array(nt);
    var vdead = new Uint8Array(nv), border = new Uint8Array(nv), locked = new Uint8Array(nv);
    var vstamp = new Int32Array(nv);     // bumped when a vertex moves; heap entries carry both endpoint stamps
    var mark = new Int32Array(nv), markCtr = 0;
    var nb = new Int32Array(nv), nbCnt = new Int32Array(nv), nbTri = new Int32Array(nv), nbn = 0;

    // ---- vertex -> triangle lists (CSR; a collapsed vertex's new list is appended at the end) ----
    var vstart = new Int32Array(nv), vcount = new Int32Array(nv);
    for (i = 0; i < 3 * nt; i++) vcount[T[i]]++;
    var refs = new Int32Array(3 * nt + (3 * nt >> 1) + 16), refsLen = 0;
    for (i = 0; i < nv; i++) { vstart[i] = refsLen; refsLen += vcount[i]; vcount[i] = 0; }
    for (f = 0; f < nt; f++) for (k = 0; k < 3; k++) { var vv = T[3 * f + k]; refs[vstart[vv] + vcount[vv]++] = f; }

    // neighbours of v into nb[0..nbn): with nbCnt = triangles shared with v and nbTri = one such triangle
    function gather(v) {
      var m = ++markCtr, s = vstart[v], e = s + vcount[v];
      nbn = 0;
      for (var r = s; r < e; r++) {
        var tf = refs[r];
        if (tdead[tf]) continue;
        for (var q = 0; q < 3; q++) {
          var u = T[3 * tf + q];
          if (u === v) continue;
          if (mark[u] !== m) { mark[u] = m; nb[nbn] = u; nbCnt[nbn] = 0; nbTri[nbn] = tf; nbn++; }
        }
      }
      // second pass counts shared triangles per neighbour; mark briefly holds -(index+1), never a counter value
      for (var j = 0; j < nbn; j++) mark[nb[j]] = -(j + 1);
      for (r = s; r < e; r++) {
        tf = refs[r];
        if (tdead[tf]) continue;
        for (q = 0; q < 3; q++) { u = T[3 * tf + q]; if (u !== v) nbCnt[-mark[u] - 1]++; }
      }
    }

    // ---- quadrics: area-weighted face planes, plus border penalty planes ----
    var Q = new Float64Array(10 * nv);
    function addPlane(v, a, b, c, d, w) {
      var o = 10 * v;
      Q[o] += w * a * a; Q[o + 1] += w * a * b; Q[o + 2] += w * a * c; Q[o + 3] += w * a * d;
      Q[o + 4] += w * b * b; Q[o + 5] += w * b * c; Q[o + 6] += w * b * d;
      Q[o + 7] += w * c * c; Q[o + 8] += w * c * d; Q[o + 9] += w * d * d;
    }
    var FN = new Float64Array(3);
    function faceNormal(tf) { // unit normal into FN, returns twice the area
      var a = 3 * T[3 * tf], b = 3 * T[3 * tf + 1], c = 3 * T[3 * tf + 2];
      var ux = P[b] - P[a], uy = P[b + 1] - P[a + 1], uz = P[b + 2] - P[a + 2];
      var wx = P[c] - P[a], wy = P[c + 1] - P[a + 1], wz = P[c + 2] - P[a + 2];
      var nx = uy * wz - uz * wy, ny = uz * wx - ux * wz, nz = ux * wy - uy * wx;
      var len = Math.sqrt(nx * nx + ny * ny + nz * nz);
      if (len > 0) { FN[0] = nx / len; FN[1] = ny / len; FN[2] = nz / len; } else { FN[0] = FN[1] = FN[2] = 0; }
      return len;
    }
    for (f = 0; f < nt; f++) {
      var len2 = faceNormal(f);
      if (!(len2 > 0)) continue;
      var a0 = 3 * T[3 * f], d0 = -(FN[0] * P[a0] + FN[1] * P[a0 + 1] + FN[2] * P[a0 + 2]);
      for (k = 0; k < 3; k++) addPlane(T[3 * f + k], FN[0], FN[1], FN[2], d0, len2 / 2);
    }
    for (var v0 = 0; v0 < nv; v0++) {
      gather(v0);
      for (var j0 = 0; j0 < nbn; j0++) {
        var u0 = nb[j0], c0 = nbCnt[j0];
        if (c0 > 2) { locked[v0] = 1; locked[u0] = 1; continue; } // non-manifold edge: leave it alone
        if (c0 !== 1 || u0 < v0) continue;
        border[v0] = 1; border[u0] = 1;
        faceNormal(nbTri[j0]);
        var ex = P[3 * u0] - P[3 * v0], ey = P[3 * u0 + 1] - P[3 * v0 + 1], ez = P[3 * u0 + 2] - P[3 * v0 + 2];
        var px = ey * FN[2] - ez * FN[1], py = ez * FN[0] - ex * FN[2], pz = ex * FN[1] - ey * FN[0];
        var pl = Math.sqrt(px * px + py * py + pz * pz);
        if (!(pl > 0)) continue;
        px /= pl; py /= pl; pz /= pl;
        var pd = -(px * P[3 * v0] + py * P[3 * v0 + 1] + pz * P[3 * v0 + 2]), w = BORDER_WEIGHT * (ex * ex + ey * ey + ez * ez);
        addPlane(v0, px, py, pz, pd, w); addPlane(u0, px, py, pz, pd, w);
      }
    }

    // ---- collapse cost: optimal point if well conditioned (and near the edge), else best of ends / midpoint ----
    var BX = 0, BY = 0, BZ = 0;
    function edgeCost(a, b) {
      var oa = 10 * a, ob = 10 * b;
      var q0 = Q[oa] + Q[ob], q1 = Q[oa + 1] + Q[ob + 1], q2 = Q[oa + 2] + Q[ob + 2], q3 = Q[oa + 3] + Q[ob + 3];
      var q4 = Q[oa + 4] + Q[ob + 4], q5 = Q[oa + 5] + Q[ob + 5], q6 = Q[oa + 6] + Q[ob + 6];
      var q7 = Q[oa + 7] + Q[ob + 7], q8 = Q[oa + 8] + Q[ob + 8], q9 = Q[oa + 9] + Q[ob + 9];
      var ax = P[3 * a], ay = P[3 * a + 1], az = P[3 * a + 2], bx = P[3 * b], by = P[3 * b + 1], bz = P[3 * b + 2];
      var mx = (ax + bx) / 2, my = (ay + by) / 2, mz = (az + bz) / 2;
      function err(x, y, z) {
        return q0 * x * x + 2 * q1 * x * y + 2 * q2 * x * z + 2 * q3 * x + q4 * y * y + 2 * q5 * y * z + 2 * q6 * y +
          q7 * z * z + 2 * q8 * z + q9;
      }
      var c00 = q4 * q7 - q5 * q5, c01 = q2 * q5 - q1 * q7, c02 = q1 * q5 - q2 * q4;
      var det = q0 * c00 + q1 * c01 + q2 * c02, tr = q0 + q4 + q7;
      if (tr > 0 && Math.abs(det) > COND * tr * tr * tr) {
        var c11 = q0 * q7 - q2 * q2, c12 = q1 * q2 - q0 * q5, c22 = q0 * q4 - q1 * q1;
        var x = -(c00 * q3 + c01 * q6 + c02 * q8) / det;
        var y = -(c01 * q3 + c11 * q6 + c12 * q8) / det;
        var z = -(c02 * q3 + c12 * q6 + c22 * q8) / det;
        var dx = x - mx, dy = y - my, dz = z - mz, el2 = (ax - bx) * (ax - bx) + (ay - by) * (ay - by) + (az - bz) * (az - bz);
        if (dx * dx + dy * dy + dz * dz <= el2) { BX = x; BY = y; BZ = z; return err(x, y, z); }
      }
      var ea = err(ax, ay, az), eb = err(bx, by, bz), em = err(mx, my, mz);
      if (em <= ea && em <= eb) { BX = mx; BY = my; BZ = mz; return em; }
      if (ea <= eb) { BX = ax; BY = ay; BZ = az; return ea; }
      BX = bx; BY = by; BZ = bz; return eb;
    }

    // ---- binary heap of edge entries (cost, entry id); entries carry endpoint stamps ----
    var cap = Math.max(64, 2 * nt);
    var hc = new Float64Array(cap), hi = new Int32Array(cap), hsize = 0;
    var ea = new Int32Array(cap), eb = new Int32Array(cap), esa = new Int32Array(cap), esb = new Int32Array(cap);
    var freeIds = new Int32Array(cap), nfree = 0, nextId = 0;
    function push(a, b) {
      var cost = edgeCost(a, b), id;
      if (nfree) id = freeIds[--nfree];
      else {
        id = nextId++;
        if (id >= ea.length) {
          ea = grownI32(ea, id + 1); eb = grownI32(eb, id + 1); esa = grownI32(esa, id + 1); esb = grownI32(esb, id + 1);
          freeIds = grownI32(freeIds, id + 1);
        }
      }
      ea[id] = a; eb[id] = b; esa[id] = vstamp[a]; esb[id] = vstamp[b];
      if (hsize >= hc.length) { hc = grownF64(hc, hsize + 1); hi = grownI32(hi, hsize + 1); }
      var n = hsize++;
      while (n > 0) {
        var p = (n - 1) >> 1;
        if (hc[p] <= cost) break;
        hc[n] = hc[p]; hi[n] = hi[p]; n = p;
      }
      hc[n] = cost; hi[n] = id;
    }
    function pop() {
      var top = hi[0];
      hsize--;
      var lc = hc[hsize], li = hi[hsize], n = 0, half = hsize >> 1;
      while (n < half) {
        var c = 2 * n + 1;
        if (c + 1 < hsize && hc[c + 1] < hc[c]) c++;
        if (hc[c] >= lc) break;
        hc[n] = hc[c]; hi[n] = hi[c]; n = c;
      }
      if (hsize > 0) { hc[n] = lc; hi[n] = li; }
      freeIds[nfree++] = top;
      return top;
    }
    function pushAll() {
      for (var v = 0; v < nv; v++) {
        if (vdead[v] || locked[v]) continue;
        gather(v);
        for (var j = 0; j < nbn; j++) { var u = nb[j]; if (u > v && !locked[u]) push(v, u); }
      }
    }

    // ---- checks ----
    function flips(v, other, x, y, z) { // would moving v to (x,y,z) turn any of its triangles (not shared with other)?
      for (var r = vstart[v], e = r + vcount[v]; r < e; r++) {
        var tf = refs[r];
        if (tdead[tf]) continue;
        var i0 = T[3 * tf], i1 = T[3 * tf + 1], i2 = T[3 * tf + 2];
        if (i0 === other || i1 === other || i2 === other) continue;
        var a = 3 * i0, b = 3 * i1, c = 3 * i2;
        var ax = P[a], ay = P[a + 1], az = P[a + 2], bx = P[b], by = P[b + 1], bz = P[b + 2], cx = P[c], cy = P[c + 1], cz = P[c + 2];
        var ux = bx - ax, uy = by - ay, uz = bz - az, wx = cx - ax, wy = cy - ay, wz = cz - az;
        var ox = uy * wz - uz * wy, oy = uz * wx - ux * wz, oz = ux * wy - uy * wx;
        if (i0 === v) { ax = x; ay = y; az = z; } else if (i1 === v) { bx = x; by = y; bz = z; } else { cx = x; cy = y; cz = z; }
        ux = bx - ax; uy = by - ay; uz = bz - az; wx = cx - ax; wy = cy - ay; wz = cz - az;
        var nx = uy * wz - uz * wy, ny = uz * wx - ux * wz, nz = ux * wy - uy * wx;
        var lo = Math.sqrt(ox * ox + oy * oy + oz * oz), ln = Math.sqrt(nx * nx + ny * ny + nz * nz);
        if (!(ln > 0)) return true;
        if (lo > 0 && ox * nx + oy * ny + oz * nz < FLIP_DOT * lo * ln) return true;
      }
      return false;
    }
    function liveCount(v) {
      var n = 0;
      for (var r = vstart[v], e = r + vcount[v]; r < e; r++) if (!tdead[refs[r]]) n++;
      return n;
    }
    // link condition: the two ends share exactly the vertices opposite the edge (2 inside, 1 on a border)
    var lastShared = 0;
    function linkOk(a, b) {
      gather(a);
      var shared = -1, j;
      for (j = 0; j < nbn; j++) if (nb[j] === b) { shared = nbCnt[j]; break; }
      if (shared !== 1 && shared !== 2) return false;
      if (shared === 2 && border[a] && border[b]) return false; // inner edge joining two border points: a pinch
      var m = ++markCtr;
      for (j = 0; j < nbn; j++) mark[nb[j]] = m;
      var common = 0, m2 = ++markCtr;
      for (var r = vstart[b], e = r + vcount[b]; r < e; r++) {
        var tf = refs[r];
        if (tdead[tf]) continue;
        for (var q = 0; q < 3; q++) {
          var u = T[3 * tf + q];
          if (u !== a && u !== b && mark[u] === m) { mark[u] = m2; common++; }
        }
      }
      if (common !== shared) return false;
      if (!border[a] && !border[b] && liveCount(a) + liveCount(b) - 2 * shared < 3) return false; // tetrahedron
      lastShared = shared;
      return true;
    }

    // ---- collapse b into a at (x,y,z) ----
    function collapse(a, b, x, y, z) {
      var removed = 0, need = refsLen + vcount[a] + vcount[b], r, e, tf, n = 0, start = refsLen;
      if (need > refs.length) refs = grownI32(refs, need);
      for (r = vstart[a], e = r + vcount[a]; r < e; r++) {
        tf = refs[r];
        if (tdead[tf]) continue;
        if (T[3 * tf] === b || T[3 * tf + 1] === b || T[3 * tf + 2] === b) { tdead[tf] = 1; removed++; continue; }
        refs[start + n++] = tf;
      }
      for (r = vstart[b], e = r + vcount[b]; r < e; r++) {
        tf = refs[r];
        if (tdead[tf]) continue;
        for (var q = 0; q < 3; q++) if (T[3 * tf + q] === b) T[3 * tf + q] = a;
        refs[start + n++] = tf;
      }
      refsLen = start + n; vstart[a] = start; vcount[a] = n;
      P[3 * a] = x; P[3 * a + 1] = y; P[3 * a + 2] = z;
      for (q = 0; q < 10; q++) Q[10 * a + q] += Q[10 * b + q];
      vdead[b] = 1; border[a] |= border[b]; vstamp[a]++;
      gather(a);
      for (var j = 0; j < nbn; j++) if (!locked[nb[j]]) push(a, nb[j]);
      return removed;
    }

    // ---- main loop; when the heap runs dry, refill it (refused edges may have become fine) until no progress ----
    var live = nt, progress = false;
    pushAll();
    while (live > target) {
      if (hsize === 0) {
        if (!progress) break;
        progress = false; pushAll();
        if (hsize === 0) break;
        continue;
      }
      var id = pop(), a = ea[id], b = eb[id];
      if (vdead[a] || vdead[b] || esa[id] !== vstamp[a] || esb[id] !== vstamp[b]) continue;
      edgeCost(a, b);
      var x = BX, y = BY, z = BZ;
      if (!linkOk(a, b)) continue;
      if (live - lastShared < MIN_TRIS) continue;
      if (flips(a, b, x, y, z) || flips(b, a, x, y, z)) continue;
      live -= collapse(a, b, x, y, z);
      progress = true;
    }

    // ---- compact ----
    var map = new Int32Array(nv).fill(-1), ov = [], ot = [], cnt = 0;
    for (f = 0; f < nt; f++) {
      if (tdead[f]) continue;
      for (k = 0; k < 3; k++) {
        var o = T[3 * f + k];
        if (map[o] < 0) { map[o] = cnt++; ov.push(P[3 * o], P[3 * o + 1], P[3 * o + 2]); }
        ot.push(map[o]);
      }
    }
    return { v: ov, t: ot };
  }

  function simplifyModel(model, target) {
    var total = 0;
    model.forEach(function (s) { total += s.t.length / 3; });
    if (total <= target) return model.map(copyShell);
    return model.map(function (s) {
      return simplifyShell(s, Math.max(MIN_TRIS, Math.round(target * (s.t.length / 3) / total)));
    });
  }

  return { simplifyModel: simplifyModel, simplifyShell: simplifyShell };
});
