"""Image3D service for Render: serves the editor page and turns a photo into a GLB via a Hugging Face Space.

  uvicorn server:app --host 0.0.0.0 --port $PORT

Env: HF_TOKEN (Hugging Face read token), IMAGE3D_PASSCODE (shared passcode),
     HF_SPACE (default tencent/Hunyuan3D-2.1), HF_API_NAME (default empty = auto-pick the endpoint).
Everything is read per request, so the tests can set it with monkeypatch.
"""
import hmac
import os
import tempfile

from fastapi import FastAPI, File, Header, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

HERE = os.path.dirname(os.path.abspath(__file__))
HF_SPACE = os.environ.get("HF_SPACE") or "tencent/Hunyuan3D-2.1"
MAX_BYTES = 10 * 1024 * 1024
TIMEOUT_S = 300

app = FastAPI(title="Image3D")


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


def generate_glb(image_bytes, filename):
    """Photo bytes -> GLB bytes through the Hugging Face Space. NOT verified against the live Space."""
    from gradio_client import Client, handle_file  # lazy: tests and import must work without it

    token = os.environ.get("HF_TOKEN")
    space = os.environ.get("HF_SPACE") or HF_SPACE
    try:
        client = Client(space, token=token)
    except TypeError:  # older gradio_client versions call the argument hf_token
        client = Client(space, hf_token=token)
    api_name = os.environ.get("HF_API_NAME") or _pick_endpoint(client)
    suffix = os.path.splitext(filename or "")[1] or ".png"
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "photo" + suffix)
        with open(path, "wb") as f:
            f.write(image_bytes)
        result = client.submit(handle_file(path), api_name=api_name).result(timeout=TIMEOUT_S)
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
async def generate(image: UploadFile = File(...), x_passcode: str = Header(default="")):
    passcode, token = os.environ.get("IMAGE3D_PASSCODE"), os.environ.get("HF_TOKEN")
    if not passcode or not token:
        return _fail(500, "server not configured")
    if not hmac.compare_digest(x_passcode.encode("utf-8"), passcode.encode("utf-8")):
        return _fail(401, "wrong passcode")
    if not (image.content_type or "").startswith("image/"):
        return _fail(400, "that file is not an image")
    data = await image.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        return _fail(413, "image is too large (10 MB limit)")
    try:
        glb = await run_in_threadpool(GENERATOR, data, image.filename or "photo.png")
    except Exception as e:  # Space busy, quota, asleep, timeout ...
        return _fail(503, "generation failed: %s" % (str(e) or e.__class__.__name__))
    return Response(glb, media_type="model/gltf-binary")


@app.get("/")
def root():
    return FileResponse(os.path.join(HERE, "image3d.html"), media_type="text/html")
