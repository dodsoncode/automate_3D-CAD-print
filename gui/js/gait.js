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
  var SWING_FRAC = 0.25;

  function mod1(x) { x = x % 1.0; return x < 0 ? x + 1.0 : x; }   // Python-style modulo for floats
  function legPhase(cycleT, leg) { return mod1(cycleT - SWING_SLOT[leg] * SWING_FRAC); }

  function legProfile(phase) {
    if (phase < SWING_FRAC) {
      var s = phase / SWING_FRAC;
      return [-Math.cos(Math.PI * s), Math.sin(Math.PI * s)];
    }
    var s2 = (phase - SWING_FRAC) / (1.0 - SWING_FRAC);
    return [1.0 - 2.0 * s2, 0.0];
  }

  function clamp(x, lo, hi) { lo = lo === undefined ? -1 : lo; hi = hi === undefined ? 1 : hi; return x < lo ? lo : x > hi ? hi : x; }
  function approach(cur, target, step) { return cur < target ? Math.min(target, cur + step) : Math.max(target, cur - step); }

  function Walker(strideDeg, liftDeg, periodS, rampPerS) {
    this.stride = strideDeg === undefined ? 20.0 : strideDeg;
    this.lift = liftDeg === undefined ? 25.0 : liftDeg;
    this.period = periodS === undefined ? 1.6 : periodS;
    this.ramp = rampPerS === undefined ? 2.0 : rampPerS;
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
      out[leg + '_hip'] = this.stride * this.scale[SIDE[leg]] * pf[0];
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

  return { LEGS: LEGS, SIDE: SIDE, SWING_SLOT: SWING_SLOT, SWING_FRAC: SWING_FRAC,
           legPhase: legPhase, legProfile: legProfile, Walker: Walker, standPose: standPose };
});
