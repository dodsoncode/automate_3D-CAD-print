/* Walker design model: parameters -> layout -> printable parts -> physical checks.
 *
 * Frames (all mm):
 *   body frame : x forward, y left, z up. z = 0 is the underside of the body plate.
 *   leg frame  : origin on the hip axis at plate underside height (z=0), u = outward along the leg's heading,
 *                v = left of that, w = up (same as z). Every leg uses the SAME printed parts.
 * Parts are built in the leg/body frame; PRINT_ROT turns them onto their best printing face.
 *
 * Unverified assumption: the servo dimension defaults are typical MG90S values (measure yours!) and
 * nothing here has been test-printed yet.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./geom.js'), require('./gait.js'), require('./wheg.js'));
  else { root.WD = root.WD || {}; root.WD.model = factory(root.WD.geom, root.WD.gait, root.WD.wheg); }
})(typeof self !== 'undefined' ? self : this, function (G, Gait, WhegMod) {
  'use strict';
  var DEG = Math.PI / 180;
  var LEGS = Gait.LEGS;
  var HIP_SIGN = { FL: 1, FR: -1, RL: 1, RR: -1 };          // body corner signs: x = sx*hx, y = sy*hy
  var HIP_SY = { FL: 1, FR: -1, RL: 1, RR: -1, ML: 1, MR: -1 };
  var HIP_SX = { FL: 1, FR: 1, RL: -1, RR: -1, ML: 0, MR: 0 };     // hexapod middle legs sit at x = 0
  var YAW_SIGN = { FL: -1, FR: 1, RL: -1, RR: 1, ML: -1, MR: 1 };  // + hip command = foot toward the FRONT
  var STYLES = ['crab', 'hex', 'wheg'];
  function legsOf(p) { return p.style === 'hex' ? Gait.HEX_LEGS : Gait.LEGS; }
  var DENS = 6.8e-4;                      // g per mm3 of printed volume (PLA 1.24 g/cm3 with walls + ~25% infill)

  var BATTERY_PRESETS = {
    '4xAA': { label: '4 x AA holder (flat, with cover)', L: 62, W: 58, H: 17, mass: 135 },
    '4xAAA': { label: '4 x AAA holder (flat)', L: 56, W: 47, H: 13, mass: 62 },
    '3xAA': { label: '3 x AA holder (flat, with cover)', L: 63, W: 48, H: 17, mass: 105 },
    'custom': { label: 'Something else (type sizes below)', L: 62, W: 58, H: 17, mass: 135 }
  };

  var RANGES = {
    extraLength: [0, 40, 1], extraWidth: [0, 40, 1], cornerRadius: [2, 24, 1],
    coxaLen: [30, 60, 1], femurLen: [35, 95, 1], stanceAngle: [30, 75, 1], legWidth: [9, 16, 0.5],
    legThick: [2.6, 5, 0.2], legSplay: [30, 80, 1], footSize: [14, 32, 1], tipDrop: [8, 16, 1],
    stride: [8, 30, 1], lift: [10, 35, 1], period: [0.8, 3, 0.1], sway: [0, 15, 1],
    spokeLen: [30, 75, 1], spokeCount: [2, 6, 1], padSize: [8, 22, 1], padWidth: [5, 16, 1], maxThrottle: [0.2, 1, 0.05]
  };

  function defaults() {
    return {
      version: 2, name: 'My Walker', style: 'crab',
      extraLength: 0, extraWidth: 0, cornerRadius: 3, floorT: 3.5,
      coxaLen: 34, femurLen: 55, stanceAngle: 45, legWidth: 10, legThick: 3.2, legSplay: 50,
      footSize: 20, tipDrop: 8, footH: 9,
      stride: 20, lift: 25, period: 1.6, sway: 14,
      ams: [{ name: 'Sky blue', hex: '#3aa7ff' }, { name: 'Orange', hex: '#ff8a1f' },
            { name: 'Lime', hex: '#7ed321' }, { name: 'Pink', hex: '#ff5fa2' }],
      slots: { body: 1, trim: 2, FL: 2, FR: 3, RL: 4, RR: 1, ML: 3, MR: 2, feet: 0 },   // feet 0 = same color as the leg
      servo: { L: 22.8, W: 12.2, H: 22.5, tabSpan: 32.2, tabThick: 2.5, tabFromTop: 4.0, shaftOff: 5.9,
               holeSpan: 27.8, shaftH: 5.0, mass: 13.4, torque: 2.0, hornThick: 2.0, hornGap: 0.8,
               hornHoles: [5, 11], hub: 7.0, pilot: 1.6 },
      board: { L: 68, W: 46.5, H: 10.6, mass: 22 },
      microbit: { L: 52, W: 42, H: 4, mass: 8 },
      batteryPreset: '4xAA', battery: { L: 62, W: 58, H: 17, mass: 135 },
      spokeLen: 48, spokeCount: 3, padSize: 12, padWidth: 8, maxThrottle: 0.4,
      wheelServo: { torque: 1.3, mass: 10.6, rpm: 110 },
      clearance: 0.3, bed: 256
    };
  }

  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function clampParams(p) {
    if (STYLES.indexOf(p.style) < 0) p.style = 'crab';
    Object.keys(RANGES).forEach(function (k) {
      var r = RANGES[k]; if (typeof p[k] !== 'number' || isNaN(p[k])) p[k] = defaults()[k];
      p[k] = Math.min(r[1], Math.max(r[0], p[k]));
    });
    return p;
  }

  var PRESETS = {
    'Starter walker': {},
    'Tiny crab': { coxaLen: 30, femurLen: 40, stanceAngle: 40, legSplay: 70, footSize: 18, extraLength: 0, extraWidth: 0, stride: 18 },
    'Stilt walker': { coxaLen: 38, femurLen: 80, stanceAngle: 60, legSplay: 45, footSize: 24, legWidth: 12, legThick: 3.8, stride: 16 },
    'Wide stomper': { coxaLen: 46, femurLen: 55, stanceAngle: 35, legSplay: 60, footSize: 28, extraLength: 20, extraWidth: 14, cornerRadius: 20 }
  };

  // ------------------------------------------------------------------ layout
  function deriveLegged(p) {
    var s = p.servo, c = p.clearance, d = {};
    d.t = p.legThick;
    d.eL = p.board.L + 2 * c; d.eW = p.board.W + 2 * c;
    d.bL = p.battery.L + 2 * c; d.bW = p.battery.W + 2 * c;
    d.divider = 4; d.innerW = d.eW + d.bW + d.divider;
    d.yE = d.innerW / 2 - d.eW / 2; d.yB = -(d.innerW / 2 - d.bW / 2);
    d.bayX = Math.max(d.eL, d.bL);
    d.cutL = s.L + 2 * c; d.cutW = s.W + 2 * c;                  // servo window: cutL long, cutW short
    d.hipGapX = 11;                                             // room for rubber-band lugs
    d.hx = d.bayX / 2 + d.hipGapX + d.cutW / 2 + p.extraLength / 2;
    d.tabReach = s.shaftOff + (s.tabSpan - s.L) / 2;            // hip axis to outer tab tip
    d.halfLy = d.innerW / 2 + 4 + p.extraWidth / 2;
    d.hy = d.halfLy - d.tabReach - 3;
    d.halfLx = d.hx + d.cutW / 2 + 4;
    d.bodyCy = d.hy - (s.L / 2 - s.shaftOff);                    // |y| of the hip servo body centre
    d.legs = legsOf(p);
    if (p.style === 'hex') {                                    // middle motors sit beside the bays, so the body is wider
      d.bodyCy = d.innerW / 2 + 2 + d.cutL / 2 + p.extraWidth / 2;
      d.hy = d.bodyCy + (s.L / 2 - s.shaftOff);
      d.halfLy = d.hy + d.tabReach + 3;
    }
    d.win = {};
    d.legs.forEach(function (l) { d.win[l] = [HIP_SX[l] * d.hx, HIP_SY[l] * d.bodyCy]; });
    // roundest corner (up to the requested one) that still keeps every motor tab 2 mm inside the edge
    var req = Math.min(p.cornerRadius, d.halfLx - 1, d.halfLy - 1), r = req;
    function tabsInside(rad) {
      var o = G.rrect(0, 0, 2 * d.halfLx, 2 * d.halfLy, rad, 8), ok = true;
      d.legs.forEach(function (l) { [-1, 1].forEach(function (a) { [-1, 1].forEach(function (b) {
        var pt = [d.win[l][0] + a * (d.cutW / 2 + 1.5), d.win[l][1] + b * (s.tabSpan / 2 + 0.5)];
        if (!G.pointInPoly(pt, o) || G.distToPolyEdge(pt, o) < 2.0) ok = false;
      }); }); });
      return ok;
    }
    while (r > 0.5 && !tabsInside(r)) r -= 0.5;
    d.cornerR = r; d.cornerLimited = r < req - 1.0; d.cornerWanted = req;
    d.outline = G.rrect(0, 0, 2 * d.halfLx, 2 * d.halfLy, d.cornerR, 8);

    // vertical stack at the hip (servo hangs shaft-down through the plate, tabs rest on top)
    d.floorT = p.floorT;
    d.hipFace = d.floorT - s.tabFromTop;                        // underside face of the servo gear housing
    d.hornTop = d.hipFace - s.hornGap; d.hornBot = d.hornTop - s.hornThick;
    d.flTop = d.hornBot; d.flBot = d.flTop - d.t;               // coxa flange
    d.Kw = d.flBot - 0.6 - d.cutW / 2;                          // knee axis height
    d.a = p.coxaLen; d.uc = d.a - (s.L / 2 - s.shaftOff);       // knee servo body centre (u)
    d.cw = 16; d.vp0 = d.cw / 2;                                // coxa width; vertical plate starts at v = vp0
    d.plateU0 = d.uc - (s.holeSpan / 2 + 4); d.plateU1 = d.uc + (s.holeSpan / 2 + 4);
    d.wPlateTop = d.flBot + 1.0; d.wPlateBot = d.Kw - d.cutW / 2 - 3;
    d.vF0 = d.vp0 + s.tabFromTop + s.hornGap + s.hornThick;     // femur inboard face
    d.vF1 = d.vF0 + d.t; d.vFc = (d.vF0 + d.vF1) / 2;
    d.recess = Math.min(1.6, d.t - 1.2);

    // femur: knee -> bend -> tip
    d.phi = p.stanceAngle;
    d.Qu = d.a + p.femurLen * Math.cos(d.phi * DEG); d.Qw = d.Kw - p.femurLen * Math.sin(d.phi * DEG);
    d.Tw = d.Qw - p.tipDrop;
    d.footBase = 2.0; d.pegIn = p.footH - d.footBase;
    d.footBot = d.Tw - d.footBase; d.footTop = d.Tw + d.pegIn;
    d.standH = -d.footBot;                                       // underside of body above the ground
    d.pocketU = p.legWidth + 2 * c; d.pocketV = d.t + 2 * c;
    d.minFoot = Math.hypot(d.pocketU, d.pocketV) + 4;

    // hip positions / headings
    d.hip = {}; d.heading = {};
    var sp = p.legSplay;
    d.heading.FL = sp; d.heading.FR = -sp; d.heading.RL = 180 - sp; d.heading.RR = -(180 - sp);
    d.heading.ML = 90; d.heading.MR = -90;
    d.legs.forEach(function (l) { d.hip[l] = [HIP_SX[l] * d.hx, HIP_SY[l] * d.hy]; });
    return d;
  }

  // ------------------------------------------------------------------ parts (shells)
  function buildBody(p, d) {
    var s = p.servo, holes = [], k;
    holes.push(G.rrect(0, d.yE, d.eL - 14, d.eW - 14, 3, 4));                       // window under the board
    d.legs.forEach(function (l) {
      var w = d.win[l];
      holes.push(G.rect(w[0], w[1], d.cutW, d.cutL));
      for (k = -1; k <= 1; k += 2) holes.push(G.circle(w[0], w[1] + k * s.holeSpan / 2, s.pilot / 2, 14));
    });
    return G.extrude(d.outline, holes, 0, d.floorT);
  }

  function buildTrim(p, d) {
    var shells = [], z0 = d.floorT, T = 2.2, LEN = 12, sx, sy;
    function corner(cx, cy, h) {                  // L-shaped corner post just outside the bay corner
      var sxx = cx > 0 ? 1 : -1, syy = cy > 0 ? 1 : -1;
      shells.push(G.extrude(G.rect(cx + sxx * T / 2, cy - syy * (LEN - T) / 2, T, LEN + T), [], z0, z0 + h));
      shells.push(G.extrude(G.rect(cx - sxx * (LEN - T) / 2, cy + syy * T / 2, LEN + T, T), [], z0, z0 + h));
    }
    var hE = 8, hB = Math.min(10, Math.max(6, p.battery.H * 0.6));
    for (sx = -1; sx <= 1; sx += 2) for (sy = -1; sy <= 1; sy += 2) {
      corner(sx * d.eL / 2, d.yE + sy * d.eW / 2, hE);
      corner(sx * d.bL / 2, d.yB + sy * d.bW / 2, hB);
    }
    for (sx = -1; sx <= 1; sx += 2) [[d.eL, d.yE], [d.bL, d.yB]].forEach(function (bay) {     // rubber-band lugs
      var x = sx * (bay[0] / 2 + T + 2.8);
      shells.push(G.extrude(G.circle(x, bay[1], 2, 20), [], z0, z0 + 7));
      shells.push(G.extrude(G.circle(x, bay[1], 3.4, 24), [], z0 + 5, z0 + 7));
    });
    return shells;
  }

  function buildCoxa(p, d) {
    var s = p.servo, t = d.t, u0 = -d.cw / 2, u1 = d.plateU1, v0 = -d.cw / 2, v1 = d.vp0 + t, holes = [];
    holes.push(G.circle(0, 0, s.hub / 2, 28));
    s.hornHoles.forEach(function (h) { holes.push(G.circle(h, 0, s.pilot / 2, 14)); });
    var flange = G.extrudeUV(G.rrect((u0 + u1) / 2, (v0 + v1) / 2, u1 - u0, v1 - v0, 3, 5), holes, d.flBot, d.flTop);
    var ph = [G.rect(d.uc, d.Kw, d.cutL, d.cutW)];
    [-1, 1].forEach(function (k) { ph.push(G.circle(d.uc + k * s.holeSpan / 2, d.Kw, s.pilot / 2, 14)); });
    var plate = G.extrudeUW(G.rect((d.plateU0 + d.plateU1) / 2, (d.wPlateBot + d.wPlateTop) / 2,
                                   d.plateU1 - d.plateU0, d.wPlateTop - d.wPlateBot), ph, d.vp0, d.vp0 + t);
    return [flange, plate];
  }

  function femurOutline(p, d) {
    return G.stroke([[d.a, d.Kw], [d.Qu, d.Qw], [d.Qu, d.Tw]], p.legWidth);
  }
  function buildFemur(p, d) {
    var s = p.servo, outline = femurOutline(p, d), dir = [Math.cos(d.phi * DEG), -Math.sin(d.phi * DEG)], holes = [];
    s.hornHoles.forEach(function (h) { holes.push(G.circle(d.a + dir[0] * h, d.Kw + dir[1] * h, s.pilot / 2, 14)); });
    var inner = G.extrudeUW(outline, holes.concat([G.circle(d.a, d.Kw, s.hub / 2, 28)]), d.vF0, d.vF0 + d.recess);
    var outer = G.extrudeUW(outline, holes, d.vF0 + d.recess - 0.1, d.vF1);
    return [inner, outer];
  }

  function buildFoot(p, d) {
    var r = Math.max(p.footSize, d.minFoot) / 2;       // too-small feet are flagged red by the check; keep the preview valid
    var base = G.extrude(G.circle(0, 0, r, 48), [], 0, d.footBase);
    var top = G.extrude(G.circle(0, 0, r, 48), [G.rect(0, 0, d.pocketU, d.pocketV)], d.footBase - 0.2, p.footH);
    return [base, top];
  }

  // print orientation: rotation matrix applied to leg-frame shells (all have det = +1)
  var PRINT_ROT = {
    body: G.I3,
    coxa: [1, 0, 0, 0, -1, 0, 0, 0, -1],          // flip so the flange lies on the bed, plate rises
    femur: [1, 0, 0, 0, 0, 1, 0, -1, 0],          // (u,v,w) -> (u, w, -v): outer face down, recess faces up
    foot: G.I3
  };

  function buildPartsLegged(p, d) {
    return {
      body: [{ name: 'plate', slotKey: 'body', shells: [buildBody(p, d)] },
             { name: 'trim', slotKey: 'trim', shells: buildTrim(p, d) }],
      coxa: [{ name: 'coxa', slotKey: 'leg', shells: buildCoxa(p, d) }],
      femur: [{ name: 'femur', slotKey: 'leg', shells: buildFemur(p, d) }],
      foot: [{ name: 'foot', slotKey: 'foot', shells: buildFoot(p, d) }]
    };
  }

  // The list of things to print: one Body + (coxa, femur, foot) per leg, each in print orientation, min corner at 0.
  function printObjectsLegged(p, d, parts) {
    parts = parts || buildPartsLegged(p, d);
    var out = [];
    function make(kind, name, leg) {
      var rot = PRINT_ROT[kind], list = parts[kind].map(function (pt) {
        var slot = pt.slotKey === 'body' ? p.slots.body : pt.slotKey === 'trim' ? p.slots.trim
                 : pt.slotKey === 'leg' ? p.slots[leg] : (p.slots.feet || p.slots[leg]);
        return { name: pt.name, slot: slot, shells: G.transformAll(pt.shells, rot) };
      });
      var all = []; list.forEach(function (pt) { all = all.concat(pt.shells); });
      var bb = G.bbox(all), sh = [-bb.min[0], -bb.min[1], -bb.min[2]];
      list.forEach(function (pt) { pt.shells = G.transformAll(pt.shells, G.I3, sh); });
      var vol = 0; list.forEach(function (pt) { pt.shells.forEach(function (s) { vol += G.volume(s); }); });
      out.push({ name: name, kind: kind, leg: leg || null, parts: list,
                 size: [bb.max[0] - bb.min[0], bb.max[1] - bb.min[1], bb.max[2] - bb.min[2]], volume: vol });
    }
    make('body', 'Body');
    d.legs.forEach(function (l) {
      make('coxa', 'Upper leg ' + l, l); make('femur', 'Lower leg ' + l, l); make('foot', 'Foot ' + l, l);
    });
    return out;
  }

  // ------------------------------------------------------------------ hardware ghosts (preview only)
  function hardwareLegged(p, d) {
    var s = p.servo, fz = d.floorT, body = [], leg = [], knee = [];
    body.push({ name: 'board', color: '#1f8a4c', size: [p.board.L, p.board.W, p.board.H], center: [0, d.yE, fz + p.board.H / 2] });
    body.push({ name: 'microbit', color: '#222a33', size: [p.microbit.L, p.microbit.W, p.microbit.H],
                center: [0, d.yE, fz + p.board.H + p.microbit.H / 2] });
    body.push({ name: 'battery', color: '#6b7280', size: [p.battery.L, p.battery.W, p.battery.H], center: [0, d.yB, fz + p.battery.H / 2] });
    d.legs.forEach(function (l) {
      body.push({ name: 'hipservo', color: '#2b6cb0', size: [s.W, s.L, s.H], center: [d.win[l][0], d.win[l][1], d.hipFace + s.H / 2] });
      body.push({ name: 'hiptab', color: '#2b6cb0', size: [s.W, s.tabSpan, s.tabThick], center: [d.win[l][0], d.win[l][1], fz + s.tabThick / 2] });
    });
    leg.push({ name: 'hiphorn', color: '#e5e7eb', size: [19, 5.5, s.hornThick], center: [5.5, 0, (d.hornTop + d.hornBot) / 2] });
    leg.push({ name: 'kneeservo', color: '#2b6cb0', size: [s.L, s.H, s.W], center: [d.uc, d.vp0 + s.tabFromTop - s.H / 2, d.Kw] });
    leg.push({ name: 'kneetab', color: '#2b6cb0', size: [s.tabSpan, s.tabThick, s.W], center: [d.uc, d.vp0 - s.tabThick / 2, d.Kw] });
    knee.push({ name: 'kneehorn', color: '#e5e7eb', size: [19, s.hornThick, 5.5],
                center: [5.5, d.vp0 + s.tabFromTop + s.hornGap + s.hornThick / 2, 0], rotY: d.phi });   // relative to the knee axis
    return { body: body, leg: leg, knee: knee };
  }

  // ------------------------------------------------------------------ kinematics, mass, stability
  function legFK(p, d, leg, hipDeg, liftDeg, pt) {
    // pt: [u, v, w] in the leg frame BEFORE the knee rotation (default: foot contact point)
    pt = pt || [d.Qu, d.vFc, d.footBot];
    var lift = liftDeg * DEG, du = pt[0] - d.a, dw = pt[2] - d.Kw;
    var u = d.a + du * Math.cos(lift) - dw * Math.sin(lift), w = d.Kw + du * Math.sin(lift) + dw * Math.cos(lift), v = pt[1];
    var yaw = (d.heading[leg] + YAW_SIGN[leg] * hipDeg) * DEG, h = d.hip[leg];
    return [h[0] + u * Math.cos(yaw) - v * Math.sin(yaw), h[1] + u * Math.sin(yaw) + v * Math.cos(yaw), w];
  }

  function masses(p, d, objs) {
    var m = { body: 0, coxa: 0, femur: 0, foot: 0 };
    objs.forEach(function (o) { m[o.kind] += o.volume * DENS; });
    // per-leg average
    var nl = d.legs.length, legMass = { fixed: (m.coxa / nl) + p.servo.mass, swing: (m.femur / nl) + (m.foot / nl) + 2 };
    var bodyParts = [
      [m.body, 0, 0, d.floorT / 2], [p.board.mass, 0, d.yE, d.floorT + 5], [p.microbit.mass, 0, d.yE, d.floorT + p.board.H + 2],
      [p.battery.mass, 0, d.yB, d.floorT + p.battery.H / 2]
    ];
    d.legs.forEach(function (l) { bodyParts.push([p.servo.mass, d.win[l][0], d.win[l][1], d.floorT + 8]); });
    var bm = 0, bx = 0, by = 0, bz = 0;
    bodyParts.forEach(function (b) { bm += b[0]; bx += b[0] * b[1]; by += b[0] * b[2]; bz += b[0] * b[3]; });
    return { printed: m, leg: legMass, bodyMass: bm, bodyCom: [bx / bm, by / bm, bz / bm],
             total: bm + nl * (legMass.fixed + legMass.swing) };
  }

  function comAt(p, d, mass, pose) {
    var M = mass.bodyMass, x = mass.bodyCom[0] * M, y = mass.bodyCom[1] * M, z = mass.bodyCom[2] * M;
    d.legs.forEach(function (l) {
      var hip = pose[l + '_hip'], lift = pose[l + '_knee'];
      var f = legFK(p, d, l, hip, 0, [d.uc, d.vp0 - 6, d.Kw]);                 // coxa + knee servo
      x += mass.leg.fixed * f[0]; y += mass.leg.fixed * f[1]; z += mass.leg.fixed * f[2]; M += mass.leg.fixed;
      var mid = [d.a + (d.Qu - d.a) / 2, d.vFc, d.Kw + (d.Qw - d.Kw) / 2];
      var g = legFK(p, d, l, hip, lift, mid);                                  // femur + foot
      x += mass.leg.swing * g[0]; y += mass.leg.swing * g[1]; z += mass.leg.swing * g[2]; M += mass.leg.swing;
    });
    return [x / M, y / M, z / M];
  }

  function hull(pts) {
    pts = pts.slice().sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    if (pts.length < 3) return pts;
    function cross(o, a, b) { return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]); }
    var lo = [], up = [], i;
    for (i = 0; i < pts.length; i++) { while (lo.length >= 2 && cross(lo[lo.length - 2], lo[lo.length - 1], pts[i]) <= 0) lo.pop(); lo.push(pts[i]); }
    for (i = pts.length - 1; i >= 0; i--) { while (up.length >= 2 && cross(up[up.length - 2], up[up.length - 1], pts[i]) <= 0) up.pop(); up.push(pts[i]); }
    lo.pop(); up.pop(); return lo.concat(up);
  }
  function insideMargin(poly, c) {              // CCW polygon: smallest signed distance from c to an edge (>0 = inside)
    var m = Infinity;
    for (var i = 0; i < poly.length; i++) {
      var a = poly[i], b = poly[(i + 1) % poly.length], ex = b[0] - a[0], ey = b[1] - a[1], L = Math.hypot(ex, ey);
      m = Math.min(m, (ex * (c[1] - a[1]) - ey * (c[0] - a[0])) / L);
    }
    return m;
  }

  function walkCycle(p, steps) {
    var W = p.style === 'hex' ? new Gait.HexWalker(p.stride, p.lift, p.period, 2.0) : new Gait.Walker(p.stride, p.lift, p.period, 2.0, p.sway, p.legSplay);
    W.command(1, 0);
    W.scale = { L: 1, R: 1 }; W.liftScale = 1; var out = [];
    for (var k = 0; k < steps; k++) { W.cycle = k / steps; out.push(W.pose()); }
    return out;
  }

  function stability(p, d, mass) {
    var worst = Infinity, worstK = 0, minGap = Infinity, steps = 48, poses = walkCycle(p, steps);
    var neutral = p.style === 'hex' ? Gait.hexStandPose(0) : Gait.standPose(0), k, nLegs = d.legs.length;
    poses.concat([neutral]).forEach(function (pose, idx) {
      var feet = [], stance = [];
      d.legs.forEach(function (l) {
        var f = legFK(p, d, l, pose[l + '_hip'], pose[l + '_knee']); feet.push(f);
        if (pose[l + '_knee'] <= 1.0) stance.push([f[0], f[1]]);
      });
      var com = comAt(p, d, mass, pose), margin = -60;
      if (stance.length >= 3) margin = insideMargin(hull(stance), com);
      if (margin < worst) { worst = margin; worstK = idx; }
      for (var i = 0; i < nLegs; i++) for (var j = i + 1; j < nLegs; j++) {          // clearance between feet (centre distance)
        var gap = Math.hypot(feet[i][0] - feet[j][0], feet[i][1] - feet[j][1]) - p.footSize;
        if (gap < minGap) minGap = gap;
      }
    });
    return { margin: worst, atPhase: worstK / steps, minFootGap: minGap };
  }

  // ------------------------------------------------------------------ checks (kid-readable)
  function mk(id, level, title, detail) { return { id: id, level: level, title: title, detail: detail }; }

  function analyzeLegged(p, objs) {
    var d = deriveLegged(p), checks = [];
    objs = objs || printObjectsLegged(p, d);
    var mass = masses(p, d, objs), st = stability(p, d, mass), s = p.servo;

    // hip windows inside the body outline (the corner radius was already limited in derive())
    var worstEdge = Infinity;
    d.legs.forEach(function (l) {
      [-1, 1].forEach(function (a) { [-1, 1].forEach(function (b) {
        var pt = [d.win[l][0] + a * (d.cutW / 2 + 1.5), d.win[l][1] + b * (s.tabSpan / 2 + 0.5)];
        var inside = G.pointInPoly(pt, d.outline);
        worstEdge = Math.min(worstEdge, inside ? G.distToPolyEdge(pt, d.outline) : -G.distToPolyEdge(pt, d.outline));
      }); });
    });
    if (worstEdge < 1.5) checks.push(mk('corners', 'bad', 'Motors do not fit in the body', 'A leg motor would hang off the edge. Make the body bigger.'));
    else if (d.cornerLimited) checks.push(mk('corners', 'warn', 'Corners made less round',
      'You asked for ' + d.cornerWanted.toFixed(0) + ' mm rounding. ' + d.cornerR.toFixed(1) + ' mm is the most that still holds the motors. Make the body bigger for rounder corners.'));
    else checks.push(mk('corners', 'ok', 'Motors fit in the body', 'The corners are strong enough to hold the leg motors.'));

    checks.push(d.floorT <= s.tabFromTop - 0.3 ? mk('floor', 'ok', 'Body plate thickness OK', 'Motor tabs sit flat on the plate.')
      : mk('floor', 'bad', 'Body plate too thick', 'Plate must be thinner than ' + (s.tabFromTop - 0.3).toFixed(1) + ' mm so the motor can poke through.'));

    var mg = st.margin;
    var lifting = p.style === 'hex' ? 'three legs lift' : 'a leg lifts';
    checks.push(mg >= 12 ? mk('stable', 'ok', 'Steady walker', 'Safe even when ' + lifting + ' (' + mg.toFixed(0) + ' mm to spare).')
      : mg >= 3 ? mk('stable', 'warn', 'A bit wobbly', 'Only ' + mg.toFixed(0) + ' mm to spare when ' + lifting + '. Try longer sideways legs or a smaller lift.')
      : mk('stable', 'bad', 'Might tip over', 'The robot\'s weight falls outside its feet when ' + lifting + '. Spread the legs out or lower the lift.'));

    var hipMax = p.stride + (p.style === 'hex' ? 0 : p.sway);
    checks.push(hipMax <= 40 ? mk('hiprange', 'ok', 'Hips swing a safe amount', 'Biggest hip swing ' + hipMax.toFixed(0) + '° (limit 45°).')
      : mk('hiprange', hipMax <= 45 ? 'warn' : 'bad', 'Hips swing a lot', 'Stride + weight shift = ' + hipMax.toFixed(0) + '°. Keep it under 45° or the motors hit their stops.'));

    // knee torque
    var arm = Math.abs(d.Qu - d.a) / 10;                                   // cm, horizontal from knee axis to foot
    var need = (mass.total / 3) * 1.3 * arm / 1000;                        // kg*cm (mass in g)
    var have = s.torque * 0.5;                                             // use half the rated torque
    var ratio = have / need;
    checks.push(ratio >= 1.5 ? mk('muscle', 'ok', 'Leg motors are strong enough', 'Needs about ' + need.toFixed(2) + ' kg-cm of ' + have.toFixed(1) + ' available.')
      : ratio >= 1 ? mk('muscle', 'warn', 'Leg motors are working hard', 'Close to the limit. A shorter lower leg or a lighter battery helps.')
      : mk('muscle', 'bad', 'Motors too weak', 'The motors may not lift the robot. Shorten the lower leg or use a lighter battery.'));

    // thin legs: bending stress in the lower leg
    var F = mass.total / 1000 * 9.81 / 3 * 1.3, M = F * Math.abs(d.Qu - d.a), Z = p.legThick * p.legWidth * p.legWidth / 6;
    var sigma = M / Z;
    checks.push(sigma < 6 ? mk('thin', 'ok', 'Legs are sturdy', 'Bending stress ' + sigma.toFixed(1) + ' MPa (printed plastic breaks near 30+).')
      : sigma < 12 ? mk('thin', 'warn', 'Legs are a bit thin', 'Thicker or wider legs would be safer (' + sigma.toFixed(1) + ' MPa).')
      : mk('thin', 'bad', 'Legs may snap', 'Make the lower leg thicker, wider or shorter (' + sigma.toFixed(1) + ' MPa).'));

    checks.push(st.minFootGap >= 8 ? mk('feet', 'ok', 'Feet never bump', 'At least ' + st.minFootGap.toFixed(0) + ' mm between feet while walking.')
      : mk('feet', st.minFootGap >= 0 ? 'warn' : 'bad', st.minFootGap >= 0 ? 'Feet get close' : 'Feet would crash',
           'Closest feet come within ' + st.minFootGap.toFixed(0) + ' mm. Turn the legs outward or use smaller feet.'));

    checks.push(p.footSize >= d.minFoot ? mk('foot', 'ok', 'Foot is big enough', 'Has room for the leg plug.')
      : mk('foot', 'bad', 'Foot too small', 'Make the foot at least ' + Math.ceil(d.minFoot) + ' mm wide so the leg can plug in.'));

    // printing
    var plates = packPlates(objs, p.bed), grams = 0;
    objs.forEach(function (o) { grams += o.volume * DENS; });
    var tooBig = objs.some(function (o) { return o.size[0] > p.bed - 10 || o.size[1] > p.bed - 10; });
    checks.push(tooBig ? mk('bed', 'bad', 'A part is too big for the printer', 'The body must fit on a ' + p.bed + ' mm bed. Shrink the body.')
      : mk('bed', 'ok', 'Prints on ' + plates.length + ' plate' + (plates.length > 1 ? 's' : ''),
           'About ' + grams.toFixed(0) + ' g of plastic, roughly ' + (grams * 2.2 / 60).toFixed(1) + ' hours.'));

    var tall = d.standH;
    checks.push(tall <= 95 ? mk('height', 'ok', 'Standing height ' + tall.toFixed(0) + ' mm', 'Body underside is this far off the floor.')
      : mk('height', 'warn', 'Very tall robot', tall.toFixed(0) + ' mm off the floor. It will be easier to tip.'));

    var worst = checks.some(function (c) { return c.level === 'bad'; }) ? 'bad' : checks.some(function (c) { return c.level === 'warn'; }) ? 'warn' : 'ok';
    return { derived: d, mass: mass, stability: st, checks: checks, worst: worst, plates: plates, grams: grams,
             torque: { need: need, have: have }, stress: sigma };
  }

  // ------------------------------------------------------------------ plate packing (shelf)
  function packPlates(objs, bed) {
    var margin = 8, gap = 6, plates = [], order = objs.slice().sort(function (a, b) { return b.size[1] - a.size[1]; });
    function newPlate() { var pl = { items: [], x: margin, y: margin, rowH: 0 }; plates.push(pl); return pl; }
    var pl = newPlate();
    order.forEach(function (o) {
      var w = o.size[0], h = o.size[1];
      if (pl.x + w > bed - margin) { pl.x = margin; pl.y += pl.rowH + gap; pl.rowH = 0; }
      if (pl.y + h > bed - margin) { pl = newPlate(); }
      pl.items.push({ obj: o, x: pl.x, y: pl.y }); pl.x += w + gap; pl.rowH = Math.max(pl.rowH, h);
    });
    return plates;
  }

  // ------------------------------------------------------------------ style dispatch (crab | hex | wheg)
  function slotFor(p, key, leg) {
    return key === 'body' ? p.slots.body : key === 'trim' ? p.slots.trim : key === 'leg' ? p.slots[leg] : (p.slots.feet || p.slots[leg]);
  }
  var Wheg = WhegMod.make({ mk: mk, packPlates: packPlates, buildTrim: buildTrim, slotFor: slotFor, DENS: DENS });
  function isWheg(p) { return p.style === 'wheg'; }
  function derive(p) { return isWheg(p) ? Wheg.derive(p) : deriveLegged(p); }
  function buildParts(p, d) { return isWheg(p) ? Wheg.buildParts(p, d) : buildPartsLegged(p, d); }
  function printObjects(p, d, parts) { return isWheg(p) ? Wheg.printObjects(p, d, parts) : printObjectsLegged(p, d, parts); }
  function hardware(p, d) { return isWheg(p) ? Wheg.hardware(p, d) : hardwareLegged(p, d); }
  function analyze(p, objs) { return isWheg(p) ? Wheg.analyze(p, objs) : analyzeLegged(p, objs); }

  var STYLE_INFO = {
    crab: { name: 'Crab walker', blurb: '4 legs, 8 motors. Creeps along one leg at a time and leans over the other three.', legs: Gait.LEGS, motors: 8 },
    hex: { name: 'Hexapod', blurb: '6 legs, 12 motors. Three legs walk while three stand, so it is very steady.', legs: Gait.HEX_LEGS, motors: 12 },
    wheg: { name: 'Windmill rover', blurb: '4 spinning spoked legs, 4 spin motors. Rolls fast and climbs over rough ground.', legs: Gait.LEGS, motors: 4 }
  };
  var STYLE_PRESETS = {
    crab: PRESETS,
    hex: {
      'Starter hexapod': {},
      'Tall hexapod': { coxaLen: 38, femurLen: 75, stanceAngle: 60, footSize: 22, legWidth: 12, legThick: 3.8 },
      'Tiny hexapod': { coxaLen: 30, femurLen: 40, stanceAngle: 40, legSplay: 60, footSize: 18, stride: 16 }
    },
    wheg: {
      'Starter rover': {},
      'Rock crawler': { spokeLen: 58, spokeCount: 3, padSize: 14, padWidth: 10, extraLength: 16, extraWidth: 6, maxThrottle: 0.3, legWidth: 10 },
      'Speedster': { spokeLen: 40, spokeCount: 4, padSize: 12, padWidth: 8, maxThrottle: 0.6 },
      'Windmill': { spokeLen: 50, spokeCount: 4, padSize: 12, padWidth: 8, maxThrottle: 0.35 }
    }
  };
  function styleDefaults(style) {
    var p = defaults(); p.style = style;
    if (style === 'hex') p.femurLen = 45;                      // 12 motors and a heavier body: shorter lower legs keep the knees comfortable
    if (style === 'wheg') { p.batteryPreset = '4xAAA'; p.battery = { L: BATTERY_PRESETS['4xAAA'].L, W: BATTERY_PRESETS['4xAAA'].W, H: BATTERY_PRESETS['4xAAA'].H, mass: BATTERY_PRESETS['4xAAA'].mass }; }
    return p;
  }

  return {
    LEGS: LEGS, HIP_SX: HIP_SX, HIP_SY: HIP_SY, YAW_SIGN: YAW_SIGN, RANGES: RANGES, PRESETS: PRESETS, STYLES: STYLES, STYLE_INFO: STYLE_INFO,
    STYLE_PRESETS: STYLE_PRESETS, styleDefaults: styleDefaults, legsOf: legsOf,
    BATTERY_PRESETS: BATTERY_PRESETS, PRINT_ROT: PRINT_ROT, DENS: DENS,
    defaults: defaults, clone: clone, clampParams: clampParams, derive: derive,
    buildParts: buildParts, printObjects: printObjects, hardware: hardware, femurOutline: femurOutline,
    legFK: legFK, analyze: analyze, packPlates: packPlates, walkCycle: walkCycle
  };
});
