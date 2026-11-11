"""Browser tests of the Image3D editor at phone size (Playwright + Chromium).
Run: python -m pytest -q image3d/tests/test_page.py"""
import functools
import http.server
import json
import os
import subprocess
import sys
import threading

import pytest

pw = pytest.importorskip("playwright.sync_api")
HERE = os.path.dirname(os.path.abspath(__file__))
I3D = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(I3D, ".."))
SAMPLES = os.path.join(HERE, "samples")
IGNORED = ("Failed to load resource", "ERR_")


@pytest.fixture(scope="module")
def server():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=REPO)
    h.log_message = lambda *a, **k: None
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d/image3d/index.html" % s.server_address[1]
    s.shutdown()


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        yield b
        b.close()


def new_page(browser, url, init=None):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, accept_downloads=True)
    pg = ctx.new_page()
    if init:
        pg.add_init_script(init)
    pg.set_default_timeout(8000)
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" and not any(i in m.text for i in IGNORED) else None)
    pg.goto(url)
    pg.wait_for_function("window.I3DApp")
    pg.evaluate("I3DApp.ready")
    return pg


@pytest.fixture
def page(browser, server):
    pg = new_page(browser, server)
    yield pg
    pg.context.close()


def open_sample(pg, name, rows=None):
    pg.set_input_files("#file", os.path.join(SAMPLES, name))
    pg.wait_for_function("I3DApp.state.model.length > 0")
    if rows is not None:
        pg.wait_for_function("document.querySelectorAll('#pieces [data-i]').length === %d" % rows)


def rows(pg):
    return pg.locator("#pieces [data-i]").count()


def test_loads_without_errors(page):
    assert page.errors == []
    assert page.evaluate("typeof I3DApp") == "object"
    assert page.evaluate("I3DApp.serverMode") is False
    assert not page.locator("#gen-panel").is_visible()
    assert page.locator("#howto").is_visible()
    assert "huggingface.co/spaces/tencent/Hunyuan3D-2.1" in page.locator("#howto").inner_html()
    assert "huggingface.co/spaces/trellis-community/TRELLIS" in page.locator("#howto").inner_html()


def test_open_two_cubes_and_delete(page):
    open_sample(page, "two_cubes.stl", rows=2)
    page.locator("#pieces [data-i]").nth(1).tap()
    page.locator("#btn-delete").tap()
    assert rows(page) == 1
    assert page.errors == []


def test_open_scales_to_100mm(page):
    open_sample(page, "unit_box.glb", rows=1)
    size = page.evaluate("I3D.mesh.bbox(I3DApp.state.model).size")
    assert max(size) == pytest.approx(100, abs=1e-3)
    assert "100 mm" in page.locator("#msg").inner_text()


def test_size_cut_export(page):
    open_sample(page, "two_cubes.stl", rows=2)
    page.locator("#btn-keep-largest").tap()
    page.wait_for_function("document.querySelectorAll('#pieces [data-i]').length === 1")
    page.fill("#size-mm", "60")
    page.locator("#btn-size").tap()
    page.select_option("#cut-axis", "z")
    page.evaluate("(()=>{const r=document.getElementById('cut-pos');r.value=30;r.dispatchEvent(new Event('input',{bubbles:true}));})()")
    page.select_option("#cut-keep", "below")
    page.locator("#btn-cut").tap()
    res = page.evaluate("""(() => {
      const b = I3DApp.exportStl(), soup = I3D.stl.read(b), m = I3D.mesh;
      const shells = m.split(m.weld(soup));
      return {n: shells.length, closed: shells.every(m.isClosed), bb: m.bbox(shells)};
    })()""")
    assert res["n"] == 1 and res["closed"]
    assert res["bb"]["min"][2] == pytest.approx(0, abs=1e-3)
    assert res["bb"]["max"][2] == pytest.approx(30, abs=1e-3)
    with page.expect_download() as d:
        page.locator("#btn-export").tap()
    assert d.value.suggested_filename == "model.stl"
    assert page.errors == []


def test_undo_restores(page):
    open_sample(page, "two_cubes.stl", rows=2)
    page.locator("#pieces [data-i]").nth(1).tap()
    page.locator("#btn-delete").tap()
    assert rows(page) == 1
    page.locator("#btn-undo").tap()
    assert rows(page) == 2


def test_bad_file_leaves_model_unchanged(page, tmp_path):
    open_sample(page, "two_cubes.stl", rows=2)
    bad = tmp_path / "bad.glb"
    bad.write_bytes(b"not a glb at all")
    page.set_input_files("#file", str(bad))
    page.wait_for_function("document.getElementById('msg').innerText.trim() !== ''")
    assert rows(page) == 2
    assert page.evaluate("I3DApp.state.model.length") == 2
    assert "glb" in page.locator("#msg").inner_text().lower()


def test_touch_targets(page):
    heights = page.evaluate("""[...document.querySelectorAll('button, select, input[type=range], input[type=file]')]
      .filter(e => e.getBoundingClientRect().height > 0)
      .map(e => [e.id || e.tagName, e.getBoundingClientRect().height])""")
    assert heights
    small = [h for h in heights if h[1] < 44]
    assert small == []
    open_sample(page, "two_cubes.stl", rows=2)
    small = page.evaluate("""[...document.querySelectorAll('#pieces button')].map(e => e.getBoundingClientRect().height).filter(h => h < 44)""")
    assert small == []
    assert page.evaluate("document.documentElement.scrollWidth") <= 390


def test_built_single_file(browser, tmp_path):
    subprocess.run([sys.executable, os.path.join(I3D, "build.py")], check=True, cwd=str(tmp_path), capture_output=True)
    out = os.path.join(I3D, "image3d.html")
    html = open(out, encoding="utf-8").read()
    assert "<script src" not in html and "<title>Image3D editor</title>" in html
    pg = new_page(browser, "file://" + out)
    assert pg.errors == []
    open_sample(pg, "two_cubes.glb", rows=2)
    assert pg.errors == []
    pg.context.close()


FAKE_SAVE = """window.claude = {use: async (n) => ({save: async (a) => { window.__saved = a; return {status: 'saved'}; }})};"""
FAKE_DECLINE = """window.claude = {use: async (n) => ({save: async (a) => { throw {code: 'declined', message: 'no'}; }})};"""
FAKE_NULL = """window.claude = {use: async (n) => null};"""


def prep_cube(pg):
    open_sample(pg, "two_cubes.stl", rows=2)
    pg.locator("#btn-keep-largest").tap()
    pg.wait_for_function("document.querySelectorAll('#pieces [data-i]').length === 1")


def test_export_via_artifact_downloads_zip(browser, server):
    pg = new_page(browser, server, FAKE_SAVE)
    prep_cube(pg)
    pg.locator("#btn-export").tap()
    pg.wait_for_function("window.__saved")
    res = pg.evaluate("""(async () => {
      const a = window.__saved, z = await JSZip.loadAsync(a.data), names = Object.keys(z.files);
      const bytes = await z.files['model.stl'].async('uint8array'), m = I3D.mesh;
      const shells = m.split(m.weld(I3D.stl.read(bytes)));
      return {filename: a.filename, names, closed: shells.length === 1 && shells.every(m.isClosed)};
    })()""")
    assert res == {"filename": "model.zip", "names": ["model.stl"], "closed": True}
    assert "Saved model.zip (contains model.stl)" in pg.locator("#msg").inner_text()
    assert pg.errors == []
    pg.context.close()


def test_export_declined_shows_cancelled_without_fallback(browser, server):
    pg = new_page(browser, server, FAKE_DECLINE)
    prep_cube(pg)
    downloads = []
    pg.on("download", lambda d: downloads.append(d))
    pg.locator("#btn-export").tap()
    pg.wait_for_function("document.getElementById('msg').innerText.includes('Download cancelled')")
    pg.wait_for_timeout(500)
    assert downloads == []
    pg.context.close()


def test_export_falls_back_when_downloads_unavailable(browser, server):
    pg = new_page(browser, server, FAKE_NULL)
    prep_cube(pg)
    with pg.expect_download() as d:
        pg.locator("#btn-export").tap()
    assert d.value.suggested_filename == "model.stl"
    pg.context.close()


def test_cut_preview_only_while_cutting(page):
    open_sample(page, "two_cubes.stl", rows=2)
    assert page.evaluate("I3DApp.cutPreviewVisible()") is False
    page.evaluate("(()=>{const r=document.getElementById('cut-pos');r.value=r.min;r.dispatchEvent(new Event('input',{bubbles:true}));})()")
    assert page.evaluate("I3DApp.cutPreviewVisible()") is True
    page.locator("#btn-cut").tap()
    assert page.evaluate("I3DApp.cutPreviewVisible()") is False
    page.select_option("#cut-keep", "below")
    assert page.evaluate("I3DApp.cutPreviewVisible()") is True
    page.locator("#btn-flat").tap()
    assert page.evaluate("I3DApp.cutPreviewVisible()") is False


def test_size_field_shows_current_size(page):
    open_sample(page, "two_cubes.stl", rows=2)
    longest = page.evaluate("Math.max(...I3D.mesh.bbox(I3DApp.state.model).size)")
    assert float(page.input_value("#size-mm")) == pytest.approx(round(longest, 1), abs=1e-9)
    page.fill("#size-mm", "60")
    page.locator("#btn-size").tap()
    assert float(page.input_value("#size-mm")) == pytest.approx(60)


def test_view_stays_in_viewport_when_tools_scroll(page):
    open_sample(page, "two_cubes.stl", rows=2)
    page.locator("#btn-export").scroll_into_view_if_needed()
    box = page.evaluate("(()=>{const r=document.querySelector('#view canvas').getBoundingClientRect();return [r.top,r.bottom,innerHeight];})()")
    assert box[0] >= 0 and box[1] <= box[2] and box[1] - box[0] > 100
