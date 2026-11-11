/* Dependency-free mesh maths for the image3d editor: weld, split, measure, scale, orient, delete pieces, cut.
 *
 * A shell is {v: [x,y,z, ...], t: [i,j,k, ...]} with shared (welded) vertices and outward-facing CCW triangles
 * (same as gui/js/geom.js). A model is an array of shells. Every function is pure (returns new arrays).
 * Units: millimetres.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else { root.I3D = root.I3D || {}; root.I3D.mesh = factory(); }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  var AXES = { x: 0, y: 1, z: 2 };

  // ---------- building shells ----------
  // keep only the vertices the triangles use, renumbered
  function compact(v, t) {
    var map = new Int32Array(v.length / 3).fill(-1), nv = [], nt = new Array(t.length), n = 0;
    for (var i = 0; i < t.length; i++) {
      var o = t[i];
      if (map[o] < 0) { map[o] = n++; nv.push(v[3 * o], v[3 * o + 1], v[3 * o + 2]); }
      nt[i] = map[o];
    }
    return { v: nv, t: nt };
  }

  // positions: flat triangle soup (9 numbers per triangle) or an indexed {v,t}; merges vertices closer than ~tol
  function weld(positions, tol) {
    tol = tol || 1e-5;
    var src = positions && positions.v && positions.t ? positions : null; // else a flat soup: Array or typed array
    var pv = src ? src.v : positions, n = pv.length / 3;
    var seen = new Map(), remap = new Int32Array(n), v = [], i;
    for (i = 0; i < n; i++) {
      var key = Math.round(pv[3 * i] / tol) + ',' + Math.round(pv[3 * i + 1] / tol) + ',' + Math.round(pv[3 * i + 2] / tol);
      var id = seen.get(key);
      if (id === undefined) { id = v.length / 3; seen.set(key, id); v.push(pv[3 * i], pv[3 * i + 1], pv[3 * i + 2]); }
      remap[i] = id;
    }
    var it = src ? src.t : null, t = [];
    var tn = src ? it.length : n;
    for (i = 0; i + 2 < tn; i += 3) {
      var a = src ? remap[it[i]] : remap[i], b = src ? remap[it[i + 1]] : remap[i + 1], c = src ? remap[it[i + 2]] : remap[i + 2];
      if (a !== b && b !== c && a !== c) t.push(a, b, c); // drops degenerate triangles
    }
    return compact(v, t);
  }

  // connected pieces (triangles that share a vertex), largest volume first
  function split(shell) {
    var nv = shell.v.length / 3, t = shell.t, parent = new Int32Array(nv), i;
    for (i = 0; i < nv; i++) parent[i] = i;
    function find(x) { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; }
    for (i = 0; i < t.length; i += 3) {
      var r0 = find(t[i]), r1 = find(t[i + 1]), r2 = find(t[i + 2]);
      if (r1 !== r0) parent[r1] = r0;
      if (r2 !== r0) parent[r2] = r0;
    }
    var groups = new Map(), order = [];
    for (i = 0; i < t.length; i += 3) {
      var r = find(t[i]), g = groups.get(r);
      if (!g) { g = []; groups.set(r, g); order.push(g); }
      g.push(t[i], t[i + 1], t[i + 2]);
    }
    var pieces = order.map(function (g) { return compact(shell.v, g); });
    var vols = pieces.map(volume);
    var idx = pieces.map(function (_, k) { return k; });
    idx.sort(function (a, b) { return vols[b] - vols[a] || a - b; });
    return idx.map(function (k) { return pieces[k]; });
  }

  // ---------- measuring ----------
  function bbox(model) {
    var mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity], any = false;
    model.forEach(function (s) {
      for (var i = 0; i < s.v.length; i += 3) for (var a = 0; a < 3; a++) {
        any = true;
        if (s.v[i + a] < mn[a]) mn[a] = s.v[i + a];
        if (s.v[i + a] > mx[a]) mx[a] = s.v[i + a];
      }
    });
    if (!any) return { min: [0, 0, 0], max: [0, 0, 0], size: [0, 0, 0] };
    return { min: mn, max: mx, size: [mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]] };
  }
  function diag(model) { var s = bbox(model).size; return Math.sqrt(s[0] * s[0] + s[1] * s[1] + s[2] * s[2]); }

  // |signed-tetra sum|, measured from the first vertex to keep float error small far from the origin
  function volume(shell) {
    var v = shell.v, t = shell.t, sum = 0;
    if (!t.length) return 0;
    var ox = v[0], oy = v[1], oz = v[2];
    for (var i = 0; i < t.length; i += 3) {
      var a = 3 * t[i], b = 3 * t[i + 1], c = 3 * t[i + 2];
      var ax = v[a] - ox, ay = v[a + 1] - oy, az = v[a + 2] - oz;
      var bx = v[b] - ox, by = v[b + 1] - oy, bz = v[b + 2] - oz;
      var cx = v[c] - ox, cy = v[c + 1] - oy, cz = v[c + 2] - oz;
      sum += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx);
    }
    return Math.abs(sum / 6);
  }

  // every edge used exactly twice, once in each direction
  function isClosed(shell) {
    var t = shell.t, nv = shell.v.length / 3, dir = new Map(), i;
    if (!t.length) return false;
    for (i = 0; i < t.length; i += 3) {
      for (var k = 0; k < 3; k++) {
        var key = t[i + k] * nv + t[i + (k + 1) % 3];
        if (dir.has(key)) return false;
        dir.set(key, 1);
      }
    }
    var ok = true;
    dir.forEach(function (_, key) {
      var a = Math.floor(key / nv), b = key - a * nv;
      if (!dir.has(b * nv + a)) ok = false;
    });
    return ok;
  }

  // ---------- transforms ----------
  function mapShells(model, fn) {
    return model.map(function (s) {
      var v = new Array(s.v.length);
      for (var i = 0; i < s.v.length; i += 3) fn(s.v, i, v);
      return { v: v, t: s.t.slice() };
    });
  }
  function scale(model, k) {
    return mapShells(model, function (a, i, o) { o[i] = a[i] * k; o[i + 1] = a[i + 1] * k; o[i + 2] = a[i + 2] * k; });
  }
  function scaleToLongest(model, mm) {
    var s = bbox(model).size, longest = Math.max(s[0], s[1], s[2]);
    return longest > 0 ? scale(model, mm / longest) : scale(model, 1);
  }
  // +90 degrees about a world axis through the origin (right-handed); layFlat re-seats the result
  function rotate90(model, axis) {
    var a = AXES[axis];
    if (a === undefined) throw new Error('axis must be x, y or z');
    var p = (a + 1) % 3, q = (a + 2) % 3;
    return mapShells(model, function (s, i, o) {
      o[i + a] = s[i + a]; o[i + p] = -s[i + q]; o[i + q] = s[i + p];
    });
  }
  // min z = 0, bounding box centred on x/y = 0
  function layFlat(model) {
    var b = bbox(model), cx = (b.min[0] + b.max[0]) / 2, cy = (b.min[1] + b.max[1]) / 2, z0 = b.min[2];
    return mapShells(model, function (s, i, o) { o[i] = s[i] - cx; o[i + 1] = s[i + 1] - cy; o[i + 2] = s[i + 2] - z0; });
  }

  // ---------- deleting pieces ----------
  function removePiece(model, index) {
    return model.filter(function (_, i) { return i !== index; }).map(copyShell);
  }
  function copyShell(s) { return { v: s.v.slice(), t: s.t.slice() }; }
  function keepLargest(model) {
    var best = -1, bv = -1;
    model.forEach(function (s, i) { var v = volume(s); if (v > bv) { bv = v; best = i; } });
    return best < 0 ? [] : [copyShell(model[best])];
  }
  // drops pieces whose bbox diagonal is under `fraction` of the whole model's; never drops everything
  function dropSmall(model, fraction) {
    fraction = fraction == null ? 0.01 : fraction;
    var limit = fraction * diag(model);
    var kept = model.filter(function (s) { return diag([s]) >= limit; });
    return kept.length ? kept.map(copyShell) : keepLargest(model);
  }

  // ---------- cutting ----------
  // cap triangulation: ear clipping in 2D. pos(id) -> [u,v]. polygon = array of vertex ids, CCW. Returns id triples.
  function cross2(ax, ay, bx, by, cx, cy) { return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax); }

  function earClip(ids, pos) {
    var n = ids.length, tris = [], i;
    if (n < 3) return tris;
    var X = [], Y = [], prev = [], next = [], minx = Infinity, maxx = -Infinity, miny = Infinity, maxy = -Infinity;
    for (i = 0; i < n; i++) {
      var p = pos(ids[i]); X.push(p[0]); Y.push(p[1]); prev.push((i + n - 1) % n); next.push((i + 1) % n);
      minx = Math.min(minx, p[0]); maxx = Math.max(maxx, p[0]); miny = Math.min(miny, p[1]); maxy = Math.max(maxy, p[1]);
    }
    var ext = Math.max(maxx - minx, maxy - miny), dtol = 1e-12 * ext; // distance tolerance: anything closer than this to a line counts as on it
    function cr(a, b, c) { return cross2(X[a], Y[a], X[b], Y[b], X[c], Y[c]); }
    function same(a, b) { return X[a] === X[b] && Y[a] === Y[b]; }
    function dist(a, b) { return Math.hypot(X[b] - X[a], Y[b] - Y[a]); }
    // strictly convex corner, judged by the height of c above line a-b (not by area, which vanishes for fine loops)
    function convex(a, b, c) { return cr(a, b, c) > dtol * dist(a, b); }
    function isEar(a, b, c) {
      var tab = dtol * dist(a, b), tbc = dtol * dist(b, c), tca = dtol * dist(c, a);
      for (var m = next[c]; m !== a; m = next[m]) {
        if (same(m, a) || same(m, b) || same(m, c)) continue; // bridge duplicates sit exactly on ear corners
        // inside or on an edge (within float noise): a diagonal through a vertex would leave a T-junction
        if (cr(a, b, m) >= -tab && cr(b, c, m) >= -tbc && cr(c, a, m) >= -tca) return false;
      }
      return true;
    }
    function clip(b, emit) {
      var a = prev[b], c = next[b];
      if (emit) tris.push([ids[a], ids[b], ids[c]]);
      next[a] = c; prev[c] = a; return a;
    }
    var left = n, cur = 0;
    while (left > 3) {
      var found = -1, k = cur, tries = 0;
      do {
        if (convex(prev[k], k, next[k]) && isEar(prev[k], k, next[k])) { found = k; break; }
        k = next[k]; tries++;
      } while (tries < left);
      if (found < 0) { // degenerate input: clip the most convex corner anyway, or drop a flat one
        var bestK = -1, bestC = -Infinity;
        k = cur;
        for (tries = 0; tries < left; tries++, k = next[k]) { var cv = cr(prev[k], k, next[k]) / (dist(prev[k], k) || 1); if (cv > bestC) { bestC = cv; bestK = k; } }
        cur = clip(bestK, bestC > dtol);
      } else cur = clip(found, true);
      left--;
    }
    if (left === 3 && convex(prev[cur], cur, next[cur])) tris.push([ids[prev[cur]], ids[cur], ids[next[cur]]]);
    return tris;
  }

  function pointInPoly(x, y, poly, pos) {
    var inside = false;
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      var a = pos(poly[i]), b = pos(poly[j]);
      if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
    }
    return inside;
  }
  function polyArea(poly, pos) {
    var s = 0;
    for (var i = 0; i < poly.length; i++) { var a = pos(poly[i]), b = pos(poly[(i + 1) % poly.length]); s += a[0] * b[1] - b[0] * a[1]; }
    return s / 2;
  }

  // merge CW holes into a CCW outer polygon with zero-width bridges (Eberly), then ear-clip
  function triangulateWithHoles(outer, holes, pos) {
    var poly = outer.slice();
    var order = holes.map(function (h) {
      var mi = 0; for (var i = 1; i < h.length; i++) if (pos(h[i])[0] > pos(h[mi])[0]) mi = i;
      return { h: h, mi: mi };
    }).sort(function (a, b) { return pos(b.h[b.mi])[0] - pos(a.h[a.mi])[0]; });
    order.forEach(function (o) {
      var h = o.h.slice(o.mi).concat(o.h.slice(0, o.mi)); // starts at the hole's rightmost vertex M
      var M = pos(h[0]), mx = M[0], my = M[1], bestX = Infinity, pi = -1, i;
      for (i = 0; i < poly.length; i++) { // nearest outer edge hit by a ray from M towards +u
        var a = pos(poly[i]), b = pos(poly[(i + 1) % poly.length]);
        if ((a[1] <= my && b[1] >= my) || (b[1] <= my && a[1] >= my)) {
          if (a[1] === b[1]) continue;
          var x = a[0] + (my - a[1]) * (b[0] - a[0]) / (b[1] - a[1]);
          if (x >= mx && x < bestX) { bestX = x; pi = a[0] > b[0] ? i : (i + 1) % poly.length; }
        }
      }
      if (pi < 0) pi = 0;
      var P = pos(poly[pi]), I = [bestX, my];
      // vertices inside triangle M-I-P block the bridge: take the one making the smallest angle with the ray
      var bestCos = -Infinity;
      if (isFinite(bestX)) for (i = 0; i < poly.length; i++) {
        var q = pos(poly[i]);
        if (i === pi || (q[0] === P[0] && q[1] === P[1])) continue;
        var c1 = cross2(mx, my, I[0], I[1], q[0], q[1]), c2 = cross2(I[0], I[1], P[0], P[1], q[0], q[1]), c3 = cross2(P[0], P[1], mx, my, q[0], q[1]);
        if (!((c1 >= 0 && c2 >= 0 && c3 >= 0) || (c1 <= 0 && c2 <= 0 && c3 <= 0))) continue;
        var dist = Math.hypot(q[0] - mx, q[1] - my), cs = dist > 0 ? (q[0] - mx) / dist : -Infinity;
        if (cs > bestCos) { bestCos = cs; pi = i; }
      }
      // earlier bridges leave several copies of the same point: use the copy whose corner faces M
      var want = pos(poly[pi]), cn = poly.length;
      for (i = 0; i < cn; i++) {
        var pp = pos(poly[i]);
        if (pp[0] !== want[0] || pp[1] !== want[1]) continue;
        var pr = pos(poly[(i + cn - 1) % cn]), nx = pos(poly[(i + 1) % cn]);
        var l1 = cross2(pr[0], pr[1], pp[0], pp[1], mx, my) > 0, l2 = cross2(pp[0], pp[1], nx[0], nx[1], mx, my) > 0;
        if (cross2(pr[0], pr[1], pp[0], pp[1], nx[0], nx[1]) > 0 ? (l1 && l2) : (l1 || l2)) { pi = i; break; }
      }
      poly = poly.slice(0, pi + 1).concat(h, [h[0]], [poly[pi]], poly.slice(pi + 1));
    });
    return earClip(poly, pos);
  }

  function cutShell(sh, a, value, sgn) {
    var nv0 = sh.v.length / 3, bb = bbox([sh]);
    var eps = 1e-7 * Math.sqrt(bb.size[0] * bb.size[0] + bb.size[1] * bb.size[1] + bb.size[2] * bb.size[2]);
    var V = sh.v.slice(), D = new Array(nv0), i;
    for (i = 0; i < nv0; i++) { // signed distance, positive on the kept side; near-plane vertices snap onto the plane
      var d = (V[3 * i + a] - value) * sgn;
      if (Math.abs(d) <= eps) { d = 0; V[3 * i + a] = value; }
      D[i] = d;
    }
    var cache = new Map(), T = [], edges = [];
    function cross(i0, j0) { // one shared vertex per cut edge, so neighbouring walls and the cap agree
      var lo = Math.min(i0, j0), hi = Math.max(i0, j0), key = lo * nv0 + hi, id = cache.get(key);
      if (id !== undefined) return id;
      var f = D[lo] / (D[lo] - D[hi]);
      id = V.length / 3;
      for (var c = 0; c < 3; c++) V.push(c === a ? value : V[3 * lo + c] + f * (V[3 * hi + c] - V[3 * lo + c]));
      D.push(0); cache.set(key, id); return id;
    }
    for (i = 0; i < sh.t.length; i += 3) {
      var tri = [sh.t[i], sh.t[i + 1], sh.t[i + 2]];
      if (D[tri[0]] <= 0 && D[tri[1]] <= 0 && D[tri[2]] <= 0) continue; // removed (or lying in the plane: the cap replaces it)
      var poly = [], k;
      for (k = 0; k < 3; k++) {
        var cu = tri[k], nx = tri[(k + 1) % 3];
        if (D[cu] >= 0) poly.push(cu);
        if ((D[cu] > 0 && D[nx] < 0) || (D[cu] < 0 && D[nx] > 0)) poly.push(cross(cu, nx));
      }
      for (k = 1; k + 1 < poly.length; k++) T.push(poly[0], poly[k], poly[k + 1]);
      for (k = 0; k < poly.length; k++) {
        var e0 = poly[k], e1 = poly[(k + 1) % poly.length];
        if (D[e0] === 0 && D[e1] === 0) edges.push([e0, e1]);
      }
    }
    if (!T.length) return [];

    // chain the plane edges into closed loops (an open mesh leaves broken chains, which just get no cap)
    var out = new Map(), used = new Array(edges.length).fill(false), loops = [], e;
    edges.forEach(function (ed, idx) { var l = out.get(ed[0]); if (!l) out.set(ed[0], l = []); l.push(idx); });
    for (e = 0; e < edges.length; e++) {
      if (used[e]) continue;
      used[e] = true;
      var loop = [edges[e][0]], at = edges[e][1], ok = true;
      while (at !== loop[0]) {
        loop.push(at);
        var cand = out.get(at), nxt = -1;
        if (cand) for (var c = 0; c < cand.length; c++) if (!used[cand[c]]) { nxt = cand[c]; break; }
        if (nxt < 0) { ok = false; break; }
        used[nxt] = true; at = edges[nxt][1];
      }
      if (ok && loop.length >= 3) loops.push(loop.reverse()); // reversed: the cap runs opposite to the walls
    }
    // the cap faces away from the kept side; (u,v) is a right-handed frame about that normal
    var u = sgn > 0 ? (a + 2) % 3 : (a + 1) % 3, w = sgn > 0 ? (a + 1) % 3 : (a + 2) % 3;
    function pos(id) { return [V[3 * id + u], V[3 * id + w]]; }
    loops = loops.filter(function (l) { return Math.abs(polyArea(l, pos)) > 0; });
    var depth = loops.map(function (l, li) {
      var p = pos(l[0]), dp = 0;
      loops.forEach(function (o, oi) { if (oi !== li && pointInPoly(p[0], p[1], o, pos)) dp++; });
      return dp;
    });
    var parent = loops.map(function (l, li) { // innermost loop that contains this one
      var p = pos(l[0]), best = -1, ba = Infinity;
      loops.forEach(function (o, oi) {
        if (oi === li || depth[oi] !== depth[li] - 1 || !pointInPoly(p[0], p[1], o, pos)) return;
        var ar = Math.abs(polyArea(o, pos)); if (ar < ba) { ba = ar; best = oi; }
      });
      return best;
    });
    loops.forEach(function (l, li) { // even depth: outline (CCW); odd depth: hole (CW)
      if ((polyArea(l, pos) > 0) !== (depth[li] % 2 === 0)) l.reverse();
    });
    loops.forEach(function (l, li) {
      if (depth[li] % 2) return;
      var holes = [];
      loops.forEach(function (h, hi) { if (parent[hi] === li && depth[hi] % 2) holes.push(h); });
      triangulateWithHoles(l, holes, pos).forEach(function (tr) { T.push(tr[0], tr[1], tr[2]); });
    });
    return split(compact(V, T)); // a cut can leave a shell in several separate pieces
  }

  function cut(model, axis, value, keep) {
    var a = AXES[axis];
    if (a === undefined) throw new Error('axis must be x, y or z');
    if (keep !== 'above' && keep !== 'below') throw new Error("keep must be 'above' or 'below'");
    var out = [];
    model.forEach(function (s) { cutShell(s, a, value, keep === 'above' ? 1 : -1).forEach(function (p) { out.push(p); }); });
    if (!out.length) throw new Error('cut removes everything');
    return out;
  }

  return {
    weld: weld, split: split, bbox: bbox, volume: volume, isClosed: isClosed,
    scale: scale, scaleToLongest: scaleToLongest, rotate90: rotate90, layFlat: layFlat,
    removePiece: removePiece, keepLargest: keepLargest, dropSmall: dropSmall, cut: cut
  };
});
