"""Tests of the Render service (server.py) with a FAKE generator; no network, no Hugging Face.
Test-only needs (not in requirements.txt): httpx (FastAPI TestClient).
Run: python -m pytest -q image3d/tests/test_server.py"""
import os
import sys

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
I3D = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, I3D)
import server  # noqa: E402

with open(os.path.join(HERE, "samples", "two_cubes.glb"), "rb") as f:
    GLB = f.read()
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("IMAGE3D_PASSCODE", "sesame")
    monkeypatch.setenv("HF_TOKEN", "hf_fake")
    monkeypatch.setattr(server, "GENERATOR", lambda image, name: GLB)
    return TestClient(server.app)


def post(client, passcode="sesame", data=PNG, ctype="image/png"):
    headers = {} if passcode is None else {"X-Passcode": passcode}
    return client.post("/api/generate", files={"image": ("photo.png", data, ctype)}, headers=headers)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "space": server.HF_SPACE}


def test_root_serves_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "I3DApp" in r.text


def test_generate_ok(client):
    r = post(client)
    assert r.status_code == 200
    assert r.headers["content-type"] == "model/gltf-binary"
    assert r.content.startswith(b"glTF")


def test_generate_wrong_passcode(client):
    assert post(client, passcode="nope").status_code == 401


def test_generate_missing_passcode(client):
    assert post(client, passcode=None).status_code == 401


def test_generate_not_image(client):
    r = post(client, data=b"hello", ctype="text/plain")
    assert r.status_code == 400
    assert "image" in r.json()["detail"]


def test_generate_too_large(client):
    assert post(client, data=b"\0" * (11 * 1024 * 1024)).status_code == 413


def test_generate_space_busy(client, monkeypatch):
    def boom(image, name):
        raise RuntimeError("You have exceeded your GPU quota")
    monkeypatch.setattr(server, "GENERATOR", boom)
    r = post(client)
    assert r.status_code == 503
    assert "quota" in r.json()["detail"]


@pytest.mark.parametrize("var", ["IMAGE3D_PASSCODE", "HF_TOKEN"])
def test_not_configured(client, monkeypatch, var):
    monkeypatch.delenv(var)
    r = post(client)
    assert r.status_code == 500
    assert "server not configured" in r.json()["detail"]


def test_not_configured_beats_wrong_passcode(client, monkeypatch):
    monkeypatch.delenv("HF_TOKEN")
    assert post(client, passcode="nope").status_code == 500


def test_wrong_passcode_beats_bad_image(client):
    assert post(client, passcode="nope", data=b"x", ctype="text/plain").status_code == 401


def _fake_gradio(monkeypatch, tmp_path, new_style):
    """A fake gradio_client: checks endpoint auto-pick, token keyword fallback and .glb extraction."""
    import types
    glb_path = tmp_path / "out.glb"
    glb_path.write_bytes(GLB)
    calls = {}

    class Job:
        def result(self, timeout=None):
            calls["timeout"] = timeout
            return [{"value": "x.png"}, ("meta", {"path": str(glb_path)})]

    class Client:
        def __init__(self, space, token=None, hf_token=None):
            if new_style and hf_token is not None or not new_style and token is not None:
                raise TypeError("unexpected keyword")
            calls["token"] = token or hf_token

        def view_api(self, return_format=None):
            return {"named_endpoints": {
                "/health": {"parameters": []},
                "/image_to_shape": {"parameters": [{"component": "Image"}]}}}

        def submit(self, arg, api_name=None):
            calls["api_name"] = api_name
            return Job()

    mod = types.ModuleType("gradio_client")
    mod.Client, mod.handle_file = Client, lambda p: p
    monkeypatch.setitem(sys.modules, "gradio_client", mod)
    monkeypatch.setenv("HF_TOKEN", "hf_fake")
    monkeypatch.delenv("HF_API_NAME", raising=False)
    return calls


@pytest.mark.parametrize("new_style", [True, False])
def test_generate_glb_with_fake_gradio_client(monkeypatch, tmp_path, new_style):
    calls = _fake_gradio(monkeypatch, tmp_path, new_style)
    out = server.generate_glb(PNG, "photo.png")
    assert out == GLB
    assert calls == {"token": "hf_fake", "api_name": "/image_to_shape", "timeout": 300}
