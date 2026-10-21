// Walking maths for the walker robot. No hardware here.
// This is a line-by-line port of firmware/src/gait.py (checked by makecode-kid/tests/test_ts_parity.py).
// Legs are numbered 0 front-left, 1 front-right, 2 rear-left, 3 rear-right.
namespace walker {
    const SWING_FRAC = 0.20          // a leg is in the air for 20% of the cycle
    const SLOT_SPACING = 0.25        // legs start their swings a quarter cycle apart
    const SWAY_RAMP_IN = 0.08        // weight starts moving before a leg lifts
    const SWAY_RAMP_OUT = 0.05       // ...and eases back after it lands
    const SQRT_HALF = 0.7071067811865476
    const DEG2RAD = 0.017453292519943295
    const PI = 3.141592653589793

    const SWING_SLOT = [3, 1, 2, 0]  // swing order: rear-right, front-right, rear-left, front-left
    const SIDE = [0, 1, 0, 1]        // 0 = left side, 1 = right side
    const CORNER_X = [1, 1, -1, -1]  // x forward
    const CORNER_Y = [1, -1, 1, -1]  // y left
    const YAW_SIGN = [-1, 1, -1, 1]  // + hip = foot toward the front

    let stride = 20
    let lift = 25
    let period = 1.6
    let ramp = 2.0
    let sway = 14
    let splay = 50
    let cycle = 0
    let targetL = 0
    let targetR = 0
    let scaleL = 0
    let scaleR = 0
    let liftScale = 0
    let hipOut = [0, 0, 0, 0, 0, 0]
    let kneeOut = [0, 0, 0, 0, 0, 0]

    // ---- which robot: 0 crab (4 legs), 1 hexapod (6 legs), 2 windmill rover (4 spinning legs) ----
    // Hexapod legs: 0 FL, 1 FR, 2 RL, 3 RR, 4 ML, 5 MR (same order as firmware/src/gait.py HEX_LEGS).
    const HEX_SWING_FRAC = 0.45
    const HEX_SIDE = [0, 1, 0, 1, 0, 1]
    const HEX_GROUP = [0, 1, 0, 1, 1, 0]   // two tripods: FL+MR+RL step, then FR+ML+RR
    let style = 0
    let throttle = 0.4
    let rpmFull = 110
    let whegSpeed = [0, 0, 0, 0]
    let whegAngle = [0, 0, 0, 0]

    function mod1(x: number): number {
        return x - Math.floor(x)
    }
    function clamp1(x: number): number {
        return x < -1 ? -1 : x > 1 ? 1 : x
    }
    function approach(cur: number, target: number, step: number): number {
        if (cur < target) return Math.min(target, cur + step)
        return Math.max(target, cur - step)
    }
    function legPhase(c: number, leg: number): number {
        return mod1(c - SWING_SLOT[leg] * SLOT_SPACING)
    }
    function swayEnvelope(phase: number): number {
        if (phase < SWING_FRAC) return 1
        if (phase < SWING_FRAC + SWAY_RAMP_OUT)
            return 0.5 * (1 + Math.cos(PI * (phase - SWING_FRAC) / SWAY_RAMP_OUT))
        if (phase > 1 - SWAY_RAMP_IN)
            return 0.5 * (1 - Math.cos(PI * (phase - (1 - SWAY_RAMP_IN)) / SWAY_RAMP_IN))
        return 0
    }
    function heading(leg: number): number {
        if (leg == 0) return splay
        if (leg == 1) return -splay
        if (leg == 2) return 180 - splay
        return -(180 - splay)
    }
    function swayOffset(leg: number): number {
        let h = heading(leg) * DEG2RAD
        let tx = -YAW_SIGN[leg] * Math.sin(h)
        let ty = YAW_SIGN[leg] * Math.cos(h)
        let total = 0
        for (let k = 0; k < 4; k++) {
            if (k == leg) continue
            let dot = (tx * CORNER_X[k] + ty * CORNER_Y[k]) * SQRT_HALF
            total += sway * dot * swayEnvelope(legPhase(cycle, k))
        }
        return total
    }
    function isMoving(): boolean {
        return Math.abs(scaleL) > 0.001 || Math.abs(scaleR) > 0.001 || liftScale > 0.001
    }

    function hexPhase(c: number, leg: number): number {
        return mod1(c - 0.5 * HEX_GROUP[leg])
    }

    //% blockHidden=true
    export function _setStyle(s: number) {
        style = s
    }
    //% blockHidden=true
    export function _configureWheg(maxThrottle: number, rpm: number, rampPerS: number) {
        throttle = maxThrottle
        rpmFull = rpm
        ramp = rampPerS
    }
    //% blockHidden=true
    export function _whegSpeed(leg: number): number {
        return whegSpeed[leg]
    }
    //% blockHidden=true
    export function _whegAngle(leg: number): number {
        return whegAngle[leg]
    }
    // continuous-rotation servo pulse (microseconds): stop + trim + sign * speed * 500
    //% blockHidden=true
    export function _whegPulse(speed: number, sign: number, trimUs: number): number {
        return 1500 + trimUs + sign * clamp1(speed) * 500
    }

    //% blockHidden=true
    export function _configure(strideDeg: number, liftDeg: number, periodS: number, rampPerS: number, swayDeg: number, splayDeg: number) {
        stride = strideDeg
        lift = liftDeg
        period = periodS
        ramp = rampPerS
        sway = swayDeg
        splay = splayDeg
    }
    //% blockHidden=true
    export function _command(fwd: number, turn: number) {
        targetL = clamp1(fwd - turn)
        targetR = clamp1(fwd + turn)
    }
    //% blockHidden=true
    export function _reset() {
        cycle = 0
        targetL = 0
        targetR = 0
        scaleL = 0
        scaleR = 0
        liftScale = 0
        for (let i = 0; i < 4; i++) {
            whegSpeed[i] = 0
            whegAngle[i] = 0
        }
    }
    //% blockHidden=true
    export function _moving(): boolean {
        return isMoving()
    }
    //% blockHidden=true
    export function _update(dt: number) {
        let step = ramp * dt
        scaleL = approach(scaleL, targetL, step)
        scaleR = approach(scaleR, targetR, step)
        let want = (Math.abs(targetL) > 0.001 || Math.abs(targetR) > 0.001) ? 1 : 0
        if (style == 2) {
            for (let leg = 0; leg < 4; leg++) {
                whegSpeed[leg] = (SIDE[leg] == 0 ? scaleL : scaleR) * throttle
                whegAngle[leg] = mod1((whegAngle[leg] + whegSpeed[leg] * rpmFull * 6 * dt) / 360) * 360
            }
            return
        }
        liftScale = approach(liftScale, want, step)
        if (isMoving()) cycle = mod1(cycle + dt / period)
        if (style == 1) {
            for (let leg = 0; leg < 6; leg++) {
                let ph = hexPhase(cycle, leg)
                let hf = 0
                let lf = 0
                if (ph < HEX_SWING_FRAC) {
                    let u = ph / HEX_SWING_FRAC
                    hf = -Math.cos(PI * u)
                    lf = Math.sin(PI * u)
                } else {
                    hf = 1 - 2 * (ph - HEX_SWING_FRAC) / (1 - HEX_SWING_FRAC)
                }
                hipOut[leg] = stride * (HEX_SIDE[leg] == 0 ? scaleL : scaleR) * hf
                kneeOut[leg] = lift * liftScale * lf
            }
            return
        }
        for (let leg = 0; leg < 4; leg++) {
            let phase = legPhase(cycle, leg)
            let hipF = 0
            let liftF = 0
            if (phase < SWING_FRAC) {
                let s = phase / SWING_FRAC
                hipF = -Math.cos(PI * s)
                liftF = Math.sin(PI * s)
            } else {
                let s2 = (phase - SWING_FRAC) / (1 - SWING_FRAC)
                hipF = 1 - 2 * s2
            }
            let sc = SIDE[leg] == 0 ? scaleL : scaleR
            let hip = stride * sc * hipF
            if (sway != 0) hip += liftScale * swayOffset(leg)
            hipOut[leg] = hip
            kneeOut[leg] = lift * liftScale * liftF
        }
    }
    //% blockHidden=true
    export function _hip(leg: number): number {
        return hipOut[leg]
    }
    //% blockHidden=true
    export function _knee(leg: number): number {
        return kneeOut[leg]
    }
}
