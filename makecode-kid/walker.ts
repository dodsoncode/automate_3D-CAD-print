// Blocks for the walker robots: micro:bit + PCA9685 servo board. Three styles (see "start walker as"):
//   crab:    8 micro servos on channels 0..7 in this order: front-left hip, front-left knee, front-right hip,
//            front-right knee, rear-left hip, rear-left knee, rear-right hip, rear-right knee.
//   hexapod: the crab 8, plus middle-left hip 8, knee 9, middle-right hip 10, knee 11.
//   windmill rover: 4 continuous-rotation servos on channels 0..3: front-left, front-right, back-left, back-right.
// NOT tested yet in the MakeCode editor or on hardware. See makecode-kid/README.md.

enum Leg {
    //% block="front left"
    FrontLeft = 0,
    //% block="front right"
    FrontRight = 1,
    //% block="back left"
    BackLeft = 2,
    //% block="back right"
    BackRight = 3,
    //% block="middle left (hexapod)"
    MiddleLeft = 4,
    //% block="middle right (hexapod)"
    MiddleRight = 5
}

enum Style {
    //% block="crab (4 legs)"
    Crab = 0,
    //% block="hexapod (6 legs)"
    Hexapod = 1,
    //% block="windmill rover (4 spinning legs)"
    Windmill = 2
}

enum Joint {
    //% block="hip (swings forward and back)"
    Hip = 0,
    //% block="knee (lifts the foot)"
    Knee = 1
}

enum Move {
    //% block="forward"
    Forward = 0,
    //% block="backward"
    Backward = 1,
    //% block="turn left"
    TurnLeft = 2,
    //% block="turn right"
    TurnRight = 3
}

//% weight=100 color=#2a7de1 icon="" block="Walker"
//% groups=['Start', 'Walk', 'Legs', 'Settings', 'Fix a leg']
namespace walker {
    const HIP_LIMIT = 45
    const KNEE_MIN = -30
    const KNEE_MAX = 60
    // + hip moves the foot forward and + knee lifts the foot for every leg: mirrored servos need opposite signs
    let signs = [-1, 1, 1, -1, -1, 1, 1, -1, -1, 1, 1, -1]
    let offsets = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    // windmill rover: + = rolls the robot forward; the right side servos face the other way
    let wheelSigns = [1, -1, 1, -1]
    let wheelTrim = [0, 0, 0, 0]
    let style = 0
    let addr = 0x40
    let freq = 50.03
    let ready = false
    let loopStarted = false
    let relaxed = true
    let cfgStride = 20
    let cfgLift = 25
    let cfgPeriod = 1.6
    let cfgSway = 14
    let cfgThrottle = 0.4

    function write2(reg: number, val: number): number {
        let b = pins.createBuffer(2)
        b.setNumber(NumberFormat.UInt8LE, 0, reg)
        b.setNumber(NumberFormat.UInt8LE, 1, val)
        return pins.i2cWriteBuffer(addr, b)
    }

    function setTicks(channel: number, off: number) {
        let b = pins.createBuffer(5)
        b.setNumber(NumberFormat.UInt8LE, 0, 0x06 + 4 * channel)
        b.setNumber(NumberFormat.UInt8LE, 1, 0)
        b.setNumber(NumberFormat.UInt8LE, 2, 0)
        b.setNumber(NumberFormat.UInt8LE, 3, off & 0xff)
        b.setNumber(NumberFormat.UInt8LE, 4, (off >> 8) & 0x1f)
        pins.i2cWriteBuffer(addr, b)
    }

    // pulse in microseconds for an absolute servo angle 0..180
    export function pulseFor(absDeg: number): number {
        let a = Math.max(0, Math.min(180, absDeg))
        return 500 + a / 180 * 2000
    }

    //% blockHidden=true
    export function _ticksFor(us: number): number {
        return Math.max(0, Math.min(4095, Math.round(us * freq * 4096 / 1000000)))
    }

    //% blockHidden=true
    export function _absAngle(joint: number, rel: number): number {
        let lim = joint % 2 == 0 ? Math.max(-HIP_LIMIT, Math.min(HIP_LIMIT, rel)) : Math.max(KNEE_MIN, Math.min(KNEE_MAX, rel))
        return 90 + signs[joint] * lim + offsets[joint]
    }

    function setJoint(joint: number, rel: number) {
        if (!ready) return
        relaxed = false
        setTicks(joint, _ticksFor(pulseFor(_absAngle(joint, rel))))
    }

    function legCount(): number {
        return style == 1 ? 6 : 4
    }

    function setWheel(leg: number, speed: number) {
        if (!ready) return
        relaxed = false
        setTicks(leg, _ticksFor(walker._whegPulse(speed, wheelSigns[leg], wheelTrim[leg])))
    }

    function applyWalkPose() {
        if (style == 2) {
            for (let leg = 0; leg < 4; leg++) setWheel(leg, walker._whegSpeed(leg))
            return
        }
        for (let leg = 0; leg < legCount(); leg++) {
            setJoint(leg * 2, walker._hip(leg))
            setJoint(leg * 2 + 1, walker._knee(leg))
        }
    }

    // true when this leg does not exist on the chosen robot
    function noSuchLeg(leg: number): boolean {
        return style == 2 || leg >= legCount()
    }

    function backgroundLoop() {
        let last = control.millis()
        let wasMoving = false
        while (true) {
            let now = control.millis()
            let dt = Math.min(0.05, (now - last) / 1000)
            last = now
            if (walker._moving()) {
                walker._update(dt)
                applyWalkPose()
                wasMoving = true
            } else if (wasMoving) {
                walker._update(0)
                applyWalkPose()
                wasMoving = false
            }
            basic.pause(20)
        }
    }

    /**
     * Wake up the servo board and get the robot ready.
     * Shows a sad face if the board is not found: check the little cable and the power switch.
     */
    //% block="start walker"
    //% group="Start" weight=100
    export function start() {
        startAs(Style.Crab)
    }

    /**
     * Wake up the servo board for the robot you built: the crab, the hexapod or the windmill rover.
     */
    //% block="start walker as %robot"
    //% group="Start" weight=95
    export function startAs(robot: Style) {
        style = robot
        let found = false
        let tries = [0x40, 0x6c]
        for (let i = 0; i < tries.length; i++) {
            addr = tries[i]
            if (write2(0x00, 0x00) == 0) {
                found = true
                break
            }
        }
        if (!found) {
            basic.showIcon(IconNames.Sad)
            return
        }
        write2(0x01, 0x04)          // outputs: totem pole
        write2(0x00, 0x10)          // sleep so the speed can be changed
        write2(0xfe, 121)           // 50 Hz servo pulses
        write2(0x00, 0x00)          // wake up
        control.waitMicros(1000)
        write2(0x00, 0xa0)          // restart with auto-increment
        ready = true
        walker._reset()
        cfgStride = 20
        cfgLift = 25
        cfgPeriod = style == 1 ? 1.4 : 1.6
        cfgSway = 14
        cfgThrottle = 0.4
        pushSettings()
        if (!loopStarted) {
            loopStarted = true
            control.inBackground(backgroundLoop)
        }
        stand()
    }

    /**
     * Stand still with every joint in the middle.
     */
    //% block="stand"
    //% group="Start" weight=90
    export function stand() {
        walker._reset()
        if (style == 2) {
            for (let leg = 0; leg < 4; leg++) setWheel(leg, 0)
            return
        }
        for (let j = 0; j < legCount() * 2; j++) setJoint(j, 0)
    }

    /**
     * Start walking. The robot keeps going until you use "stop walking".
     */
    //% block="walk %move"
    //% group="Walk" weight=80
    export function walk(move: Move) {
        if (!ready) return
        if (move == Move.Forward) walker._command(1, 0)
        else if (move == Move.Backward) walker._command(-1, 0)
        else if (move == Move.TurnLeft) walker._command(0, 1)
        else walker._command(0, -1)
    }

    /**
     * Walk for some seconds, then stop.
     */
    //% block="walk %move for %seconds seconds"
    //% seconds.defl=5 seconds.min=0 seconds.max=60
    //% group="Walk" weight=70
    export function walkFor(move: Move, seconds: number) {
        walk(move)
        basic.pause(seconds * 1000)
        stopWalking()
    }

    /**
     * Slow down and stand still.
     */
    //% block="stop walking"
    //% group="Walk" weight=60
    export function stopWalking() {
        walker._command(0, 0)
        while (walker._moving()) basic.pause(20)
    }

    /**
     * Move one joint to an angle. 0 is the middle.
     * For a hip, a positive angle swings the foot forward. For a knee, a positive angle lifts the foot.
     */
    //% block="set %leg %joint to %degrees degrees"
    //% degrees.min=-45 degrees.max=60 degrees.defl=0
    //% group="Legs" weight=50
    export function setLeg(leg: Leg, joint: Joint, degrees: number) {
        if (noSuchLeg(leg)) return
        if (walker._moving()) stopWalking()
        setJoint(leg * 2 + joint, degrees)
    }

    /**
     * Let the motors go limp so you can move the legs by hand.
     */
    //% block="relax motors"
    //% group="Legs" weight=40
    export function relax() {
        walker._reset()
        for (let j = 0; j < 12; j++) setTicks(j, 4096)
        relaxed = true
    }

    /**
     * How far each foot swings (degrees) while walking.
     */
    //% block="step size %stepDeg degrees"
    //% stepDeg.min=5 stepDeg.max=30 stepDeg.defl=20
    //% group="Settings" weight=30
    export function setStepSize(stepDeg: number) {
        cfgStride = stepDeg
        pushSettings()
    }

    /**
     * How high each foot lifts (degrees of knee).
     */
    //% block="foot lift %liftDeg degrees"
    //% liftDeg.min=10 liftDeg.max=35 liftDeg.defl=25
    //% group="Settings" weight=29
    export function setFootLift(liftDeg: number) {
        cfgLift = liftDeg
        pushSettings()
    }

    /**
     * Seconds for the legs to go through all four steps once. Smaller is faster.
     */
    //% block="seconds for 4 steps %seconds"
    //% seconds.min=0.8 seconds.max=3 seconds.defl=1.6
    //% group="Settings" weight=28
    export function setSpeed(seconds: number) {
        cfgPeriod = seconds
        pushSettings()
    }

    /**
     * How much the robot leans over its standing legs (degrees). More lean means fewer tumbles.
     */
    //% block="lean over standing legs %leanDeg degrees"
    //% leanDeg.min=0 leanDeg.max=15 leanDeg.defl=14
    //% group="Settings" weight=27
    export function setLean(leanDeg: number) {
        cfgSway = leanDeg
        pushSettings()
    }

    /**
     * Windmill rover only: how fast the spinning legs go, in percent of their top speed. Start low.
     */
    //% block="top speed %percent percent"
    //% percent.min=10 percent.max=100 percent.defl=40
    //% group="Settings" weight=26
    export function setTopSpeed(percent: number) {
        cfgThrottle = Math.max(0.1, Math.min(1, percent / 100))
        pushSettings()
    }

    function pushSettings() {
        walker._setStyle(style)
        walker._configure(cfgStride, cfgLift, cfgPeriod, 2.0, cfgSway, 50)
        walker._configureWheg(cfgThrottle, 110, 2.0)
    }

    /**
     * Fix a leg that stands crooked: nudge one joint a few degrees.
     */
    //% block="nudge %leg %joint by %degrees degrees"
    //% degrees.min=-20 degrees.max=20 degrees.defl=0
    //% group="Fix a leg" weight=20
    export function nudge(leg: Leg, joint: Joint, degrees: number) {
        if (noSuchLeg(leg)) return
        offsets[leg * 2 + joint] = degrees
        setJoint(leg * 2 + joint, 0)
    }

    /**
     * If a joint moves the wrong way, flip it.
     */
    //% block="flip direction of %leg %joint"
    //% group="Fix a leg" weight=10
    export function flip(leg: Leg, joint: Joint) {
        if (noSuchLeg(leg)) return
        signs[leg * 2 + joint] = -signs[leg * 2 + joint]
        setJoint(leg * 2 + joint, 0)
    }

    /**
     * Wiggle one joint so you can see which motor it is.
     */
    //% block="wiggle %leg %joint"
    //% group="Fix a leg" weight=5
    export function wiggle(leg: Leg, joint: Joint) {
        if (noSuchLeg(leg)) return
        for (let i = 0; i < 2; i++) {
            setLeg(leg, joint, 15)
            basic.pause(300)
            setLeg(leg, joint, -15)
            basic.pause(300)
        }
        setLeg(leg, joint, 0)
    }

    /**
     * Windmill rover: make a wheel stand perfectly still. Nudge the stop point a little (microseconds) until it stops creeping.
     */
    //% block="stop-fix %leg wheel by %micros"
    //% micros.min=-60 micros.max=60 micros.defl=0
    //% group="Fix a wheel" weight=4
    export function fixWheelStop(leg: Leg, micros: number) {
        if (style != 2 || leg > 3) return
        wheelTrim[leg] = micros
        setWheel(leg, 0)
    }

    /**
     * Windmill rover: if a wheel turns the wrong way when the robot drives forward, flip it.
     */
    //% block="flip spin direction of %leg wheel"
    //% group="Fix a wheel" weight=3
    export function flipWheel(leg: Leg) {
        if (style != 2 || leg > 3) return
        wheelSigns[leg] = -wheelSigns[leg]
        setWheel(leg, 0)
    }

    /**
     * Windmill rover: spin one wheel forward for a second so you can see which one it is.
     */
    //% block="test spin %leg wheel"
    //% group="Fix a wheel" weight=2
    export function testWheel(leg: Leg) {
        if (style != 2 || leg > 3) return
        if (walker._moving()) stopWalking()
        setWheel(leg, 0.3)
        basic.pause(1000)
        setWheel(leg, 0)
    }
}
