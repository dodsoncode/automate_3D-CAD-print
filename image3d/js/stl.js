/* Binary / ASCII STL reader and binary writer. No dependencies.
 *
 * write(model, name) -> Uint8Array   binary STL of every shell, with computed unit normals
 * read(bytes)        -> number[]     triangle soup (9 numbers per triangle); binary or ASCII
 * A model is an array of shells {v: [x,y,z, ...], t: [i,j,k, ...]}. Units: millimetres.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else { root.I3D = root.I3D || {}; root.I3D.stl = factory(); }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function write(model, name) {
    name = String(name == null ? 'image3d' : name);
    if (/^solid/i.test(name)) name = '_' + name; // a binary header starting with "solid" fools some readers
    var n = 0, s, i;
    for (s = 0; s < model.length; s++) n += model[s].t.length / 3;
    var out = new Uint8Array(84 + 50 * n), dv = new DataView(out.buffer);
    for (i = 0; i < name.length && i < 80; i++) out[i] = name.charCodeAt(i) & 0x7f;
    dv.setUint32(80, n, true);
    var off = 84;
    for (s = 0; s < model.length; s++) {
      var v = model[s].v, t = model[s].t;
      for (i = 0; i < t.length; i += 3) {
        var a = t[i] * 3, b = t[i + 1] * 3, c = t[i + 2] * 3;
        var ux = v[b] - v[a], uy = v[b + 1] - v[a + 1], uz = v[b + 2] - v[a + 2];
        var wx = v[c] - v[a], wy = v[c + 1] - v[a + 1], wz = v[c + 2] - v[a + 2];
        var nx = uy * wz - uz * wy, ny = uz * wx - ux * wz, nz = ux * wy - uy * wx;
        var len = Math.sqrt(nx * nx + ny * ny + nz * nz);
        if (len > 0) { nx /= len; ny /= len; nz /= len; } else { nx = ny = nz = 0; }
        dv.setFloat32(off, nx, true); dv.setFloat32(off + 4, ny, true); dv.setFloat32(off + 8, nz, true);
        var p = [a, b, c];
        for (var k = 0; k < 3; k++) {
          dv.setFloat32(off + 12 + 12 * k, v[p[k]], true);
          dv.setFloat32(off + 16 + 12 * k, v[p[k] + 1], true);
          dv.setFloat32(off + 20 + 12 * k, v[p[k] + 2], true);
        }
        off += 50; // 2 attribute bytes stay 0
      }
    }
    return out;
  }

  function read(bytes) {
    var soup = [], i;
    if (bytes.length >= 84) {
      var dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
      var n = dv.getUint32(80, true);
      if (bytes.length === 84 + 50 * n) { // size matches the binary layout (also true for binary files that start with "solid")
        for (i = 0; i < n; i++) {
          var o = 84 + 50 * i + 12;
          for (var k = 0; k < 9; k++) soup.push(dv.getFloat32(o + 4 * k, true));
        }
        return soup;
      }
    }
    var text = '';
    for (i = 0; i < bytes.length; i += 32768) text += String.fromCharCode.apply(null, bytes.subarray(i, i + 32768));
    if (!/^\s*solid/i.test(text)) throw new Error('not an STL file');
    var re = /vertex\s+(\S+)\s+(\S+)\s+(\S+)/gi, m;
    while ((m = re.exec(text))) soup.push(parseFloat(m[1]), parseFloat(m[2]), parseFloat(m[3]));
    if (soup.length % 9 !== 0) throw new Error('ASCII STL is truncated');
    return soup;
  }

  return { write: write, read: read };
});
