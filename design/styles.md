# Locomotion styles

The kid edition now has three body styles. All share the micro:bit V2 + Kitronik Compact 16 Servo Driver, the AA NiMH pack, the printed body bays and the color-coded parts idea. The Walker Designer picks the style first.

| | **Crab** (original) | **Hexapod** | **Wheg rover** (windmill legs) |
|---|---|---|---|
| Idea | 4 legs, creep gait, leans onto 3 feet | 6 legs, tripod gait (3 feet always down) | 4 spoked "windmill" legs that spin continuously |
| Motors | 8 x MG90S (position) | 12 x MG90S (position) | 4 x FS90R (continuous rotation) |
| Servo board channels | 0-7 | 0-11 | 0-3 |
| Steering | left/right sweep scale | left/right sweep scale | left/right wheg speed (spin on the spot) |
| Rough ground | low steps (foot lift 25 deg) | low steps, very stable on slopes | best: spokes climb steps about as tall as the spoke radius x 0.7 |
| Speed | slow (about 3 cm/s) | medium | fast (10+ cm/s at 50% throttle) |
| Complexity to program | medium | medium | easiest (4 speeds) |
| Weak point | needs weight shift, 8 fragile joints | more parts and wiring, wider body | motors are open loop: wheg phases drift, so spokes can touch; needs wide axle spacing |
| Added cost vs crab | none | 4 servos | swap 8 servos for 4 FS90R |

## Windmill legs ("whegs")
A wheg is a hub with 3 straight spokes 120 degrees apart. Each tip carries a wide pad. The body rides on the hub axle, so it rolls like a wheel on flat ground and the spokes grab and lift over obstacles like a leg. Real whegs (the Case Western robots) phase-lock front and rear whegs. With cheap continuous servos there is no position feedback, so phases drift. The design therefore keeps the axle spacing at least 2 x spoke radius + pad so spokes can never hit each other.
- Spoke radius sets climbing height (about 0.7 x radius) and ground clearance. Torque needed also grows with radius, so a long spoke on a heavy robot is a warning in the designer.
- The motor sits in a vertical wall of the body with its tabs on the inside face and the shaft pointing outward (same trick as the crab knee).
- Parts: body (floor + two walls), 4 identical whegs (hub + 3 spokes, leg color) with pad tips in the foot color.

## Hexapod
Legs FL, FR, RL, RR as the crab (same channels 0-7) plus ML (8-9) and MR (10-11), so a crab can be upgraded in place. Tripod gait: front-left + middle-right + rear-left swing together, then the other three. The center of mass always lies inside the 3-foot triangle, so no weight shift is needed. The body is wider because the middle motors sit beside the battery and board bays.

## Verified hardware facts (web only, not on a bench)
- FS90R: 4.8-6 V, torque 1.3 kg-cm at 4.8 V and 1.5 at 6 V, no-load about 110 rpm at 4.8 V, 22.5 x 12 x 22.7 mm class body, 10 g, stop at 1500 us, full speed about 1000 / 2000 us, dead band about 90 us, has a trim screw to find its true stop. Sources: [Core Electronics](https://core-electronics.com.au/continuous-rotation-micro-servo-fs90r.html.plain.md) (Adafruit ADA2442, noted as retired there), [Servo Database](https://servodatabase.com/servo/feetech/fs90r).
- The FS90R body is the same size class as the MG90S, so the designer reuses the same motor-window numbers. Measure yours.
- Kid rules: limit wheg throttle to 50% at first (110 rpm is fast for 50 mm spokes); trim each servo until it stands still at "stop"; first test on the bench with the wheels off.
- Power: 12 servos can pull several amps if they stall together. The tripod gait moves 6 at once. NiMH AA pack ok; never LiPo (see kid-edition.md).

## Unverified
Everything mechanical is script-checked only. No part has been printed, no FS90R has been bought or run, and the wheg climbing height and hexapod tripod stability are model estimates.
