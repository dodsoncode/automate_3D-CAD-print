/* Tiny solid-modelling kit: closed "shells" made by extruding 2D polygons (with holes).
 *
 * A shell is {v: [x,y,z, ...], t: [i,j,k, ...]} with shared vertices, outward-facing CCW triangles.
 * Holes are cut inside ONE polygon (never by overlapping shells), so a part = a few shells that overlap or
 * touch; slicers union overlapping closed shells. Needs THREE.ShapeUtils for cap triangulation only.
 * Units: millimetres. Angles: degrees.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('three'));
  else { root.WD = root.WD || {}; root.WD.geom = factory(root.THREE); }
})(typeof self !== 'undefined' ? self : this, function (THREE) {
  'use strict';
  var DEG = Math.PI / 180;

  // ---------- 2D polygon helpers (points are [x, y]) ----------
  function signedArea(pts) {
    var a = 0, n = pts.length;
    for (var i = 0; i < n; i++) { var p = pts[i], q = pts[(i + 1) % n]; a += p[0] * q[1] - q[0] * p[1]; }
    return a / 2;
  }
  function asCCW(pts) { return signedArea(pts) > 0 ? pts : pts.slice().reverse(); }
  function asCW(pts) { return signedArea(pts) < 0 ? pts : pts.slice().reverse(); }

  function rect(cx, cy, w, h) {
    return [[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2], [cx + w / 2, cy + h / 2], [cx - w / 2, cy + h / 2]];
  }
  function circle(cx, cy, r, n) {
    n = n || 40; var pts = [];
    for (var i = 0; i < n; i++) { var a = 2 * Math.PI * i / n; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
    return pts;
  }
  function rrect(cx, cy, w, h, r, seg) {
    seg = seg || 8; r = Math.max(0.01, Math.min(r, w / 2 - 0.01, h / 2 - 0.01));
    var pts = [], hw = w / 2 - r, hh = h / 2 - r;
    var corners = [[hw, hh, 0], [-hw, hh, 90], [-hw, -hh, 180], [hw, -hh, 270]];
    for (var c = 0; c < 4; c++) {
      for (var i = 0; i <= seg; i++) {
        var a = (corners[c][2] + 90 * i / seg) * DEG;
        pts.push([cx + corners[c][0] + r * Math.cos(a), cy + corners[c][1] + r * Math.sin(a)]);
      }
    }
    return pts;
  }
  // Outline of a polyline "bar" of constant width: mitred bends, flat end at the last point, round cap at the first.
  function stroke(points, width, capSeg) {
    capSeg = capSeg || 14; var hw = width / 2, n = points.length, i;
    var dirs = [], norms = [];
    for (i = 0; i < n - 1; i++) {
      var dx = points[i + 1][0] - points[i][0], dy = points[i + 1][1] - points[i][1], L = Math.hypot(dx, dy);
      dirs.push([dx / L, dy / L]); norms.push([-dy / L, dx / L]);
    }
    var left = [], right = [];
    left.push([points[0][0] + norms[0][0] * hw, points[0][1] + norms[0][1] * hw]);
    right.push([points[0][0] - norms[0][0] * hw, points[0][1] - norms[0][1] * hw]);
    for (i = 1; i < n - 1; i++) {
      var n1 = norms[i - 1], n2 = norms[i], k = 1 + n1[0] * n2[0] + n1[1] * n2[1];
      var mx = (n1[0] + n2[0]) / k * hw, my = (n1[1] + n2[1]) / k * hw;
      left.push([points[i][0] + mx, points[i][1] + my]);
      right.push([points[i][0] - mx, points[i][1] - my]);
    }
    var nl = norms[n - 2];
    left.push([points[n - 1][0] + nl[0] * hw, points[n - 1][1] + nl[1] * hw]);
    right.push([points[n - 1][0] - nl[0] * hw, points[n - 1][1] - nl[1] * hw]);
    // loop: right side forward, then left side backward, then the round cap around the start
    var poly = right.slice();
    for (i = left.length - 1; i >= 0; i--) poly.push(left[i]);
    var a0 = Math.atan2(norms[0][1], norms[0][0]);        // start at the left normal, sweep through the back
    for (i = 1; i < capSeg; i++) {
      var a = a0 + Math.PI * i / capSeg;
      poly.push([points[0][0] + hw * Math.cos(a), points[0][1] + hw * Math.sin(a)]);
    }
    return poly;
  }
  function pointInPoly(p, poly) {
    var inside = false;
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      var xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
      if ((yi > p[1]) !== (yj > p[1]) && p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }
  function distToSegment(p, a, b) {
    var dx = b[0] - a[0], dy = b[1] - a[1], L2 = dx * dx + dy * dy;
    var t = L2 === 0 ? 0 : Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2));
    return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
  }
  function distToPolyEdge(p, poly) {
    var d = Infinity;
    for (var i = 0; i < poly.length; i++) d = Math.min(d, distToSegment(p, poly[i], poly[(i + 1) % poly.length]));
    return d;
  }

  // ---------- extrusion ----------
  // Make every cap triangle counter-clockwise. Zero-area triangles (three collinear points, which happen when
  // hole corners line up) have no orientation of their own, so they copy it from a neighbour sharing an edge.
  function orientTriangles(tri, pts) {
    var n = tri.length, done = [], i, k, c;
    for (i = 0; i < n; i++) {
      var a = tri[i][0], b = tri[i][1], cc = tri[i][2];
      var area = (pts[b][0] - pts[a][0]) * (pts[cc][1] - pts[a][1]) - (pts[cc][0] - pts[a][0]) * (pts[b][1] - pts[a][1]);
      if (Math.abs(area) > 1e-9) { if (area < 0) { tri[i][1] = cc; tri[i][2] = b; } done.push(true); } else done.push(false);
    }
    var edges = {};
    function key(x, y) { return x < y ? x + '_' + y : y + '_' + x; }
    for (i = 0; i < n; i++) for (k = 0; k < 3; k++) { var kk = key(tri[i][k], tri[i][(k + 1) % 3]); (edges[kk] = edges[kk] || []).push(i); }
    var changed = true, guard = 0;
    while (changed && guard++ < 100) {
      changed = false;
      for (i = 0; i < n; i++) {
        if (done[i]) continue;
        for (k = 0; k < 3 && !done[i]; k++) {
          var x = tri[i][k], y = tri[i][(k + 1) % 3], list = edges[key(x, y)];
          for (c = 0; c < list.length; c++) {
            var j = list[c]; if (j === i || !done[j]) continue;
            var sameDir = false;
            for (var m = 0; m < 3; m++) if (tri[j][m] === x && tri[j][(m + 1) % 3] === y) sameDir = true;
            if (sameDir) { var tmp = tri[i][1]; tri[i][1] = tri[i][2]; tri[i][2] = tmp; }
            done[i] = true; changed = true; break;
          }
        }
      }
    }
  }

  function extrude(outer, holes, z0, z1) {
    outer = asCCW(outer); holes = (holes || []).map(asCW);
    var rings = [outer].concat(holes), pts = [], starts = [], r, i;
    for (r = 0; r < rings.length; r++) { starts.push(pts.length); for (i = 0; i < rings[r].length; i++) pts.push(rings[r][i]); }
    // Symbolic perturbation: hole corners that line up exactly make the triangulator drop zero-area triangles and
    // leave the cap with gaps. Nudge every point by <= 2 microns (far below print resolution), deterministically.
    pts = pts.map(function (q, idx) { return [q[0] + 0.002 * Math.sin(idx * 12.9898 + 1.3), q[1] + 0.002 * Math.sin(idx * 78.233 + 2.1)]; });
    for (r = 0, i = 0; r < rings.length; r++) rings[r] = rings[r].map(function () { return pts[i++]; });
    outer = rings[0]; holes = rings.slice(1);
    var N = pts.length, v = [], t = [];
    for (i = 0; i < N; i++) v.push(pts[i][0], pts[i][1], z0);
    for (i = 0; i < N; i++) v.push(pts[i][0], pts[i][1], z1);
    var tri = THREE.ShapeUtils.triangulateShape(
      outer.map(function (p) { return new THREE.Vector2(p[0], p[1]); }),
      holes.map(function (h) { return h.map(function (p) { return new THREE.Vector2(p[0], p[1]); }); }));
    if (tri.length !== N + 2 * holes.length - 2) throw new Error('triangulation incomplete (' + tri.length + ' of ' + (N + 2 * holes.length - 2) + ' triangles)');
    orientTriangles(tri, pts);
    for (i = 0; i < tri.length; i++) {
      t.push(N + tri[i][0], N + tri[i][1], N + tri[i][2]);      // top cap, normal +z
      t.push(tri[i][0], tri[i][2], tri[i][1]);                  // bottom cap, normal -z
    }
    for (r = 0; r < rings.length; r++) {
      var n = rings[r].length, s = starts[r];
      for (i = 0; i < n; i++) {
        var bi = s + i, bj = s + (i + 1) % n;
        t.push(bi, bj, N + bj, bi, N + bj, N + bi);
      }
    }
    return { v: v, t: t };
  }

  // ---------- transforms: x' = M x + T, M is a row-major 3x3 ----------
  var I3 = [1, 0, 0, 0, 1, 0, 0, 0, 1];
  function rotX(d) { var c = Math.cos(d * DEG), s = Math.sin(d * DEG); return [1, 0, 0, 0, c, -s, 0, s, c]; }
  function rotY(d) { var c = Math.cos(d * DEG), s = Math.sin(d * DEG); return [c, 0, s, 0, 1, 0, -s, 0, c]; }
  function rotZ(d) { var c = Math.cos(d * DEG), s = Math.sin(d * DEG); return [c, -s, 0, s, c, 0, 0, 0, 1]; }
  function mul3(A, B) {
    var R = [];
    for (var r = 0; r < 3; r++) for (var c = 0; c < 3; c++)
      R.push(A[r * 3] * B[c] + A[r * 3 + 1] * B[3 + c] + A[r * 3 + 2] * B[6 + c]);
    return R;
  }
  function det3(M) {
    return M[0] * (M[4] * M[8] - M[5] * M[7]) - M[1] * (M[3] * M[8] - M[5] * M[6]) + M[2] * (M[3] * M[7] - M[4] * M[6]);
  }
  function transform(shell, M, T) {
    T = T || [0, 0, 0]; var v = shell.v, out = new Array(v.length);
    for (var i = 0; i < v.length; i += 3) {
      var x = v[i], y = v[i + 1], z = v[i + 2];
      out[i] = M[0] * x + M[1] * y + M[2] * z + T[0];
      out[i + 1] = M[3] * x + M[4] * y + M[5] * z + T[1];
      out[i + 2] = M[6] * x + M[7] * y + M[8] * z + T[2];
    }
    var t = shell.t.slice();
    if (det3(M) < 0) for (var k = 0; k < t.length; k += 3) { var tmp = t[k + 1]; t[k + 1] = t[k + 2]; t[k + 2] = tmp; }
    return { v: out, t: t };
  }
  function transformAll(shells, M, T) { return shells.map(function (s) { return transform(s, M, T); }); }

  // Extrude a profile drawn in the (u, w) plane along v (side view), or in (v, w) along u, or (u, v) along w.
  // All three keep a right-handed frame so triangles stay outward-facing.
  function extrudeUV(outer, holes, w0, w1) { return extrude(outer, holes, w0, w1); }            // x=u, y=v, z=w
  function extrudeUW(outer, holes, v0, v1) {                                                   // x=u, y=w, z=-v
    return transform(extrude(outer, holes, -v1, -v0), [1, 0, 0, 0, 0, -1, 0, 1, 0]);          // (x,y,z) -> (x, -z, y)
  }
  function extrudeVW(outer, holes, u0, u1) {                                                   // x=v, y=w, z=u
    return transform(extrude(outer, holes, u0, u1), [0, 0, 1, 1, 0, 0, 0, 1, 0]);              // (x,y,z) -> (z, x, y)
  }

  // ---------- measurement ----------
  function volume(shell) {
    var v = shell.v, t = shell.t, s = 0;
    for (var i = 0; i < t.length; i += 3) {
      var a = t[i] * 3, b = t[i + 1] * 3, c = t[i + 2] * 3;
      s += v[a] * (v[b + 1] * v[c + 2] - v[b + 2] * v[c + 1])
         - v[a + 1] * (v[b] * v[c + 2] - v[b + 2] * v[c])
         + v[a + 2] * (v[b] * v[c + 1] - v[b + 1] * v[c]);
    }
    return s / 6;
  }
  function bbox(shells) {
    var mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
    (Array.isArray(shells) ? shells : [shells]).forEach(function (s) {
      for (var i = 0; i < s.v.length; i += 3) for (var k = 0; k < 3; k++) {
        if (s.v[i + k] < mn[k]) mn[k] = s.v[i + k];
        if (s.v[i + k] > mx[k]) mx[k] = s.v[i + k];
      }
    });
    return { min: mn, max: mx };
  }
  // closed + consistently oriented: every directed edge occurs once and so does its reverse
  function isClosed(shell) {
    var t = shell.t, seen = {}, i, a, b, key;
    for (i = 0; i < t.length; i += 3) {
      for (var e = 0; e < 3; e++) {
        a = t[i + e]; b = t[i + (e + 1) % 3]; key = a + '_' + b;
        if (seen[key]) return false;
        seen[key] = 1;
      }
    }
    for (key in seen) { var p = key.split('_'); if (!seen[p[1] + '_' + p[0]]) return false; }
    return true;
  }

  function toBufferGeometry(shells) {
    var pos = [], idx = [], base = 0;
    shells.forEach(function (s) {
      for (var i = 0; i < s.v.length; i++) pos.push(s.v[i]);
      for (var j = 0; j < s.t.length; j++) idx.push(s.t[j] + base);
      base += s.v.length / 3;
    });
    var g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setIndex(idx);
    g.computeVertexNormals();
    return g;
  }

  return {
    DEG: DEG, I3: I3, rect: rect, circle: circle, rrect: rrect, stroke: stroke, signedArea: signedArea,
    pointInPoly: pointInPoly, distToPolyEdge: distToPolyEdge,
    extrude: extrude, extrudeUV: extrudeUV, extrudeUW: extrudeUW, extrudeVW: extrudeVW,
    rotX: rotX, rotY: rotY, rotZ: rotZ, mul3: mul3, det3: det3, transform: transform, transformAll: transformAll,
    volume: volume, bbox: bbox, isClosed: isClosed, toBufferGeometry: toBufferGeometry
  };
});
