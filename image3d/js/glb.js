/* Binary glTF (GLB) reader. No dependencies.
 *
 * read(bytes) -> number[]   triangle soup (9 numbers per triangle) in the file's units, Z-up
 * Handles the GLB container with an embedded BIN chunk, float POSITION accessors (optionally strided), indices of
 * any integer type or none, triangle primitives only, node hierarchies (matrix or TRS) and several meshes.
 * glTF is Y-up; (x, y, z) -> (x, -z, y) makes the result Z-up. Draco / meshopt files throw Error('compressed').
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else { root.I3D = root.I3D || {}; root.I3D.glb = factory(); }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var SIZES = { 5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4 };
  var COUNTS = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT2: 4, MAT3: 9, MAT4: 16 };

  // column-major 4x4 multiply: a * b
  function mul(a, b) {
    var o = new Array(16);
    for (var c = 0; c < 4; c++) for (var r = 0; r < 4; r++) {
      var s = 0;
      for (var k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k];
      o[c * 4 + r] = s;
    }
    return o;
  }
  function local(n) {
    if (n.matrix) return n.matrix.slice();
    var t = n.translation || [0, 0, 0], q = n.rotation || [0, 0, 0, 1], s = n.scale || [1, 1, 1];
    var x = q[0], y = q[1], z = q[2], w = q[3];
    return [
      (1 - 2 * (y * y + z * z)) * s[0], 2 * (x * y + z * w) * s[0], 2 * (x * z - y * w) * s[0], 0,
      2 * (x * y - z * w) * s[1], (1 - 2 * (x * x + z * z)) * s[1], 2 * (y * z + x * w) * s[1], 0,
      2 * (x * z + y * w) * s[2], 2 * (y * z - x * w) * s[2], (1 - 2 * (x * x + y * y)) * s[2], 0,
      t[0], t[1], t[2], 1];
  }

  function read(bytes) {
    if (bytes.length < 12) throw new Error('not a GLB file');
    var dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    if (dv.getUint32(0, true) !== 0x46546C67) throw new Error('not a GLB file');
    var json = null, bin = null, off = 12, end = Math.min(dv.getUint32(8, true), bytes.length);
    while (off + 8 <= end) {
      var len = dv.getUint32(off, true), type = dv.getUint32(off + 4, true), start = off + 8;
      if (start + len > bytes.length) throw new Error('GLB file is truncated');
      if (type === 0x4E4F534A && json === null) {
        var text = '';
        for (var i = start; i < start + len; i++) text += String.fromCharCode(bytes[i]);
        try { json = JSON.parse(decodeURIComponent(escape(text))); } catch (e) { throw new Error('GLB JSON is invalid'); }
      } else if (type === 0x004E4942 && bin === null) bin = bytes.subarray(start, start + len);
      off = start + len + ((4 - len % 4) % 4);
    }
    if (!json) throw new Error('GLB has no JSON chunk');
    var req = json.extensionsRequired || [];
    if (req.indexOf('KHR_draco_mesh_compression') >= 0 || req.indexOf('EXT_meshopt_compression') >= 0) throw new Error('compressed');

    var accessors = json.accessors || [], views = json.bufferViews || [], meshes = json.meshes || [], nodes = json.nodes || [];

    // element j of accessor a, component c
    function reader(a) {
      var acc = accessors[a];
      if (!acc || acc.bufferView === undefined) throw new Error('GLB accessor has no data');
      var view = views[acc.bufferView], csize = SIZES[acc.componentType], n = COUNTS[acc.type];
      if (!csize || !n) throw new Error('GLB accessor type is not supported');
      if (view.buffer !== 0 || !bin) throw new Error('GLB data must be embedded in the file');
      var base = (view.byteOffset || 0) + (acc.byteOffset || 0), stride = view.byteStride || csize * n;
      if (base + stride * (acc.count - 1) + csize * n > bin.length) throw new Error('GLB file is truncated');
      var bdv = new DataView(bin.buffer, bin.byteOffset, bin.byteLength);
      return {
        count: acc.count,
        get: function (j, c) {
          var p = base + j * stride + c * csize;
          switch (acc.componentType) {
            case 5126: return bdv.getFloat32(p, true);
            case 5125: return bdv.getUint32(p, true);
            case 5123: return bdv.getUint16(p, true);
            case 5121: return bdv.getUint8(p);
            case 5122: return bdv.getInt16(p, true);
            default: return bdv.getInt8(p);
          }
        }
      };
    }

    var soup = [];
    function emit(mesh, m) {
      (mesh.primitives || []).forEach(function (prim) {
        if (prim.mode !== undefined && prim.mode !== 4) return; // triangles only
        if (!prim.attributes || prim.attributes.POSITION === undefined) return;
        var pos = reader(prim.attributes.POSITION), idx = prim.indices !== undefined ? reader(prim.indices) : null;
        var n = idx ? idx.count : pos.count;
        n -= n % 3;
        for (var k = 0; k < n; k++) {
          var vi = idx ? idx.get(k, 0) : k;
          if (vi >= pos.count) throw new Error('GLB index is out of range');
          var x = pos.get(vi, 0), y = pos.get(vi, 1), z = pos.get(vi, 2);
          var wx = m[0] * x + m[4] * y + m[8] * z + m[12];
          var wy = m[1] * x + m[5] * y + m[9] * z + m[13];
          var wz = m[2] * x + m[6] * y + m[10] * z + m[14];
          soup.push(wx, -wz, wy); // Y-up -> Z-up
        }
      });
    }

    var ID = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
    function visit(i, parent, depth) {
      if (depth > 256 || !nodes[i]) throw new Error('GLB node tree is invalid');
      var m = mul(parent, local(nodes[i]));
      if (nodes[i].mesh !== undefined && meshes[nodes[i].mesh]) emit(meshes[nodes[i].mesh], m);
      (nodes[i].children || []).forEach(function (c) { visit(c, m, depth + 1); });
    }
    var roots;
    if (json.scenes && json.scenes.length) roots = (json.scenes[json.scene || 0] || json.scenes[0]).nodes || [];
    else {
      var child = {};
      nodes.forEach(function (n) { (n.children || []).forEach(function (c) { child[c] = true; }); });
      roots = nodes.map(function (_, i) { return i; }).filter(function (i) { return !child[i]; });
    }
    roots.forEach(function (r) { visit(r, ID, 0); });
    if (!nodes.length) meshes.forEach(function (mesh) { emit(mesh, ID); });
    return soup;
  }

  return { read: read };
});
