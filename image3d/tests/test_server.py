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


@pytest.fixture(autouse=True)
def clean_throttle():
    server.reset_throttle()


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
    """A fake gradio_client: checks the keyword call, token keyword fallback and the dict-shaped result."""
    import types
    glb_path = tmp_path / "out.glb"
    glb_path.write_bytes(GLB)
    calls = {}

    class Job:
        def cancel(self):
            calls["cancelled"] = calls.get("cancelled", 0) + 1
            return True

        def result(self, timeout=None):
            calls["timeout"] = timeout
            if calls.get("raise"):
                raise calls["raise"]
            return [{"value": str(glb_path), "__type__": "update"}, {"value": None}, "stats", 42]

    class Client:
        def __init__(self, space, token=None, hf_token=None):
            if new_style and hf_token is not None or not new_style and token is not None:
                raise TypeError("unexpected keyword")
            calls["space"], calls["token"] = space, token or hf_token

        def view_api(self, return_format=None):
            return {"named_endpoints": {
                "/health": {"parameters": []},
                "/image_to_shape": {"parameters": [{"component": "Image"}]}}}

        def submit(self, *args, api_name=None, **kwargs):
            calls["api_name"], calls["args"], calls["kwargs"] = api_name, args, kwargs
            return Job()

    mod = types.ModuleType("gradio_client")
    mod.Client, mod.handle_file = Client, lambda p: "FILE:" + os.path.basename(p)
    monkeypatch.setitem(sys.modules, "gradio_client", mod)
    monkeypatch.setenv("HF_TOKEN", "hf_fake")
    for v in ("HF_API_NAME", "HF_SPACE", "HF_IMAGE_PARAM", "HF_EXTRA_JSON"):
        monkeypatch.delenv(v, raising=False)
    return calls


@pytest.mark.parametrize("new_style", [True, False])
def test_generate_glb_with_fake_gradio_client(monkeypatch, tmp_path, new_style):
    calls = _fake_gradio(monkeypatch, tmp_path, new_style)
    assert server.generate_glb(PNG, "photo.png") == GLB
    assert calls == {"space": "tencent/Hunyuan3D-2", "token": "hf_fake", "api_name": "/shape_generation",
                     "args": (), "kwargs": {"image": "FILE:photo.png", "octree_resolution": 128}, "timeout": 300}


def test_timeout_cancels_the_job_and_answers_503(client, monkeypatch, tmp_path):
    calls = _fake_gradio(monkeypatch, tmp_path, True)
    calls["raise"] = TimeoutError()
    monkeypatch.setattr(server, "GENERATOR", server.generate_glb)
    r = post(client)
    assert r.status_code == 503
    assert calls["cancelled"] == 1


def test_generate_glb_image_param_and_space_from_env(monkeypatch, tmp_path):
    calls = _fake_gradio(monkeypatch, tmp_path, True)
    monkeypatch.setenv("HF_IMAGE_PARAM", "input_image")
    monkeypatch.setenv("HF_SPACE", "someone/other")
    monkeypatch.setenv("HF_API_NAME", "/gen")
    server.generate_glb(PNG, "photo.jpg")
    assert calls["kwargs"] == {"input_image": "FILE:photo.jpg"}
    assert (calls["space"], calls["api_name"]) == ("someone/other", "/gen")


def test_generate_glb_extra_settings_from_env(monkeypatch, tmp_path):
    # HF_EXTRA_JSON adds keyword settings to the Space call; the default asks Hunyuan3D-2 for a lighter mesh
    calls = _fake_gradio(monkeypatch, tmp_path, True)
    monkeypatch.setenv("HF_EXTRA_JSON", '{"octree_resolution": 96, "steps": 20}')
    server.generate_glb(PNG, "photo.png")
    assert calls["kwargs"] == {"image": "FILE:photo.png", "octree_resolution": 96, "steps": 20}
    monkeypatch.setenv("HF_EXTRA_JSON", "{}")
    server.generate_glb(PNG, "photo.png")
    assert calls["kwargs"] == {"image": "FILE:photo.png"}


def test_generate_glb_no_default_extras_for_another_space(monkeypatch, tmp_path):
    calls = _fake_gradio(monkeypatch, tmp_path, True)
    monkeypatch.setenv("HF_SPACE", "someone/other")
    monkeypatch.setenv("HF_API_NAME", "/gen")
    server.generate_glb(PNG, "photo.png")
    assert calls["kwargs"] == {"image": "FILE:photo.png"}


@pytest.mark.parametrize("bad", ["not json", "[1, 2]", '{"image": "x"}'])
def test_generate_glb_rejects_bad_extra_settings(monkeypatch, tmp_path, bad):
    _fake_gradio(monkeypatch, tmp_path, True)
    monkeypatch.setenv("HF_EXTRA_JSON", bad)
    with pytest.raises(RuntimeError, match="HF_EXTRA_JSON"):
        server.generate_glb(PNG, "photo.png")


def test_generate_glb_empty_api_name_autopicks(monkeypatch, tmp_path):
    calls = _fake_gradio(monkeypatch, tmp_path, True)
    monkeypatch.setenv("HF_API_NAME", "")
    server.generate_glb(PNG, "photo.png")
    assert calls["api_name"] == "/image_to_shape"


def test_first_glb_shapes():
    assert server._first_glb("/tmp/a/white_mesh.glb") == "/tmp/a/white_mesh.glb"
    assert server._first_glb([None, {"value": "/t/m.glb", "__type__": "update"}]) == "/t/m.glb"
    assert server._first_glb(("x", {"path": "/t/n.GLB"})) == "/t/n.GLB"
    assert server._first_glb(["/t/a.png", 3]) is None


# ---------- hardening ----------
def test_docs_disabled(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_error_detail_is_capped(client, monkeypatch):
    def boom(image, name):
        raise RuntimeError("x" * 1000)
    monkeypatch.setattr(server, "GENERATOR", boom)
    r = post(client)
    assert r.status_code == 503
    assert len(r.json()["detail"]) <= 300


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_throttle_locks_after_five_wrong_passcodes(client, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(server, "CLOCK", clock)
    for _ in range(5):
        assert post(client, passcode="nope").status_code == 401
    r = post(client, passcode="sesame")  # even the right one is refused while locked
    assert r.status_code == 429
    assert r.json()["detail"] == "too many attempts, try again later"
    clock.t += 599
    assert post(client).status_code == 429
    clock.t += 2
    assert post(client).status_code == 200


def test_throttle_correct_passcode_resets_count(client):
    for _ in range(4):
        assert post(client, passcode="nope").status_code == 401
    assert post(client).status_code == 200
    for _ in range(4):
        assert post(client, passcode="nope").status_code == 401
    assert post(client).status_code == 200


def test_throttle_old_failures_expire_and_ips_are_separate(client, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(server, "CLOCK", clock)
    for _ in range(4):
        post(client, passcode="nope")
    clock.t += 601
    assert post(client, passcode="nope").status_code == 401  # the 4 old ones no longer count
    assert post(client).status_code == 200
    for _ in range(5):
        client.post("/api/generate", headers={"X-Passcode": "nope", "X-Forwarded-For": "1.2.3.4"})
    assert client.post("/api/generate", headers={"X-Passcode": "nope", "X-Forwarded-For": "1.2.3.4"}).status_code == 429
    assert post(client).status_code == 200  # another client (the socket peer) is not locked


def test_throttle_key_is_the_last_forwarded_entry(client):
    # the first entries are client-controlled; rotating them must not dodge the limit
    for i in range(5):
        r = client.post("/api/generate", headers={"X-Passcode": "nope", "X-Forwarded-For": "6.6.6.%d, 9.9.9.9" % i})
        assert r.status_code == 401
    r = client.post("/api/generate", headers={"X-Passcode": "sesame", "X-Forwarded-For": "7.7.7.7, 9.9.9.9"})
    assert r.status_code == 429
    r = client.post("/api/generate", headers={"X-Passcode": "sesame", "X-Forwarded-For": "7.7.7.7, 8.8.8.8"})
    assert r.status_code != 429  # a different last entry is a different client


def wrong_from(client, key):
    return client.post("/api/generate", headers={"X-Passcode": "nope", "X-Forwarded-For": key})


def test_global_backstop_trips_and_clears(client, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(server, "CLOCK", clock)
    for i in range(31):
        assert wrong_from(client, "10.0.0.%d" % i).status_code == 401
    r = post(client)  # correct passcode, but too many wrong attempts overall
    assert r.status_code == 429 and r.json()["detail"] == "too many attempts, try again later"
    assert wrong_from(client, "10.9.9.9").status_code == 429
    clock.t += 599
    assert post(client).status_code == 429
    clock.t += 2
    assert post(client).status_code == 200


def test_global_count_is_not_reset_by_a_correct_passcode(client, monkeypatch):
    monkeypatch.setattr(server, "CLOCK", Clock())
    for i in range(31):
        wrong_from(client, "10.0.1.%d" % i)
        if i % 5 == 0:
            client.post("/api/generate", headers={"X-Passcode": "sesame", "X-Forwarded-For": "5.5.5.5"})
    assert post(client).status_code == 429


def test_throttle_table_is_bounded(monkeypatch):
    monkeypatch.setattr(server, "CLOCK", Clock())
    monkeypatch.setattr(server, "MAX_GLOBAL_FAILS", 10**6)  # keep the global backstop out of the way
    for i in range(1500):
        server._wrong("k%d" % i)
    assert len(server._fails) <= 1000 and len(server._locked) <= 1000
    assert "k1499" in server._fails and "k0" not in server._fails
    for i in range(1500):
        server._wrong("L%d" % (i % 3))  # three keys hammered: they lock, table stays small
    assert len(server._fails) <= 1000


def test_expired_entries_are_swept(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(server, "CLOCK", clock)
    monkeypatch.setattr(server, "MAX_GLOBAL_FAILS", 10**6)
    for i in range(50):
        server._wrong("old%d" % i)
    clock.t += 601
    server._wrong("fresh")
    assert list(server._fails) == ["fresh"]


# ---------- body limits are enforced before the body is read ----------
def run_asgi(headers, chunks, config=True):
    """Call server.app directly. Returns (status, body, number of body chunks the app pulled)."""
    import asyncio
    pulled = []
    sent = []

    async def go():
        it = iter(chunks)

        async def receive():
            pulled.append(1)
            try:
                c = next(it)
            except StopIteration:
                return {"type": "http.disconnect"}
            return {"type": "http.request", "body": c, "more_body": True}

        async def send(m):
            sent.append(m)

        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
                 "path": "/api/generate", "raw_path": b"/api/generate", "query_string": b"", "root_path": "",
                 "scheme": "http", "server": ("t", 80), "client": ("9.9.9.9", 1),
                 "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
        await server.app(scope, receive, send)

    asyncio.run(go())
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, body, len(pulled)


def test_wrong_passcode_with_huge_content_length_never_reads_body(client):
    status, body, pulled = run_asgi(
        {"content-length": str(5 * 1024**3), "content-type": "multipart/form-data; boundary=x", "x-passcode": "nope"},
        [b"x" * 1000] * 3)
    assert status == 401 and pulled == 0


def test_not_configured_never_reads_body(client, monkeypatch):
    monkeypatch.delenv("HF_TOKEN")
    status, body, pulled = run_asgi({"content-length": "999999999", "x-passcode": "sesame"}, [b"x"])
    assert status == 500 and pulled == 0 and b"server not configured" in body


def test_huge_content_length_with_right_passcode_is_413_without_reading(client):
    status, body, pulled = run_asgi(
        {"content-length": str(5 * 1024**3), "content-type": "multipart/form-data; boundary=x", "x-passcode": "sesame"},
        [b"x" * 1000])
    assert status == 413 and pulled == 0


def test_chunked_body_over_cap_stops_early(client):
    chunk = b"x" * 65536
    total_chunks = 400  # 25 MB offered, no Content-Length
    status, body, pulled = run_asgi(
        {"content-type": "multipart/form-data; boundary=x", "x-passcode": "sesame"}, [chunk] * total_chunks)
    assert status == 413
    assert pulled < total_chunks // 2


def test_chunked_body_over_cap_via_client(client):
    def gen():
        for _ in range(200):
            yield b"x" * 65536
    r = client.post("/api/generate", content=gen(),
                    headers={"X-Passcode": "sesame", "Content-Type": "multipart/form-data; boundary=x"})
    assert r.status_code == 413
