"""Tiny phone-friendly web remote served from the ESP32 (asyncio)."""
import asyncio
import json

PAGE = """<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">
<title>Walker</title><style>
body{font-family:sans-serif;text-align:center;background:#111;color:#eee;margin:0;padding:16px}
.g{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;max-width:340px;margin:16px auto}
button{font-size:22px;padding:22px 0;border:0;border-radius:12px;background:#2a6;color:#fff}
button.s{background:#c33}button.n{background:#555}#st{font-size:14px;color:#aaa}
</style></head><body><h2>Walker</h2>
<div class=g>
<span></span><button onclick="c('fwd')">&#9650;</button><span></span>
<button onclick="c('left')">&#10226;</button><button class=s onclick="c('stop')">&#9632;</button><button onclick="c('right')">&#10227;</button>
<span></span><button onclick="c('back')">&#9660;</button><span></span>
<button class=n onclick="c('stand')">stand</button><span></span><button class=n onclick="c('relax')">relax</button>
</div><div id=st>...</div>
<script>
function c(m){fetch('/cmd?m='+m).then(r=>r.json()).then(s)}
function s(j){document.getElementById('st').textContent=
 'mode: '+j.mode+'  |  battery: '+(j.vbat?j.vbat.toFixed(2)+' V':'?')+(j.lowbatt?'  LOW!':'')}
setInterval(()=>fetch('/status').then(r=>r.json()).then(s),2000);
</script></body></html>"""


def _parse(line):
    try:
        path = line.decode().split(" ")[1]
    except (IndexError, UnicodeError):
        return "/", {}
    if "?" not in path:
        return path, {}
    path, qs = path.split("?", 1)
    args = {}
    for kv in qs.split("&"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            args[k] = v
    return path, args


async def _handle(reader, writer, robot):
    try:
        line = await reader.readline()
        while True:                      # drain headers
            h = await reader.readline()
            if not h or h == b"\r\n":
                break
        path, args = _parse(line)
        if path == "/cmd":
            robot.do(args.get("m", "stop"))
            body, ctype = json.dumps(robot.status()), "application/json"
        elif path == "/status":
            body, ctype = json.dumps(robot.status()), "application/json"
        elif path == "/":
            body, ctype = PAGE, "text/html"
        else:
            writer.write(b"HTTP/1.0 404 Not Found\r\n\r\n")
            await writer.drain()
            return
        data = body.encode()
        writer.write(("HTTP/1.0 200 OK\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
                      "Connection: close\r\n\r\n" % (ctype, len(data))).encode())
        writer.write(data)
        await writer.drain()
    except Exception as e:  # never let a bad request kill the robot loop
        print("http error:", e)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


def start_ap(ssid, password):
    import network
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    try:
        ap.config(ssid=ssid, key=password, security=3)       # MicroPython >= 1.20
    except (TypeError, ValueError, OSError):
        ap.config(essid=ssid, password=password, authmode=3)  # older firmware
    return ap.ifconfig()[0]


async def serve(robot, port=80):
    return await asyncio.start_server(lambda r, w: _handle(r, w, robot), "0.0.0.0", port)
