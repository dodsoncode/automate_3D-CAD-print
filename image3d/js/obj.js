/* Wavefront OBJ reader. No dependencies.
 *
 * read(text) -> number[]   triangle soup (9 numbers per triangle)
 * Reads "v" and "f" lines only; faces may use v, v/vt, v//vn or v/vt/vn, positive or negative (relative)
 * indices, and any number of corners (fan-triangulated). Coordinates are kept as written (no axis change).
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else { root.I3D = root.I3D || {}; root.I3D.obj = factory(); }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function read(text) {
    var verts = [], soup = [], lines = String(text).split(/\r\n|\r|\n/);
    for (var li = 0; li < lines.length; li++) {
      var line = lines[li].trim();
      var c0 = line.charCodeAt(0);
      if (c0 !== 118 && c0 !== 102) continue; // 'v' or 'f'
      var p = line.split(/\s+/);
      if (p[0] === 'v') {
        var x = parseFloat(p[1]), y = parseFloat(p[2]), z = parseFloat(p[3]);
        if (isNaN(x) || isNaN(y) || isNaN(z)) throw new Error('OBJ vertex is invalid (line ' + (li + 1) + ')');
        verts.push(x, y, z);
      } else if (p[0] === 'f') {
        var n = verts.length / 3, ids = [];
        for (var k = 1; k < p.length; k++) {
          var i = parseInt(p[k].split('/')[0], 10);
          if (isNaN(i) || i === 0) throw new Error('OBJ face is invalid (line ' + (li + 1) + ')');
          i = i < 0 ? n + i : i - 1;
          if (i < 0 || i >= n) throw new Error('OBJ face index is out of range (line ' + (li + 1) + ')');
          ids.push(i * 3);
        }
        for (var f = 1; f + 1 < ids.length; f++) {
          var tri = [ids[0], ids[f], ids[f + 1]];
          for (var q = 0; q < 3; q++) soup.push(verts[tri[q]], verts[tri[q] + 1], verts[tri[q] + 2]);
        }
      }
    }
    return soup;
  }

  return { read: read };
});
