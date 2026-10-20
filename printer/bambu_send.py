#!/usr/bin/env python3
"""
bambu_send.py - talk to a Bambu Lab P1S (with AMS) over the local network.

  status  : connect, print printer state + what's loaded in each AMS slot
  send    : upload a SLICED .gcode.3mf over FTPS and start the print over MQTT
  slice   : (optional, experimental) slice a .3mf with the Bambu Studio CLI

Printer setup (on the P1S screen):
  Settings > WLAN  -> note IP address and Access Code
  Enable "LAN Only Mode", then enable "Developer Mode"
  (Developer Mode is what allows third-party MQTT/FTP control.)
Serial number: Settings > Device (or Bambu Studio > Device tab).

Install:  pip install paho-mqtt
Config :  put ip/serial/access_code in bambu_config.json next to this file,
          or pass --ip --serial --code on the command line.

Examples:
  python bambu_send.py status
  python bambu_send.py send cube_disk_2color.gcode.3mf --ams-map 0,1
  python bambu_send.py send part.gcode.3mf --no-ams

Run this on a computer on the same network as the printer.
"""
import argparse
import ftplib
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import time

try:
    import paho.mqtt.client as mqtt
except ImportError:
    sys.exit("Missing dependency: pip install paho-mqtt")

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bambu_config.json")
MQTT_PORT = 8883
FTPS_PORT = 990
USER = "bblp"


def tls_context():
    # The printer presents a self-signed certificate on the LAN, so it can't be
    # verified against public CAs. Traffic is still encrypted.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ------------------------------- FTPS upload -------------------------------
class ImplicitFTPS(ftplib.FTP_TLS):
    """Implicit-TLS FTP (port 990) with TLS session reuse on the data channel,
    which the Bambu FTP server requires."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._sock = None

    @property
    def sock(self):
        return self._sock

    @sock.setter
    def sock(self, value):
        if value is not None and not isinstance(value, ssl.SSLSocket):
            value = self.context.wrap_socket(value, server_hostname=self.host)
        self._sock = value

    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(conn, server_hostname=self.host,
                                            session=self.sock.session)
        return conn, size


def ftps_upload(ip, code, local_path, remote_name):
    ftp = ImplicitFTPS(context=tls_context(), timeout=30)
    ftp.connect(ip, FTPS_PORT)
    ftp.login(USER, code)
    ftp.prot_p()
    size = os.path.getsize(local_path)
    sent = 0
    # Manual STOR: ftplib's storbinary() calls unwrap() on the data socket,
    # which hangs on Bambu firmware.
    conn = ftp.transfercmd(f"STOR {remote_name}")
    with open(local_path, "rb") as f:
        while chunk := f.read(64 * 1024):
            conn.sendall(chunk)
            sent += len(chunk)
            print(f"\r  uploading {sent * 100 // size:3d}%", end="", flush=True)
    conn.close()
    print()
    try:
        ftp.voidresp()
    except (ftplib.error_temp, socket.timeout, TimeoutError):
        pass  # some firmware never sends the 226 reply; upload is done
    try:
        ftp.quit()
    except Exception:
        ftp.close()


# --------------------------------- MQTT ------------------------------------
class Printer:
    def __init__(self, ip, serial, code):
        self.serial = serial
        self.state = {}
        self.got_report = False
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                             client_id=f"bambu_send_{os.getpid()}")
        self.c.username_pw_set(USER, code)
        self.c.tls_set_context(tls_context())
        self.c.tls_insecure_set(True)
        self.c.on_connect = self._on_connect
        self.c.on_message = self._on_message
        self.c.connect(ip, MQTT_PORT, keepalive=30)
        self.c.loop_start()

    def _on_connect(self, client, userdata, flags, rc, props=None):
        if rc != 0:
            print(f"MQTT connect failed: {rc} (check access code / Developer Mode)")
            return
        client.subscribe(f"device/{self.serial}/report")
        self.publish({"pushing": {"sequence_id": "0", "command": "pushall"}})

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload)
        except ValueError:
            return
        p = data.get("print", {})
        self.state.update(p)  # reports are incremental; merge them
        if "gcode_state" in p or "ams" in p:
            self.got_report = True

    def publish(self, payload):
        self.c.publish(f"device/{self.serial}/request", json.dumps(payload))

    def wait_report(self, timeout=15):
        t0 = time.time()
        while not self.got_report and time.time() - t0 < timeout:
            time.sleep(0.2)
        return self.got_report

    def close(self):
        self.c.loop_stop()
        self.c.disconnect()

    def start_print(self, remote_name, plate=1, use_ams=True, ams_map=None,
                    bed_level=True, timelapse=False):
        cmd = {
            "print": {
                "sequence_id": "0",
                "command": "project_file",
                "param": f"Metadata/plate_{plate}.gcode",
                "url": f"file:///sdcard/{remote_name}",
                "subtask_name": remote_name.removesuffix(".3mf").removesuffix(".gcode"),
                "project_id": "0", "profile_id": "0",
                "task_id": "0", "subtask_id": "0",
                "md5": "",
                "timelapse": timelapse,
                "bed_type": "auto",
                "bed_levelling": bed_level,
                "flow_cali": False,
                "vibration_cali": True,
                "layer_inspect": False,
                "use_ams": use_ams,
            }
        }
        if use_ams and ams_map is not None:
            cmd["print"]["ams_mapping"] = ams_map
        self.publish(cmd)


def describe(state):
    print(f"  state      : {state.get('gcode_state', '?')}")
    print(f"  progress   : {state.get('mc_percent', '?')}%  "
          f"(layer {state.get('layer_num', '?')}/{state.get('total_layer_num', '?')})")
    print(f"  nozzle/bed : {state.get('nozzle_temper', '?')} / {state.get('bed_temper', '?')} C")
    ams = state.get("ams", {}).get("ams", [])
    if not ams:
        print("  AMS        : none reported")
    for unit in ams:
        uid = int(unit.get("id", 0))
        for tray in unit.get("tray", []):
            tid = int(tray.get("id", 0))
            idx = uid * 4 + tid
            kind = tray.get("tray_type") or "(empty)"
            color = tray.get("tray_color", "")
            print(f"  AMS {uid + 1} slot {tid + 1} [map index {idx}]: {kind} #{color[:6]}")


# --------------------------------- slicing ---------------------------------
def find_studio():
    for c in ("bambu-studio", "BambuStudio",
              r"C:\Program Files\Bambu Studio\bambu-studio.exe",
              "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"):
        if shutil.which(c) or os.path.exists(c):
            return shutil.which(c) or c
    return None


def slice_3mf(src, out, machine, process, filaments):
    exe = find_studio()
    if not exe:
        sys.exit("Bambu Studio not found. Slice in the GUI instead: "
                 "Slice plate > File > Export > Export plate sliced file.")
    cmd = [exe, "--slice", "0", "--export-3mf", out]
    if machine and process:
        cmd += ["--load-settings", f"{machine};{process}"]
    if filaments:
        cmd += ["--load-filaments", ";".join(filaments)]
    cmd.append(src)
    print("Running:", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0 or not os.path.exists(out):
        sys.exit("Slicing failed - slice in the GUI and export the plate sliced file.")
    print(f"Sliced -> {out}")


# ---------------------------------- CLI ------------------------------------
def load_conn(args):
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
    ip = args.ip or cfg.get("ip")
    serial = args.serial or cfg.get("serial")
    code = args.code or cfg.get("access_code")
    if not (ip and serial and code):
        sys.exit("Need printer ip, serial and access code "
                 f"(flags or {CONFIG_FILE}).")
    return ip, serial, code


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ip"); ap.add_argument("--serial"); ap.add_argument("--code")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="show printer state and AMS contents")

    s = sub.add_parser("send", help="upload a sliced .gcode.3mf and start it")
    s.add_argument("file")
    s.add_argument("--plate", type=int, default=1)
    s.add_argument("--ams-map", default="0,1",
                   help="AMS tray index per filament in the file, e.g. 0,1 "
                        "(filament 1 -> slot 1, filament 2 -> slot 2)")
    s.add_argument("--no-ams", action="store_true")
    s.add_argument("--no-level", action="store_true", help="skip bed leveling")
    s.add_argument("--timelapse", action="store_true")
    s.add_argument("--yes", action="store_true", help="don't ask for confirmation")

    sl = sub.add_parser("slice", help="(experimental) slice with Bambu Studio CLI")
    sl.add_argument("file"); sl.add_argument("-o", "--out")
    sl.add_argument("--machine", help="machine profile .json")
    sl.add_argument("--process", help="process profile .json")
    sl.add_argument("--filament", action="append", help="filament profile .json (repeat per slot)")

    args = ap.parse_args()

    if args.cmd == "slice":
        out = args.out or os.path.splitext(args.file)[0] + ".gcode.3mf"
        slice_3mf(args.file, out, args.machine, args.process, args.filament)
        return

    ip, serial, code = load_conn(args)
    p = Printer(ip, serial, code)
    try:
        if not p.wait_report():
            sys.exit("No report from printer. Check IP, serial, access code, "
                     "and that LAN Only + Developer Mode are on.")
        print(f"Connected to {serial} at {ip}")
        describe(p.state)
        if args.cmd == "status":
            return

        if not args.file.endswith(".3mf"):
            sys.exit("Send a sliced .gcode.3mf (export 'plate sliced file' from Bambu Studio).")
        if p.state.get("gcode_state") in ("RUNNING", "PREPARE", "PAUSE"):
            sys.exit("Printer is busy - not starting a new job.")
        ams_map = None if args.no_ams else [int(x) for x in args.ams_map.split(",")]
        remote = os.path.basename(args.file).replace(" ", "_")
        if not args.yes:
            print(f"\nAbout to print {remote} (plate {args.plate}, "
                  f"{'no AMS' if args.no_ams else f'AMS map {ams_map}'}).")
            if input("Plate clear and filaments loaded? [y/N] ").strip().lower() != "y":
                sys.exit("Cancelled.")
        print("Uploading over FTPS...")
        ftps_upload(ip, code, args.file, remote)
        print("Starting print...")
        p.start_print(remote, args.plate, not args.no_ams, ams_map,
                      bed_level=not args.no_level, timelapse=args.timelapse)
        time.sleep(8)
        describe(p.state)
    finally:
        p.close()


if __name__ == "__main__":
    main()
