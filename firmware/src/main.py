"""Walker robot entry point (runs automatically on boot).

Control:
  - Wi-Fi: join network "walker-robot", browse to http://192.168.4.1
  - REPL:  press Ctrl-C to stop main, then e.g.
             import main; r = main.Robot(); r.do("stand")
"""
import asyncio
import time

from machine import ADC, I2C, Pin

import config
from drive import make_rig
from pca9685 import PCA9685


class Robot:
    def __init__(self):
        i2c = I2C(0, sda=Pin(config.I2C_SDA), scl=Pin(config.I2C_SCL), freq=config.I2C_FREQ)
        if config.PCA_ADDR not in i2c.scan():
            raise OSError("PCA9685 not found on I2C - check SDA/SCL/3V3/GND wiring")
        pca = PCA9685(i2c, config.PCA_ADDR, config.SERVO_FREQ, config.PCA_OSC_HZ)
        self.rig = make_rig(config, pca)
        self.adc = ADC(Pin(config.BATT_PIN))
        self.adc.atten(ADC.ATTN_11DB)
        self.led = Pin(config.STATUS_LED, Pin.OUT)
        self.mode = "relaxed"
        self.vbat = None
        self.lowbatt = False

    # ---- commands ----
    MOVES = {"fwd": (1, 0), "back": (-1, 0), "left": (0, 1), "right": (0, -1),
             "fwd_left": (1, 0.5), "fwd_right": (1, -0.5)}

    def do(self, cmd):
        if self.lowbatt and cmd not in ("relax", "stop"):
            return
        if cmd in self.MOVES:
            if self.mode == "relaxed":
                self.rig.stand()
            self.rig.command(*self.MOVES[cmd])
            self.mode = cmd
        elif cmd == "stop":
            self.rig.stop()
            if self.mode != "relaxed":
                self.mode = "stopping"
        elif cmd == "stand":
            self.rig.stand()
            self.mode = "standing"
        elif cmd == "relax":
            self.rig.relax()
            self.mode = "relaxed"

    def status(self):
        return {"mode": self.mode, "vbat": self.vbat, "lowbatt": self.lowbatt}

    # ---- loops ----
    async def gait_loop(self):
        period_ms = 1000 // config.LOOP_HZ
        last = time.ticks_ms()
        while True:
            now = time.ticks_ms()
            dt = time.ticks_diff(now, last) / 1000
            last = now
            if self.mode != "relaxed":
                if self.rig.moving or self.mode not in ("standing", "stopping"):
                    self.rig.update(dt)
                elif self.mode == "stopping":
                    self.rig.update(dt)
                    self.mode = "standing"
            await asyncio.sleep_ms(period_ms)

    def read_vbat(self, n=8):
        uv = sum(self.adc.read_uv() for _ in range(n)) / n
        return uv / 1e6 * config.BATT_DIVIDER

    async def battery_loop(self):
        while True:
            self.vbat = self.read_vbat()
            if self.vbat < 3.0:
                pass                                  # running on USB, no battery
            elif self.vbat < config.BATT_CUTOFF_V:
                if not self.lowbatt:
                    print("battery cutoff %.2f V - relaxing" % self.vbat)
                self.lowbatt = True
                self.do("relax")
            elif self.vbat < config.BATT_WARN_V:
                print("battery low %.2f V" % self.vbat)
            await asyncio.sleep(2)

    async def led_loop(self):
        while True:
            self.led.value(not self.led.value())
            await asyncio.sleep_ms(100 if self.lowbatt else 250 if self.rig.moving else 1000)


async def run():
    import webctl
    robot = Robot()
    ip = webctl.start_ap(config.WIFI_SSID, config.WIFI_PASSWORD)
    await webctl.serve(robot, config.HTTP_PORT)
    print("Walker ready: join Wi-Fi '%s' and open http://%s" % (config.WIFI_SSID, ip))
    robot.do("stand")
    await asyncio.gather(robot.gait_loop(), robot.battery_loop(), robot.led_loop())


if __name__ == "__main__":
    try:
        asyncio.run(run())
    finally:
        asyncio.new_event_loop()
