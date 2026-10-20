/* Bambu Studio multi-material 3MF export for the Walker Designer.
 * Same package layout as cad/make_cube_disk_3mf.py: every printed object is an "assembly" made of parts, and each
 * part carries its AMS slot in Metadata/model_settings.config. One 3MF per print plate (bed).
 * UMD: browser global WalkerExport, or require() in Node (tests). Needs JSZip passed in by the caller. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else { root.WD = root.WD || {}; root.WD.export3mf = factory(); }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  var NS_CORE = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02';
  var NS_PROD = 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06';
  var NS_BBS = 'http://schemas.bambulab.com/package/2021';
  var SUB = '/3D/Objects/object_1.model';

  var uuidN = 0;
  function uuid() {                       // deterministic, so the same design always exports the same bytes
    uuidN++;
    var h = ('00000000' + (uuidN * 2654435761 >>> 0).toString(16)).slice(-8);
    return h + '-0000-4000-8000-' + ('000000000000' + uuidN.toString(16)).slice(-12);
  }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
  function f6(x) { return (Math.round(x * 1e6) / 1e6).toString(); }

  // merge a part's shells into one mesh (slicers union overlapping shells)
  function mergeShells(shells) {
    var v = [], t = [], off = 0;
    shells.forEach(function (s) {
      for (var i = 0; i < s.v.length; i++) v.push(s.v[i]);
      for (var j = 0; j < s.t.length; j++) t.push(s.t[j] + off);
      off += s.v.length / 3;
    });
    return { v: v, t: t };
  }
  function meshXml(m) {
    var o = ['   <mesh>', '    <vertices>'], i;
    for (i = 0; i < m.v.length; i += 3) o.push('     <vertex x="' + f6(m.v[i]) + '" y="' + f6(m.v[i + 1]) + '" z="' + f6(m.v[i + 2]) + '"/>');
    o.push('    </vertices>', '    <triangles>');
    for (i = 0; i < m.t.length; i += 3) o.push('     <triangle v1="' + m.t[i] + '" v2="' + m.t[i + 1] + '" v3="' + m.t[i + 2] + '"/>');
    o.push('    </triangles>', '   </mesh>');
    return o.join('\n');
  }

  var CONTENT_TYPES = '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n' +
    ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n' +
    ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n' +
    ' <Default Extension="config" ContentType="text/xml"/>\n</Types>\n';
  var ROOT_RELS = '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n' +
    ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n';
  var MODEL_RELS = '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n' +
    ' <Relationship Target="' + SUB + '" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n';

  // plate: { items: [{obj, x, y}] } from Model.packPlates. Returns {path: text} for one 3MF package.
  function plateFiles(plate, title) {
    uuidN = 0;
    var nextId = 1, partsXml = [], assemblies = [], settingsObjs = [], stats = { triangles: 0, parts: 0 };
    plate.items.forEach(function (it) {
      var partIds = [];
      it.obj.parts.forEach(function (pt) {
        var m = mergeShells(pt.shells), id = nextId++;
        partsXml.push('  <object id="' + id + '" p:UUID="' + uuid() + '" type="model">\n' + meshXml(m) + '\n  </object>');
        partIds.push({ id: id, name: pt.name, slot: pt.slot, faces: m.t.length / 3 });
        stats.triangles += m.t.length / 3; stats.parts++;
      });
      assemblies.push({ it: it, parts: partIds });
    });
    var subModel = '<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" xmlns="' + NS_CORE +
      '" xmlns:p="' + NS_PROD + '" requiredextensions="p">\n <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n' +
      partsXml.join('\n') + '\n </resources>\n <build/>\n</model>\n';

    var resObjs = [], items = [], plateInst = [];
    assemblies.forEach(function (a) {
      var aid = nextId++;
      var comps = a.parts.map(function (p) {
        return '    <component p:path="' + SUB + '" objectid="' + p.id + '" p:UUID="' + uuid() + '" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>';
      }).join('\n');
      resObjs.push('  <object id="' + aid + '" p:UUID="' + uuid() + '" type="model">\n   <components>\n' + comps + '\n   </components>\n  </object>');
      items.push('  <item objectid="' + aid + '" p:UUID="' + uuid() + '" transform="1 0 0 0 1 0 0 0 1 ' + f6(a.it.x) + ' ' + f6(a.it.y) + ' 0" printable="1"/>');
      var faces = a.parts.reduce(function (s, p) { return s + p.faces; }, 0);
      settingsObjs.push('  <object id="' + aid + '">\n    <metadata key="name" value="' + esc(a.it.obj.name) + '"/>\n' +
        '    <metadata key="extruder" value="' + a.parts[0].slot + '"/>\n    <metadata face_count="' + faces + '"/>\n' +
        a.parts.map(function (p) {
          return '    <part id="' + p.id + '" subtype="normal_part">\n      <metadata key="name" value="' + esc(p.name) + '"/>\n' +
            '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n      <metadata key="extruder" value="' + p.slot + '"/>\n' +
            '      <mesh_stat face_count="' + p.faces + '" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n    </part>';
        }).join('\n') + '\n  </object>');
      plateInst.push('    <model_instance>\n      <metadata key="object_id" value="' + aid + '"/>\n      <metadata key="instance_id" value="0"/>\n' +
        '      <metadata key="identify_id" value="' + (aid + 1000) + '"/>\n    </model_instance>');
    });
    var main = '<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" xmlns="' + NS_CORE +
      '" xmlns:BambuStudio="' + NS_BBS + '" xmlns:p="' + NS_PROD + '" requiredextensions="p">\n' +
      ' <metadata name="Application">Walker Designer</metadata>\n <metadata name="BambuStudio:3mfVersion">1</metadata>\n' +
      ' <metadata name="Title">' + esc(title) + '</metadata>\n <resources>\n' + resObjs.join('\n') + '\n </resources>\n' +
      ' <build p:UUID="' + uuid() + '">\n' + items.join('\n') + '\n </build>\n</model>\n';
    var settings = '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n' + settingsObjs.join('\n') + '\n  <plate>\n' +
      '    <metadata key="plater_id" value="1"/>\n    <metadata key="plater_name" value=""/>\n    <metadata key="locked" value="false"/>\n' +
      plateInst.join('\n') + '\n  </plate>\n</config>\n';
    var files = {
      '[Content_Types].xml': CONTENT_TYPES, '_rels/.rels': ROOT_RELS, '3D/3dmodel.model': main,
      '3D/_rels/3dmodel.model.rels': MODEL_RELS, '3D/Objects/object_1.model': subModel,
      'Metadata/model_settings.config': settings
    };
    files.__stats = stats;
    return files;
  }

  function readme(info) {
    return ['WALKER DESIGN - print files', '',
      'Open each plate_N.3mf in Bambu Studio (File > Open). Every part already knows which AMS slot (filament) it uses.',
      '',
      'Filament slots:'].concat(info.colors.map(function (c, i) { return '  Slot ' + (i + 1) + ': ' + c; })).concat([
      '', info.plates + ' plate(s), about ' + info.grams + ' g of plastic, about ' + info.hours + ' h of printing.',
      '', 'robot_settings.txt has the walking numbers for the robot code. walker_design.json holds every setting. Open the designer and use "Load design" to change it later.',
      'Not yet test-printed: print ONE leg first and check the servo fits (see design/kid-edition.md).']).join('\n') + '\n';
  }

  // Returns Promise<Uint8Array> of a zip: plate_1.3mf ..., walker_design.json, README.txt
  function buildZip(JSZip, Model, params, opts) {
    opts = opts || {};
    var d = Model.derive(params), parts = Model.buildParts(params, d), objs = Model.printObjects(params, d, parts);
    var plates = Model.packPlates(objs, params.bed), an = Model.analyze(params);
    var outer = new JSZip(), jobs = [];
    plates.forEach(function (pl, i) {
      var files = plateFiles(pl, 'Walker plate ' + (i + 1)), inner = new JSZip();
      Object.keys(files).forEach(function (k) { if (k !== '__stats') inner.file(k, files[k]); });
      jobs.push(inner.generateAsync({ type: 'uint8array', compression: 'DEFLATE' }).then(function (bytes) {
        outer.file('plate_' + (i + 1) + '.3mf', bytes);
      }));
    });
    return Promise.all(jobs).then(function () {
      outer.file('walker_design.json', JSON.stringify({ app: 'Walker Designer', version: 1, params: params }, null, 1));
      outer.file('robot_settings.txt', 'GAIT_STRIDE_DEG = ' + params.stride + '\nGAIT_LIFT_DEG = ' + params.lift + '\nGAIT_PERIOD_S = ' + params.period + '\nGAIT_SWAY_DEG = ' + params.sway + '\nGAIT_SPLAY_DEG = ' + params.legSplay + '\n');
      outer.file('README.txt', readme({ colors: params.ams.map(function (c) { return c.name; }), plates: plates.length,
        grams: Math.round(an.grams), hours: (an.grams * 2.2 / 60).toFixed(1) }));
      return outer.generateAsync({ type: 'uint8array', compression: 'DEFLATE' });
    });
  }

  return { plateFiles: plateFiles, buildZip: buildZip, mergeShells: mergeShells };
});
