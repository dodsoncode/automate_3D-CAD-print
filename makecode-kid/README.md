# makecode-kid: programming the walker with blocks

Blocks for a micro:bit + Kitronik Compact 16 Servo Driver (PCA9685) + 8 micro servos. The walking maths is ported from the tested `firmware/src/gait.py`.

**Status: script-checked only.** The gait matches the Python version to 1e-9 and the servo pulses are checked against a fake board (`tests/test_ts_parity.py`). It has NOT been loaded into the MakeCode editor and NOT run on real hardware or a real micro:bit. Expect small fixes (block wording, an I2C quirk).

## Put the blocks in a MakeCode project
1. Go to makecode.microbit.org, start a new project, switch to **JavaScript**.
2. Click the folder icon (Explorer), open `custom.ts`, delete what is there, paste in `dist/custom.ts` (rebuild with `python makecode-kid/build_custom.py`).
3. Switch back to **Blocks**. A blue **Walker** drawer appears.
(Repo is private, so "Extensions > paste URL" does not work. If the repo is made public, the folder can be added as an extension.)

## Servo plugs
Channels 0 to 7 in order: front-left hip, front-left knee, front-right hip, front-right knee, back-left hip, back-left knee, back-right hip, back-right knee. Colour the plugs with tape to match the leg colours from the designer.

## Levels
See `lessons/`. Level 0 wiggle one motor, 1 stand and pose, 2 one step, 3 walk, 4 invent.
