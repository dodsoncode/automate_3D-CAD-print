# Mechanical design

## Leg layout

Each leg has 2 joints:

- **Hip (yaw).** The servo is mounted vertically in the chassis corner, output shaft pointing down.
  It rotates the leg forward/back in the horizontal plane.
- **Knee (lift).** The servo is mounted horizontally in the coxa bracket. It rotates the femur up/down
  to lift and plant the foot.

At the neutral pose (all servos at 90°), the legs point out diagonally at 45° from the body
axis. The femurs angle down so the body rides ~35-40 mm off the ground.

```
 side view of one leg (neutral)

   chassis ──┐
   [hip servo]──coxa──[knee servo]
                             \
                              \  femur (~55 mm)
                               \
                                o foot pad
```

## MG90S reference dimensions (verify against your servos with calipers)

| Feature | mm |
|---|---|
| Body (L x W x H, without tabs) | 22.8 x 12.2 x 22.5 |
| Length across mounting tabs | 32.2 |
| Tab hole spacing (center to center) | 27.8 |
| Tab thickness | 2.5 |
| Tab top to body top | 4.0 |
| Output shaft offset from body end | 5.9 |
| Total height including shaft | 28.5-29 |
| Spline | 20 T, ~4.8 mm OD |

Servo dimensions vary between vendors, so the CAD will take these as parameters with a
+0.3 mm pocket clearance by default.

## Printed parts

| Part | Qty | Function | Key features |
|---|---|---|---|
| Chassis tray | 1 | Backbone | 4 hip-servo pockets at the corners (vertical), ESP32 + PCA9685 standoffs, battery bay with strap slots, switch cut-out, cable pass-throughs |
| Chassis lid | 1 | Cover, stiffens tray | Snap or 4x M3 into heat-set inserts; vents; optional two-color logo |
| Coxa bracket | 4 (2 L, 2 R mirrored) | Hip horn -> knee servo | Recess for the single-arm horn (screwed through), pocket for knee servo, ~25 mm hip-to-knee axis offset |
| Femur | 4 | Knee horn -> foot | ~55 mm, I-beam section for stiffness, horn recess, foot socket |
| Foot pad | 4 | Grip | Press-fit or glued, TPU optional |

## Design rules for the CAD

- Horn interface: put a recess for the stock plastic horn in the printed link and screw through it.
  Don't print splines; they won't hold.
- Clearances: servo pockets +0.3 mm, press-fits +0.1 mm, M2 self-tap pilot holes 1.6 mm.
- Walls >= 1.6 mm (4 perimeters at 0.4 mm nozzle), 30-40% gyroid infill on links.
- Print orientation: links flat on the bed so layer lines run along the length of the arm
  (bending strength). Chassis prints upside-down from the lid side or open side up, with no supports.
- Hip pockets need a hole on the bottom for the shaft plus horn, with clearance for the
  horn's full swing (±60° minimum).
- All dimensions are parameters in one `params.py`, so a different servo (e.g. SG90 or ES08MA)
  only needs new numbers.

## Range of motion (firmware limits)

| Joint | Neutral | Gait range used | Hard limit in firmware |
|---|---|---|---|
| Hip | 90° | ±20° | ±45° |
| Knee | 90° (standing) | 0 to +30° (lift) | -30° to +60° |

## Assembly order

1. Print one coxa + one femur, fit a servo to each, and check the horn fit. Adjust params if needed.
2. Print the full set. Center every servo with `calibrate.py` *before* fitting horns.
3. Fit the hip servos into the chassis and the knee servos into the coxas.
4. Fit the horns at neutral: the coxa points 45° outward, the femur angles down to the standing height.
5. Route the wires through the pass-throughs to the PCA9685. Mount the electronics and battery.
6. Fine-tune the per-servo offsets in `calib.json` until the robot stands level.
