"""Image3D service for Render: serves the editor page and turns a photo into a GLB via a Hugging Face Space.

  uvicorn server:app --host 0.0.0.0 --port $PORT

Env: HF_TOKEN (Hugging Face read token), IMAGE3D_PASSCODE (shared passcode),
     HF_SPACE (default tencent/Hunyuan3D-2), HF_API_NAME (default /shape_generation; set it to an empty
     string to auto-pick an endpoint), HF_IMAGE_PARAM (default image: the keyword the endpoint takes the photo in),
     HF_EXTRA_JSON (extra settings for the call as a JSON object; default {"octree_resolution": 128} for the default Space).
Everything is read per request, so the tests can set it with monkeypatch.
"""
import concurrent.futures
import hmac
import json
import os
import tempfile
import time

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SPACE = "tencent/Hunyuan3D-2"
HF_SPACE = os.environ.get("HF_SPACE") or DEFAULT_SPACE
MAX_BYTES = 10 * 1024 * 1024
TIMEOUT_S = 300
BODY_LIMIT = MAX_BYTES + 64 * 1024  # multipart overhead allowance
MAX_DETAIL = 300
MAX_FAILS, FAIL_WINDOW_S, LOCK_S = 5, 600, 600
MAX_GLOBAL_FAILS = 30  # wrong passcodes from all clients together within the window
MAX_KEYS = 1000

app = FastAPI(title="Image3D", docs_url=None, redoc_url=None, openapi_url=None)

# ---------- wrong-passcode throttle (in memory) ----------
CLOCK = time.monotonic  # tests replace this
_fails = {}    # client key -> timestamps of recent wrong passcodes (oldest key first)
_locked = {}   # client key -> time the lock ends
_global = []   # timestamps of recent wrong passcodes from everyone


def reset_throttle():
    _fails.clear()
    _locked.clear()
    del _global[:]


def _global_locked():
    now = CLOCK()
    _global[:] = [t for t in _global if now - t < FAIL_WINDOW_S]
    return len(_global) > MAX_GLOBAL_FAILS


def _is_locked(key):
    until = _locked.get(key)
    if until is None:
        return False
    if CLOCK() < until:
        return True
    del _locked[key]
    _fails.pop(key, None)
    return False


def _sweep(now):
    for k in [k for k, ts in _fails.items() if now - ts[-1] >= FAIL_WINDOW_S and _locked.get(k, 0) <= now]:
        del _fails[k]
    for k in [k for k, until in _locked.items() if until <= now]:
        del _locked[k]
    for table in (_fails, _locked):
        while len(table) > MAX_KEYS:
            del table[next(iter(table))]  # drop the oldest


def _wrong(key):
    now = CLOCK()
    _global.append(now)
    recent = [t for t in _fails.pop(key, []) if now - t < FAIL_WINDOW_S] + [now]
    _fails[key] = recent  # re-inserted, so the table stays ordered by last attempt
    if len(recent) >= MAX_FAILS:
        _locked.pop(key, None)
        _locked[key] = now + LOCK_S
    _sweep(now)


def _client_key(scope, headers):
    """The LAST X-Forwarded-For entry is the one Render's proxy appended; earlier ones are client-controlled."""
    fwd = headers.get(b"x-forwarded-for", b"").decode("latin-1").split(",")[-1].strip()
    return fwd or (scope.get("client") or ("?",))[0]


class GenerateGuard:
    """ASGI middleware for POST /api/generate: checks configuration and passcode from the headers alone, then
    reads at most BODY_LIMIT bytes of body (also when chunked) BEFORE FastAPI parses the multipart upload."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/api/generate" or scope["method"] != "POST":
            return await self.inner(scope, receive, send)
        headers = dict(scope["headers"])

        async def reply(status, detail):
            await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)

        passcode, token = os.environ.get("IMAGE3D_PASSCODE"), os.environ.get("HF_TOKEN")
        if not passcode or not token:
            return await reply(500, "server not configured")
        ip = _client_key(scope, headers)
        if _global_locked() or _is_locked(ip):
            return await reply(429, "too many attempts, try again later")
        given = headers.get(b"x-passcode", b"")
        if not hmac.compare_digest(given, passcode.encode("utf-8")):
            _wrong(ip)
            return await reply(401, "wrong passcode")
        _fails.pop(ip, None)
        try:
            declared = int(headers.get(b"content-length", b"0") or 0)
        except ValueError:
            declared = 0
        if declared > BODY_LIMIT:
            return await reply(413, "image is too large (10 MB limit)")
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] != "http.request":
                return  # client went away
            body += message.get("body", b"")
            if len(body) > BODY_LIMIT:
                return await reply(413, "image is too large (10 MB limit)")
            if not message.get("more_body"):
                break
        sent = False

        async def replay():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.inner(scope, replay, send)


app.add_middleware(GenerateGuard)


def _fail(status, detail):
    return JSONResponse({"detail": detail}, status_code=status)


def _first_glb(obj):
    """First string path ending in .glb anywhere in a Gradio result (nested lists/tuples/dicts)."""
    if isinstance(obj, str):
        return obj if obj.lower().endswith(".glb") else None
    if isinstance(obj, dict):
        obj = list(obj.values())
    if isinstance(obj, (list, tuple)):
        for item in obj:
            found = _first_glb(item)
            if found:
                return found
    return None


def _takes_image(params):
    for p in params or []:
        text = " ".join(str(p.get(k, "")) for k in ("component", "type", "python_type", "label")).lower()
        if any(w in text for w in ("image", "file", "filepath")):
            return True
    return False


def _pick_endpoint(client):
    """Name of the first endpoint with an image/file input whose name contains 'generat' or 'shape'."""
    info = client.view_api(return_format="dict") or {}
    named = info.get("named_endpoints") or {}
    for name, spec in named.items():
        if _takes_image(spec.get("parameters")) and any(w in name.lower() for w in ("generat", "shape")):
            return name
    raise RuntimeError("could not find a generate endpoint on %s; set HF_API_NAME (see DEPLOY.md)" % HF_SPACE)


# Hunyuan3D-2 at its default resolution (256) returns about 900,000 triangles, too heavy for a phone;
# 128 gives about 115,000 and 96 about 55,000 (measured on a live run, 2026-11-11).
DEFAULT_EXTRA = {"octree_resolution": 128}


def _extra_settings(space, image_param):
    """Extra keyword settings for the Space call, from HF_EXTRA_JSON (a JSON object). Unset: the lighter-mesh
    default for the default Space, nothing for any other Space."""
    raw = os.environ.get("HF_EXTRA_JSON")
    if raw is None or not raw.strip():
        return dict(DEFAULT_EXTRA) if space == DEFAULT_SPACE else {}
    try:
        extra = json.loads(raw)
    except ValueError:
        raise RuntimeError("HF_EXTRA_JSON is not valid JSON") from None
    if not isinstance(extra, dict) or image_param in extra:
        raise RuntimeError("HF_EXTRA_JSON must be a JSON object that does not set the photo input")
    return extra


def generate_glb(image_bytes, filename):
    """Photo bytes -> GLB bytes through the Hugging Face Space. Run once against the live default Space on 2026-11-11 (from a workspace, not from Render)."""
    from gradio_client import Client, handle_file  # lazy: tests and import must work without it

    token = os.environ.get("HF_TOKEN")
    space = os.environ.get("HF_SPACE") or DEFAULT_SPACE
    try:
        client = Client(space, token=token)
    except TypeError:  # older gradio_client versions call the argument hf_token
        client = Client(space, hf_token=token)
    api_name = os.environ.get("HF_API_NAME", "/shape_generation") or _pick_endpoint(client)
    param = os.environ.get("HF_IMAGE_PARAM") or "image"
    extra = _extra_settings(space, param)
    suffix = os.path.splitext(filename or "")[1] or ".png"
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "photo" + suffix)
        with open(path, "wb") as f:
            f.write(image_bytes)
        job = client.submit(api_name=api_name, **{param: handle_file(path)}, **extra)
        try:
            result = job.result(timeout=TIMEOUT_S)
        except (TimeoutError, concurrent.futures.TimeoutError):
            try:
                job.cancel()
            except Exception:
                pass
            raise
    glb = _first_glb(result)
    if not glb or not os.path.exists(glb):
        raise RuntimeError("the Space returned no .glb file")
    with open(glb, "rb") as f:
        return f.read()


GENERATOR = generate_glb  # tests replace this


@app.get("/api/health")
def health():
    return {"ok": True, "space": HF_SPACE}


@app.post("/api/generate")
async def generate(image: UploadFile = File(...)):
    # configuration, passcode and body size are already enforced by GenerateGuard
    if not (image.content_type or "").startswith("image/"):
        return _fail(400, "that file is not an image")
    data = await image.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        return _fail(413, "image is too large (10 MB limit)")
    try:
        glb = await run_in_threadpool(GENERATOR, data, image.filename or "photo.png")
    except Exception as e:  # Space busy, quota, asleep, timeout ...
        return _fail(503, ("generation failed: %s" % (str(e) or e.__class__.__name__))[:MAX_DETAIL])
    return Response(glb, media_type="model/gltf-binary")


@app.get("/")
def root():
    return FileResponse(os.path.join(HERE, "image3d.html"), media_type="text/html")
