"""Minimal PCA9685 16-channel PWM driver (MicroPython machine.I2C compatible)."""
import time

_MODE1 = 0x00
_MODE2 = 0x01
_LED0_ON_L = 0x06
_PRESCALE = 0xFE

_RESTART = 0x80
_SLEEP = 0x10
_AI = 0x20       # register auto-increment
_OUTDRV = 0x04   # totem-pole outputs
_FULL = 0x1000   # full-on / full-off bit


class PCA9685:
    def __init__(self, i2c, address=0x40, freq=50, osc_hz=25_000_000):
        self.i2c = i2c
        self.address = address
        self.osc_hz = osc_hz
        self._write(_MODE2, _OUTDRV)
        self._write(_MODE1, _AI)
        time.sleep(0.005)
        self.set_freq(freq)

    def _write(self, reg, value):
        self.i2c.writeto_mem(self.address, reg, bytes([value & 0xFF]))

    def _read(self, reg):
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]

    def set_freq(self, freq):
        prescale = int(self.osc_hz / (4096 * freq) + 0.5) - 1
        prescale = max(3, min(255, prescale))
        old = self._read(_MODE1)
        self._write(_MODE1, (old & ~_RESTART) | _SLEEP)   # must sleep to change prescale
        self._write(_PRESCALE, prescale)
        self._write(_MODE1, old & ~_SLEEP)
        time.sleep(0.005)
        self._write(_MODE1, (old & ~_SLEEP) | _RESTART | _AI)
        # actual frequency after integer rounding
        self.freq = self.osc_hz / (4096 * (prescale + 1))
        self.prescale = prescale

    def pwm(self, channel, on, off):
        self.i2c.writeto_mem(self.address, _LED0_ON_L + 4 * channel,
                             bytes([on & 0xFF, (on >> 8) & 0x1F,
                                    off & 0xFF, (off >> 8) & 0x1F]))

    def us_to_ticks(self, us):
        return int(us * self.freq * 4096 / 1_000_000 + 0.5)

    def set_us(self, channel, us):
        self.pwm(channel, 0, min(4095, max(0, self.us_to_ticks(us))))

    def off(self, channel):
        """Stop pulses: servo goes limp."""
        self.pwm(channel, 0, _FULL)
