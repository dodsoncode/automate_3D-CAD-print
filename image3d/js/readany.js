/* Dispatches a model file to its reader by extension.
 *
 * readAny(name, bytes) -> number[]   triangle soup from .glb, .obj or .stl (case-insensitive)
 * Browser: I3D.readAny (needs I3D.glb, I3D.obj, I3D.stl loaded first). Node: module.exports = readAny.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory({ glb: require('./glb.js'), obj: require('./obj.js'), stl: require('./stl.js') });
  } else {
    root.I3D = root.I3D || {};
    root.I3D.readAny = factory({ glb: root.I3D.glb, obj: root.I3D.obj, stl: root.I3D.stl });
  }
})(typeof self !== 'undefined' ? self : this, function (readers) {
  'use strict';

  function readAny(name, bytes) {
    var m = /\.([^.\/\\]+)$/.exec(String(name || ''));
    var ext = m ? m[1].toLowerCase() : '';
    if (ext === 'glb') return readers.glb.read(bytes);
    if (ext === 'stl') return readers.stl.read(bytes);
    if (ext === 'obj') {
      var text = '';
      for (var i = 0; i < bytes.length; i += 32768) text += String.fromCharCode.apply(null, bytes.subarray(i, i + 32768));
      return readers.obj.read(text);
    }
    throw new Error('unsupported file');
  }

  return readAny;
});
