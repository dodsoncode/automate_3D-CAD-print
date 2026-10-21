"""Picks the controller for the chosen robot style and gives all three the same small interface:

    rig.command(fwd, turn)   rig.stop()   rig.stand()   rig.relax()   rig.update(dt)   rig.moving

Pure Python (no machine imports) so it is tested on a PC with a fake servo driver.
"""
import gait


class LeggedRig:
    """Crab or hexapod: angle servos driven from a Walker / HexWalker pose."""

    def __init__(self, servos, walker, stand_pose):
        self.servos = servos
        self.walker = walker
        self._stand = stand_pose

    @property
    def moving(self):
        return self.walker.moving

    def command(self, fwd, turn):
        self.walker.command(fwd, turn)

    def stop(self):
        self.walker.stop()

    def stand(self):
        self.walker.stop()
        self.servos.apply(self._stand())

    def relax(self):
        self.walker.stop()
        self.walker.scale = {"L": 0.0, "R": 0.0}
        self.walker.lift_scale = 0.0
        self.servos.relax()

    def update(self, dt):
        self.servos.apply(self.walker.update(dt))


class WhegRig:
    """Windmill rover: continuous-rotation servos. A pulse of exactly stop_us (plus trim) means standing still."""

    def __init__(self, driver, channels, signs, trims, drive, stop_us=1500, span_us=500):
        self.driver = driver
        self.channels = channels
        self.signs = signs
        self.trims = trims
        self.drive = drive
        self.stop_us = stop_us
        self.span_us = span_us

    @property
    def moving(self):
        return self.drive.moving

    def command(self, fwd, turn):
        self.drive.command(fwd, turn)

    def stop(self):
        self.drive.stop()

    def _write(self, speeds):
        for leg, ch in self.channels.items():
            self.driver.set_us(ch, gait.wheg_pulse_us(speeds[leg], self.signs[leg], self.trims[leg], self.span_us, self.stop_us))

    def stand(self):
        self.drive.stop()
        self.drive.scale = {"L": 0.0, "R": 0.0}
        self._write({leg: 0.0 for leg in self.channels})

    def relax(self):
        self.drive.stop()
        self.drive.scale = {"L": 0.0, "R": 0.0}
        for ch in self.channels.values():
            self.driver.off(ch)

    def update(self, dt):
        self._write(self.drive.update(dt))


def make_rig(cfg, driver, signs=None, offsets=None, trims=None):
    """Build the rig for cfg.STYLE. signs/offsets/trims default to the saved calibration."""
    from servos import Servos
    style = cfg.STYLE
    if style == "wheg":
        trims = trims if trims is not None else cfg.load_wheg_trim()
        drive = gait.WhegDrive(cfg.WHEG_MAX_THROTTLE, cfg.WHEG_RPM_FULL)
        return WhegRig(driver, cfg.WHEG_CHANNELS, cfg.load_wheg_signs(), trims, drive, cfg.WHEG_STOP_US, cfg.WHEG_SPAN_US)
    channels, _, _ = cfg.style_tables(style)
    if signs is None or offsets is None:
        signs, offsets = cfg.load_calib(style=style)
    servos = Servos(driver, channels, signs, offsets, cfg.LIMITS, cfg.SERVO_US_MIN, cfg.SERVO_US_MAX, cfg.SERVO_RANGE_DEG)
    if style == "hex":
        return LeggedRig(servos, gait.HexWalker(cfg.GAIT_STRIDE_DEG, cfg.GAIT_LIFT_DEG, cfg.GAIT_PERIOD_S), gait.hex_stand_pose)
    return LeggedRig(servos, gait.Walker(cfg.GAIT_STRIDE_DEG, cfg.GAIT_LIFT_DEG, cfg.GAIT_PERIOD_S,
                                         sway_deg=cfg.GAIT_SWAY_DEG, splay_deg=cfg.GAIT_SPLAY_DEG), gait.stand_pose)
