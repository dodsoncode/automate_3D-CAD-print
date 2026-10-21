/* Wheg rover ("windmill legs"): 4 spoked legs that spin on continuous-rotation servos.
 *
 * Body frame: x forward, y left, z up, z = 0 is the underside of the body floor.
 * The servos sit in two vertical side walls with their tabs on the INSIDE face and the shaft pointing outward.
 * Wheel frame (while building): the wheel lies in the X/Y plane and Z is |y| in the body, so the same shells can be
 * placed on either side with a +-90 degree turn about x. Nothing printed here has been test-printed yet.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./geom.js'));
  else { root.WD = root.WD || {}; root.WD.wheg = factory(root.WD.geom); }
})(typeof self !== 'undefined' ? self : this, function (G) {
  'use strict';
  var DEG = Math.PI / 180;
  var LEGS = ['FL', 'FR', 'RL', 'RR'];
  var SX = { FL: 1, FR: 1, RL: -1, RR: -1 }, SY = { FL: 1, FR: -1, RL: 1, RR: -1 };

  // H: helpers shared with model.js { mk, packPlates, buildTrim, slotFor, DENS }
  function make(H) {
    function derive(p) {
      var s = p.servo, c = p.clearance, d = {};
      d.legs = LEGS; d.t = p.legThick;
      d.eL = p.board.L + 2 * c; d.eW = p.board.W + 2 * c;
      d.bL = p.battery.L + 2 * c; d.bW = p.battery.W + 2 * c;
      d.divider = 4; d.innerW = d.eW + d.bW + d.divider;
      d.yE = d.innerW / 2 - d.eW / 2; d.yB = -(d.innerW / 2 - d.bW / 2);
      d.bayX = Math.max(d.eL, d.bL);
      d.cutL = s.L + 2 * c; d.cutW = s.W + 2 * c;
      d.floorT = p.floorT; d.wallT = 3.0;
      d.hx = d.bayX / 2 + 4 + d.cutL / 2 + p.extraLength / 2;                 // servo body centre (x)
      d.axleX = d.hx + (s.L / 2 - s.shaftOff);                                 // shaft sits toward the outside
      d.halfLx = d.hx + s.tabSpan / 2 + 2;
      d.wallIn = d.innerW / 2 + p.extraWidth / 2; d.wallOut = d.wallIn + d.wallT;
      d.halfLy = d.wallOut;
      d.zc = d.floorT + 1.5 + d.cutW / 2;                                      // servo / axle height above the underside
      d.wallTop = d.zc + d.cutW / 2 + 5;
      d.axleZ = d.zc;
      d.outline = G.rect(0, 0, 2 * d.halfLx, 2 * d.halfLy);
      // wheel
      d.R = p.spokeLen; d.padD = p.padSize; d.padW = p.padWidth;
      d.hubR = 15; d.padCenterR = d.R - d.padD / 2;
      d.hubY0 = d.wallOut + (s.tabFromTop - d.wallT) + s.hornGap + s.hornThick;   // inner face of the hub, as |y|
      d.hubY1 = d.hubY0 + d.t; d.padY1 = d.hubY0 + Math.max(d.padW, d.t);
      d.trackHalf = d.hubY0 + (d.padY1 - d.hubY0) / 2;                          // |y| of the ground contact
      d.n = Math.round(p.spokeCount);
      d.standH = d.R - d.axleZ;                                                 // underside height with a spoke straight down
      d.minClear = d.R * Math.cos(Math.PI / d.n) - d.axleZ;                     // lowest it ever gets (two spokes down)
      d.axleSpacing = 2 * d.axleX;
      d.pitch = 360 / d.n;
      return d;
    }

    function buildBody(p, d) {
      var s = p.servo, floorHoles = [G.rrect(0, d.yE, d.eL - 14, d.eW - 14, 3, 4)];
      var floor = G.extrude(G.rect(0, 0, 2 * d.halfLx, 2 * d.halfLy), floorHoles, 0, d.floorT);
      var shells = [floor];
      [-1, 1].forEach(function (sy) {
        var holes = [];
        [-1, 1].forEach(function (sx) {
          holes.push(G.rect(sx * d.hx, d.zc, d.cutL, d.cutW));
          [-1, 1].forEach(function (k) { holes.push(G.circle(sx * d.hx + k * s.holeSpan / 2, d.zc, s.pilot / 2, 14)); });
        });
        var wall = G.extrudeUW(G.rect(0, d.wallTop / 2, 2 * d.halfLx, d.wallTop), holes,
                               sy > 0 ? d.wallIn : -d.wallOut, sy > 0 ? d.wallOut : -d.wallIn);
        shells.push(wall);
      });
      return shells;
    }

    function buildWheel(p, d) {
      var s = p.servo, holes = [G.circle(0, 0, s.hub / 2, 28)], spokes = [], i;
      s.hornHoles.forEach(function (h) { holes.push(G.circle(h, 0, s.pilot / 2, 14)); });
      var hub = G.extrude(G.circle(0, 0, d.hubR, 48), holes, d.hubY0, d.hubY1);
      var r0 = d.hubR - 2.0, r1 = d.padCenterR;
      for (i = 0; i < d.n; i++) {
        var a = i * d.pitch * DEG, ca = Math.cos(a), sa = Math.sin(a);
        spokes.push(G.extrude(G.stroke([[r0 * ca, r0 * sa], [r1 * ca, r1 * sa]], p.legWidth), [], d.hubY0, d.hubY1));
      }
      var pads = [];
      for (i = 0; i < d.n; i++) {
        var b = i * d.pitch * DEG;
        pads.push(G.extrude(G.circle(d.padCenterR * Math.cos(b), d.padCenterR * Math.sin(b), d.padD / 2, 28), [], d.hubY0, d.padY1));
      }
      return { wheel: [hub].concat(spokes), pads: pads };
    }

    function buildParts(p, d) {
      var w = buildWheel(p, d);
      return {
        body: [{ name: 'body', slotKey: 'body', shells: buildBody(p, d) },
               { name: 'trim', slotKey: 'trim', shells: H.buildTrim(p, d) }],
        wheg: [{ name: 'hub and spokes', slotKey: 'leg', shells: w.wheel },
               { name: 'tip pads', slotKey: 'foot', shells: w.pads }]
      };
    }

    function printObjects(p, d, parts) {
      parts = parts || buildParts(p, d);
      var out = [];
      function one(kind, name, leg) {
        var list = parts[kind].map(function (pt) { return { name: pt.name, slot: H.slotFor(p, pt.slotKey, leg), shells: pt.shells.slice() }; });
        var all = []; list.forEach(function (pt) { all = all.concat(pt.shells); });
        var bb = G.bbox(all), sh = [-bb.min[0], -bb.min[1], -bb.min[2]];
        list.forEach(function (pt) { pt.shells = G.transformAll(pt.shells, G.I3, sh); });
        var vol = 0; list.forEach(function (pt) { pt.shells.forEach(function (s) { vol += G.volume(s); }); });
        out.push({ name: name, kind: kind, leg: leg || null, parts: list,
                   size: [bb.max[0] - bb.min[0], bb.max[1] - bb.min[1], bb.max[2] - bb.min[2]], volume: vol });
      }
      one('body', 'Body');
      LEGS.forEach(function (l) { one('wheg', 'Windmill leg ' + l, l); });
      return out;
    }

    function hardware(p, d) {
      var s = p.servo, fz = d.floorT, body = [], sx, sy;
      body.push({ name: 'board', color: '#1f8a4c', size: [p.board.L, p.board.W, p.board.H], center: [0, d.yE, fz + p.board.H / 2] });
      body.push({ name: 'microbit', color: '#222a33', size: [p.microbit.L, p.microbit.W, p.microbit.H], center: [0, d.yE, fz + p.board.H + p.microbit.H / 2] });
      body.push({ name: 'battery', color: '#6b7280', size: [p.battery.L, p.battery.W, p.battery.H], center: [0, d.yB, fz + p.battery.H / 2] });
      for (sx = -1; sx <= 1; sx += 2) for (sy = -1; sy <= 1; sy += 2) {
        var yc = sy * (d.wallIn + s.tabFromTop - s.H / 2);
        body.push({ name: 'spinservo', color: '#2b6cb0', size: [s.L, s.H, s.W], center: [sx * d.hx, yc, d.zc] });
        body.push({ name: 'spintab', color: '#2b6cb0', size: [s.tabSpan, s.tabThick, s.W], center: [sx * d.hx, sy * (d.wallIn + s.tabThick / 2), d.zc] });
      }
      return { body: body, leg: [], knee: [] };
    }

    function masses(p, d, objs) {
      var m = { body: 0, wheg: 0 };
      objs.forEach(function (o) { m[o.kind] += o.volume * H.DENS; });
      var wm = p.wheelServo.mass, parts = [[m.body, 0, 0, d.floorT], [p.board.mass, 0, d.yE, d.floorT + 5],
        [p.microbit.mass, 0, d.yE, d.floorT + p.board.H + 2], [p.battery.mass, 0, d.yB, d.floorT + p.battery.H / 2]];
      LEGS.forEach(function (l) {
        parts.push([wm, SX[l] * d.hx, SY[l] * (d.wallIn + 8), d.zc]);
        parts.push([m.wheg / 4, SX[l] * d.axleX, SY[l] * (d.hubY0 + 2), d.zc]);
      });
      var tm = 0, x = 0, y = 0, z = 0;
      parts.forEach(function (q) { tm += q[0]; x += q[0] * q[1]; y += q[0] * q[2]; z += q[0] * q[3]; });
      return { printed: m, total: tm, com: [x / tm, y / tm, z / tm], wheelMass: m.wheg / 4 };
    }

    function analyze(p, objs) {
      var d = derive(p), checks = [], s = p.servo, mk = H.mk;
      objs = objs || printObjects(p, d);
      var mass = masses(p, d, objs), W = p.wheelServo;

      checks.push(d.wallT <= s.tabFromTop - 0.3 ? mk('floor', 'ok', 'Walls are the right thickness', 'The motor top pokes through the wall so the horn can turn.')
        : mk('floor', 'bad', 'Wall too thick', 'Walls must be thinner than ' + (s.tabFromTop - 0.3).toFixed(1) + ' mm.'));

      var gap = d.axleSpacing - (2 * d.R + 4);
      checks.push(gap >= 0 ? mk('wheelgap', 'ok', 'Windmill legs never touch', 'Front and back legs clear each other by at least ' + gap.toFixed(0) + ' mm.')
        : mk('wheelgap', 'bad', 'Windmill legs would hit each other', 'The spokes are ' + (-gap).toFixed(0) + ' mm too long for the body. Make the body longer or the spokes shorter.'));

      var mc = d.minClear;
      checks.push(mc >= 10 ? mk('height', 'ok', 'Belly clears the ground', 'At least ' + mc.toFixed(0) + ' mm under the body even when two spokes touch down.')
        : mc >= 3 ? mk('height', 'warn', 'Belly is low', 'Only ' + mc.toFixed(0) + ' mm under the body at the lowest. Longer spokes or more spokes help.')
        : mk('height', 'bad', 'Body would drag', 'The body drags when two spokes touch down. Use longer or more spokes.'));

      var comH = d.standH + mass.com[2], track = d.trackHalf;
      var tip = Math.atan2(track, comH) / DEG;
      checks.push(tip >= 30 ? mk('stable', 'ok', 'Hard to tip over', 'It tips only when leaned past ' + tip.toFixed(0) + ' degrees sideways.')
        : tip >= 20 ? mk('stable', 'warn', 'Tips on slopes', 'Leans over at about ' + tip.toFixed(0) + ' degrees sideways. Wider body, lower battery or shorter spokes help.')
        : mk('stable', 'bad', 'Might tip over', 'Tips at only ' + tip.toFixed(0) + ' degrees sideways. Make the body wider or the spokes shorter.'));

      var arm = 0.7 * d.R / 10;                                              // cm: horizontal reach when a spoke pushes over a step
      var need = (mass.total / 1000 / 2) * 1.3 * arm, have = W.torque * 0.6;
      var ratio = have / need;
      checks.push(ratio >= 1.5 ? mk('muscle', 'ok', 'Motors are strong enough', 'Needs about ' + need.toFixed(2) + ' kg-cm to climb a step, has ' + have.toFixed(2) + '.')
        : ratio >= 1 ? mk('muscle', 'warn', 'Motors work hard on steps', 'Close to the limit (' + need.toFixed(2) + ' of ' + have.toFixed(2) + ' kg-cm). Shorter spokes or a lighter battery help.')
        : mk('muscle', 'bad', 'Motors too weak to climb', 'Needs ' + need.toFixed(2) + ' kg-cm but has ' + have.toFixed(2) + '. Use shorter spokes or a lighter battery pack.'));

      var F = mass.total / 1000 * 9.81 / 2 * 1.5, Mb = F * (d.padCenterR), Z = p.legThick * p.legWidth * p.legWidth / 6, sigma = Mb / Z;
      checks.push(sigma < 6 ? mk('thin', 'ok', 'Spokes are sturdy', 'Bending stress ' + sigma.toFixed(1) + ' MPa (printed plastic breaks near 30+).')
        : sigma < 12 ? mk('thin', 'warn', 'Spokes are a bit thin', 'Wider or thicker spokes are safer (' + sigma.toFixed(1) + ' MPa).')
        : mk('thin', 'bad', 'Spokes may snap', 'Make the spokes thicker, wider or shorter (' + sigma.toFixed(1) + ' MPa).'));

      checks.push(d.padD >= p.legWidth + 2 ? mk('foot', 'ok', 'Tip pads are big enough', 'The pad covers the end of the spoke.')
        : mk('foot', 'bad', 'Tip pad too small', 'Make the pad at least ' + Math.ceil(p.legWidth + 2) + ' mm across.'));

      var speed = W.rpm * p.maxThrottle / 60 * 2 * Math.PI * (0.8 * d.R / 10);   // cm/s, rolling on 0.8 R
      checks.push(speed <= 25 ? mk('speed', 'ok', 'About ' + speed.toFixed(0) + ' cm per second', 'Top speed at your throttle setting. Going slower is easier to control.')
        : mk('speed', 'warn', 'Quite fast: ' + speed.toFixed(0) + ' cm per second', 'Fast robots flip over bumps. Lower the throttle first.'));

      var plates = H.packPlates(objs, p.bed), grams = 0;
      objs.forEach(function (o) { grams += o.volume * H.DENS; });
      var tooBig = objs.some(function (o) { return o.size[0] > p.bed - 10 || o.size[1] > p.bed - 10; });
      checks.push(tooBig ? mk('bed', 'bad', 'A part is too big for the printer', 'The body must fit on a ' + p.bed + ' mm bed. Shrink the body.')
        : mk('bed', 'ok', 'Prints on ' + plates.length + ' plate' + (plates.length > 1 ? 's' : ''),
             'About ' + grams.toFixed(0) + ' g of plastic, roughly ' + (grams * 2.2 / 60).toFixed(1) + ' hours.'));

      var worst = checks.some(function (c) { return c.level === 'bad'; }) ? 'bad' : checks.some(function (c) { return c.level === 'warn'; }) ? 'warn' : 'ok';
      return { derived: d, mass: mass, stability: { margin: tip, atPhase: 0, minFootGap: gap }, checks: checks, worst: worst, plates: plates, grams: grams,
               torque: { need: need, have: have }, stress: sigma, speedCmS: speed };
    }

    return { derive: derive, buildParts: buildParts, printObjects: printObjects, hardware: hardware, analyze: analyze, LEGS: LEGS, SX: SX, SY: SY };
  }

  return { make: make, LEGS: LEGS, SX: SX, SY: SY };
});
