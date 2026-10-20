# Kid Edition

The same four-legged walker, rebuilt so a 9-year-old can **design it, program it and assemble it**
without soldering, loose battery wiring or text-only code. The original ESP32/LiPo build
([README.md](README.md), [components.md](components.md)) stays as the "maker edition" for later.

## Who does what

| Step | Kid | Adult |
|---|---|---|
| Design the robot (shape, legs, colors) in the Walker Designer GUI (`gui/`) | Yes | Helps read the "checks" panel |
| Slice and print | Picks colors | **Runs the printer**, removes parts, trims support/brims with a hobby knife |
| Assemble (screws, plug in servos, rubber bands) | Yes | Checks power wiring and battery before the first power-on |
| Program with MakeCode blocks (or Python) | Yes | Charges batteries |
| Test and tune | Yes | Present for the first power-on and any "smoke or hot" event |

## What changed, and why

| Part | Maker edition | Kid edition | Why |
|---|---|---|---|
| Controller | ESP32 DevKit + MicroPython | **BBC micro:bit V2** | Programs in a browser with blocks (and Python) at makecode.microbit.org: nothing to install, drag-and-drop a file to run, LED display, two buttons, tilt sensor and speaker built in. Edge-connector socket: no wiring |
| Servo wiring | Jumper wires to a PCA9685 board | **Kitronik Compact 16 Servo Driver Board** (PCA9685 on a micro:bit edge connector) | The micro:bit plugs straight in. Servos plug into labeled 3-pin headers. Has a power switch and a 3.3 V regulator for the micro:bit. No soldering |
| Power | 2S LiPo + UBEC + switch + voltage divider | **Battery holder with cover and switch, rechargeable AA NiMH** | No LiPo fire risk, no charger knowledge needed, no soldering, no voltage divider. Cells are shielded by the holder |
| Servos | 8x MG90S | 8x MG90S (unchanged) | Metal gears survive a kid forcing a leg by hand. Same size as SG90, so the CAD is unchanged |
| Retention | Screws, heat-set inserts, velcro | **Rubber bands through printed slots, snap-in pockets, big M2 self-tapping servo screws only** | Heat-set inserts need a soldering iron. Rubber bands are friendly and fixable |
| Leg identification | Text labels | **Color-coded legs** (each leg a different AMS filament) + numbered cable flags | The program says "red leg" and the kid sees the red leg; uses all four AMS slots |
| Electronics visibility | Closed lid | **Open top**: micro:bit sits in a cradle so the LEDs and buttons show | Feedback and debugging |
| Battery monitor | ADC divider + cutoff | Replaced by a "wobble when weak" check: servo twitch = change batteries; software cut-off dropped | Fewer parts. See Open items |

### Power note (important)
The Kitronik board takes 3-12 V and powers the servos **straight from the battery supply**. MG90S servos
are rated about 4.8-6.0 V. So:
- **Use 4x AA NiMH rechargeable (4.8-5.6 V).** Do not use a 9 V battery, a LiPo or more than 4 cells.
- Fresh **alkaline** 4xAA measure about 6.2-6.4 V, slightly over the servo rating. Use 3xAA alkaline (4.5 V) instead if you use alkalines.
- An adult checks the pack with a multimeter before the first power-on.

## Kid bill of materials

Prices are approximate and not all verified; check stock before ordering.

| Qty | Part | Notes | ~Cost |
|---|---|---|---|
| 1 | BBC micro:bit V2 | Must be V2 for the speaker/sound blocks. Not included with the driver board | $20-25 |
| 1 | Kitronik Compact 16 Servo Driver Board for micro:bit | Seen at £12.30 at one UK shop with low stock; another shop lists it as no longer stocked. 68 x 46.5 x 10.6 mm, PCA9685, V1 and V2. **Alternatives to check:** Keyestudio 16-channel servo shield for micro:bit (KS0438); Kitronik Compact All-In-One Robotics Board | ~$15-20 |
| 8 (+2 spare) | MG90S metal-gear micro servo | 10-pack is cheapest | $20-30 |
| 1 | 4xAA battery holder with cover and switch, matching connector for the board (terminal block or servo-style plug) | Check the plug fits the board before buying | $4-8 |
| 4-8 | AA NiMH rechargeable cells + charger | Lasts about 30-40 min per charge | $15-25 |
| ~20 | M2 x 6-8 mm self-tapping screws, Phillips | Servos include a few; buy a bag | $3 |
| 1 | Small magnetic Phillips screwdriver (#0 or #00) | Kid-size handle | $5 |
| 8-12 | Rubber bands or hair ties (small) | Hold battery and board | $1 |
| - | Filament: up to 4 colors for the AMS | One color per leg; the body in a fifth or a shared one | on hand |

Total roughly $70-100 depending on what you have. A USB cable for the micro:bit is needed (micro-USB).

## Mechanical changes in the GUI-generated design

The printed parts come from the Walker Designer (see `gui/README.md`), which replaces the old plan of
hand-coding the CAD:

- **Body tray**: floor plate with four hip-servo cut-outs, an open cradle for the board + micro:bit, a bay for the battery holder, rubber-band slots, rounded corners (all outlines are kid-adjustable).
- **Accent trim**: a thin ring on the body, printed as a second part in a second AMS color.
- **Legs (x4)**: an L-shaped *coxa* (hip horn to knee servo) and a *femur* (knee horn to foot), plus a snap-on *foot pad*. Each leg is its own color.
- All plates print flat; no supports on the main faces.
- Servo, battery and board sizes are parameters with a "measure yours" panel.

## Programming ladder (MakeCode)

| Level | Goal | How |
|---|---|---|
| 0 | Wiggle one servo | Standard servo blocks / `walker` "test servo" block |
| 1 | Make the robot stand and pose | "stand", "set leg" blocks |
| 2 | Take one step with one leg | Sequence of "set leg" + "pause" |
| 3 | Walk | "walk forward / backward / turn", sliders for stride, lift, speed |
| 4 | Invent | Buttons, tilt, sound, LED faces, dances, remote control by radio between two micro:bits |

The `walker` blocks live in `makecode-kid/` and are ported from the tested gait in `firmware/src/gait.py`.

## Rules for the first power-on (adult)

1. Battery pack voltage checked (4.8-5.6 V for NiMH).
2. Robot on a stand so the feet hang free.
3. Switch off, micro:bit plugged into the board, servos plugged in by number, nothing else connected.
4. Switch on. Servos twitch to neutral. Anything hot or smelly: switch off.
5. Do not push legs by hand while powered.

## Open items

- The driver board's I2C address is unconfirmed (could not read Kitronik's source). The extension scans for it.
- Servo plug orientation and power-plug type must be confirmed on the real board.
- The physical dimensions of your battery holder, the Kitronik board stack height and your MG90S servos must be measured and entered in the GUI.
- Low-battery cut-off is not implemented in the kid edition; brownouts could reset the micro:bit when batteries are weak.
- Not yet checked on real hardware: everything above.
