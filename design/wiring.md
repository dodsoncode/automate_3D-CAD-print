# Wiring, pin map and power budget

## Pin map (ESP32 DevKit)

| ESP32 pin | Connects to | Notes |
|---|---|---|
| GPIO21 (SDA) | PCA9685 SDA | I2C, 400 kHz |
| GPIO22 (SCL) | PCA9685 SCL | |
| 3V3 | PCA9685 VCC | Logic supply for PCA9685 (NOT servo power) |
| GND | PCA9685 GND, UBEC -, battery - | **Common ground is required** |
| VIN (5V) | UBEC + (5 V) | Powers ESP32 via its onboard regulator. Do not also power from USB while battery is connected unless your board has a VIN/USB diode (most DevKits do) |
| GPIO34 (ADC1, input only) | Battery divider midpoint | 100 kΩ from battery +, 47 kΩ to GND |
| GPIO2 | Onboard LED | Status blink |

## Servo channels (PCA9685)

Looking down on the robot, front at the top:

```
        FRONT
  FL (ch0 hip, ch1 knee)    FR (ch2 hip, ch3 knee)
            +-------------------+
            |   ESP32  PCA9685  |
            |      battery      |
            +-------------------+
  RL (ch4 hip, ch5 knee)    RR (ch6 hip, ch7 knee)
        REAR
```

| Channel | Joint | Channel | Joint |
|---|---|---|---|
| 0 | Front-left hip | 4 | Rear-left hip |
| 1 | Front-left knee | 5 | Rear-left knee |
| 2 | Front-right hip | 6 | Rear-right hip |
| 3 | Front-right knee | 7 | Rear-right knee |

Servo plug orientation on the PCA9685: brown/black = GND, red = V+, orange/yellow = signal (PWM).
Channels 8-15 are free for a later upgrade to 3-DOF legs.

## Power wiring

```
 2S LiPo + ──[switch]──┬── UBEC IN+ ── UBEC OUT+ (5-6 V) ──┬── PCA9685 V+ terminal (servo rail)
                       │                                    ├── 1000 µF cap (+) at PCA9685
                       │                                    └── ESP32 VIN
                       └── 100 kΩ ──┬── GPIO34
                                    └── 47 kΩ ── GND
 2S LiPo − ─────────────────────────── UBEC IN− ── UBEC OUT− ── PCA9685 GND ── ESP32 GND
```

Battery sense: V_adc = V_bat x 47 / 147. A full 8.4 V reads 2.69 V and a 6.6 V cutoff reads 2.11 V,
both inside the ESP32 ADC's 11 dB range. The divider draws ~57 µA. Put it after the switch
so it doesn't drain the battery when the robot is off.

## Power budget

| Load | Typical | Peak |
|---|---|---|
| ESP32 with Wi-Fi AP active | 0.12 A | 0.3 A |
| MG90S x 8 while walking (only 1-2 moving hard at once) | 0.8-1.5 A | ~5 A if all stall (~0.7 A each) |
| PCA9685 logic | <0.01 A | |

A 5 A UBEC covers realistic peaks. At ~1.2 A average, a 1000 mAh pack gives roughly 30-40 min.
The firmware stops the gait and relaxes the servos below 6.6 V (3.3 V/cell) and warns at 7.0 V.

## Bring-up checklist

1. Before connecting anything, check the UBEC output with a multimeter (5.0-6.0 V).
2. Connect the ESP32 by USB only, flash MicroPython, and confirm the REPL works.
3. Wire I2C + 3V3 + GND to the PCA9685 and run `i2c.scan()`. It should list `[64]` (0x40).
4. Connect the battery with no servos attached and check the ESP32 boots from VIN.
5. Attach **one** servo on ch0, run `calibrate.py`, and confirm it moves to neutral.
6. Attach the rest, set every joint to neutral, *then* fit the horns and printed links at the neutral pose.
