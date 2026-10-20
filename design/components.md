# Components (bill of materials)

Prices are approximate US hobby-market prices (Amazon / AliExpress / Adafruit) and change
often. Check them before ordering.

## Electronics

| # | Qty | Part | Spec / notes | ~Cost |
|---|---|---|---|---|
| E1 | 1 | ESP32 DevKit V1 (ESP32-WROOM-32, 30- or 38-pin) | Wi-Fi/BT, 3.3 V logic, USB-serial on board. Get one with a USB-C or micro-USB port you have cables for | $6-10 |
| E2 | 1 | PCA9685 16-channel 12-bit PWM board | I2C address 0x40; has screw terminal for servo V+ | $5-8 |
| E3 | 8 (+2 spare) | MG90S micro servo, metal gear | 4.8-6 V, ~2.0 kg·cm, ~180° range. Buy a 10-pack | $20-30 |
| E4 | 1 | 2S LiPo 7.4 V, 800-1200 mAh | JST-XH balance lead + XT30 or JST main lead | $10-15 |
| E5 | 1 | UBEC 5 V or 6 V, >= 5 A continuous | Feeds servo rail and ESP32 VIN. 5 V is gentler on MG90S; 6 V gives more torque | $6-10 |
| E6 | 1 | Small slide or rocker switch, >= 5 A | Main power | $1-3 |
| E7 | 1 | Resistors 100 kΩ + 47 kΩ (1%) | Battery voltage divider -> GPIO34 | <$1 |
| E8 | 1 | 1000 µF 10 V electrolytic capacitor | Across servo rail at PCA9685 V+ to absorb current spikes | <$1 |
| E9 | 1 set | Dupont jumpers (F-F), servo extension leads if needed | | $3-5 |
| E10 | 1 | 2S LiPo balance charger | Skip if you already have one | $10-20 |

## Hardware

| # | Qty | Part | Notes |
|---|---|---|---|
| H1 | ~20 | M2 x 6-8 mm self-tapping screws | Servo mounting tabs into printed parts (MG90S includes some) |
| H2 | ~10 | M2.5 or M3 x 6 mm screws + heat-set inserts | Chassis lid, PCB standoffs |
| H3 | 8 | Servo horn screws (included with servos) | Horn to printed link |
| H4 | - | Double-sided foam tape / velcro strap | Battery retention |

## Printed parts (filament)

| Part | Qty | Material | Filament slot |
|---|---|---|---|
| Chassis tray | 1 | PETG or PLA+ | 1 (body color) |
| Chassis lid | 1 | PETG or PLA+ | 1, with logo/accents in 2 |
| Coxa bracket (hip -> knee servo) | 4 (2 mirrored pairs) | PETG or PLA+ | 1 |
| Femur / foot link | 4 | PETG or PLA+ | 1, with tip in 2 |
| Foot pad | 4 | TPU 95A (optional) or same as body | 2 |

PETG is preferred for parts that flex or clamp a servo horn. PLA is fine for a first test
build. TPU feet improve grip a lot, but the original AMS doesn't feed TPU, so print pads
from the external spool or skip them.

## Tools

USB cable for the ESP32, laptop with Python 3, soldering iron (for divider + switch + power leads),
small Phillips screwdriver, multimeter (strongly recommended for checking the UBEC output
before connecting servos).

## Rough total

Electronics ~$50-75 (including spare servos), hardware ~$5, filament ~$2.
If you already own a charger and jumpers: ~$45-60.
