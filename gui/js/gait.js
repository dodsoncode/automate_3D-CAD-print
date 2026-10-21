/* Creep (wave) gait for the 4-leg, 2-joint-per-leg walker.
 * Straight port of firmware/src/gait.py - keep the two in sync (gui/tests/test_gait_parity.py checks this).
 * Convention: hip + = foot toward FRONT, knee + = foot UP, 0 = neutral. Angles in degrees.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else { root.WD = root.WD || {}; root.WD.gait = factory(); }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  var LEGS = ['FL', 'FR', 'RL', 'RR'];
  var SIDE = { FL: 'L', RL: 'L', FR: 'R', RR: 'R' };
  var SWING_SLOT = { RR: 0, FR: 1, RL: 2, FL: 3 };
  var SWING_FRAC = 0.20;                                                  // leg in the air for 20% of the cycle
  var SLOT_SPACING = 0.25;                                                // swings start a quarter cycle apart
  // Weight shift ("sway"): a 4-legged walker with symmetric feet cannot stand on 3 legs unless its weight moves over
  // them. While leg k swings, the other legs nudge their hips so the body slides away from the lifted corner.
  var CORNER = { FL: [1, 1], FR: [1, -1], RL: [-1, 1], RR: [-1, -1] };   // x forward, y left
  var YAW_SIGN = { FL: -1, FR: 1, RL: -1, RR: 1 };                        // hip + = foot toward the front
  var SWAY_RAMP_IN = 0.08, SWAY_RAMP_OUT = 0.05;                          // ease in before lift / out after landing

  function mod1(x) { x = x % 1.0; return x < 0 ? x + 1.0 : x; }   // Python-style modulo for floats
  function legPhase(cycleT, leg) { return mod1(cycleT - SWING_SLOT[leg] * SLOT_SPACING); }

  function legProfile(phase) {
    if (phase < SWING_FRAC) {
      var s = phase / SWING_FRAC;
      return [-Math.cos(Math.PI * s), Math.sin(Math.PI * s)];
    }
    var s2 = (phase - SWING_FRAC) / (1.0 - SWING_FRAC);
    return [1.0 - 2.0 * s2, 0.0];
  }

  function heading(leg, splayDeg) {
    return { FL: splayDeg, FR: -splayDeg, RL: 180 - splayDeg, RR: -(180 - splayDeg) }[leg];
  }
  // direction the foot moves (in the body plane) for a + hip command
  function footTangent(leg, splayDeg) {
    var h = heading(leg, splayDeg) * Math.PI / 180;
    return [-YAW_SIGN[leg] * Math.sin(h), YAW_SIGN[leg] * Math.cos(h)];
  }
  function swayEnvelope(phase) {     // 0 -> 1 just before the swing, 1 during it, 1 -> 0 just after
    if (phase < SWING_FRAC) return 1.0;
    if (phase < SWING_FRAC + SWAY_RAMP_OUT) return 0.5 * (1 + Math.cos(Math.PI * (phase - SWING_FRAC) / SWAY_RAMP_OUT));
    if (phase > 1.0 - SWAY_RAMP_IN) return 0.5 * (1 - Math.cos(Math.PI * (phase - (1.0 - SWAY_RAMP_IN)) / SWAY_RAMP_IN));
    return 0.0;
  }
  function swayOffset(leg, cycle, swayDeg, splayDeg) {
    var total = 0.0, tg = footTangent(leg, splayDeg), n = Math.SQRT1_2;
    for (var i = 0; i < LEGS.length; i++) {
      var k = LEGS[i]; if (k === leg) continue;
      var dot = (tg[0] * CORNER[k][0] + tg[1] * CORNER[k][1]) * n;
      total += swayDeg * dot * swayEnvelope(legPhase(cycle, k));
    }
    return total;
  }

  function clamp(x, lo, hi) { lo = lo === undefined ? -1 : lo; hi = hi === undefined ? 1 : hi; return x < lo ? lo : x > hi ? hi : x; }
  function approach(cur, target, step) { return cur < target ? Math.min(target, cur + step) : Math.max(target, cur - step); }

  function Walker(strideDeg, liftDeg, periodS, rampPerS, swayDeg, splayDeg) {
    this.stride = strideDeg === undefined ? 20.0 : strideDeg;
    this.lift = liftDeg === undefined ? 25.0 : liftDeg;
    this.period = periodS === undefined ? 1.6 : periodS;
    this.ramp = rampPerS === undefined ? 2.0 : rampPerS;
    this.sway = swayDeg === undefined ? 0.0 : swayDeg;
    this.splay = splayDeg === undefined ? 50.0 : splayDeg;
    this.cycle = 0.0;
    this.target = { L: 0.0, R: 0.0 };
    this.scale = { L: 0.0, R: 0.0 };
    this.liftScale = 0.0;
  }
  Walker.prototype.command = function (fwd, turn) {
    fwd = fwd || 0; turn = turn || 0;
    this.target.L = clamp(fwd - turn);
    this.target.R = clamp(fwd + turn);
  };
  Walker.prototype.stop = function () { this.command(0, 0); };
  Walker.prototype.isMoving = function () {
    return Math.abs(this.scale.L) > 1e-3 || Math.abs(this.scale.R) > 1e-3 || this.liftScale > 1e-3;
  };
  Walker.prototype.update = function (dt) {
    var step = this.ramp * dt;
    this.scale.L = approach(this.scale.L, this.target.L, step);
    this.scale.R = approach(this.scale.R, this.target.R, step);
    var want = (Math.abs(this.target.L) > 1e-3 || Math.abs(this.target.R) > 1e-3) ? 1.0 : 0.0;
    this.liftScale = approach(this.liftScale, want, step);
    if (this.isMoving()) this.cycle = mod1(this.cycle + dt / this.period);
    return this.pose();
  };
  Walker.prototype.pose = function () {
    var out = {};
    for (var i = 0; i < LEGS.length; i++) {
      var leg = LEGS[i];
      var pf = legProfile(legPhase(this.cycle, leg));
      out[leg + '_hip'] = this.stride * this.scale[SIDE[leg]] * pf[0]
        + (this.sway ? this.liftScale * swayOffset(leg, this.cycle, this.sway, this.splay) : 0.0);
      out[leg + '_knee'] = this.lift * this.liftScale * pf[1];
    }
    return out;
  };

  function standPose(heightDeg) {
    heightDeg = heightDeg || 0;
    var out = {};
    for (var i = 0; i < LEGS.length; i++) { out[LEGS[i] + '_hip'] = 0.0; out[LEGS[i] + '_knee'] = -heightDeg; }
    return out;
  }

  return { LEGS: LEGS, SIDE: SIDE, SWING_SLOT: SWING_SLOT, SWING_FRAC: SWING_FRAC, SLOT_SPACING: SLOT_SPACING,
           legPhase: legPhase, legProfile: legProfile, swayOffset: swayOffset, footTangent: footTangent, Walker: Walker, standPose: standPose };
});
