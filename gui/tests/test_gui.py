"""Browser test of the Walker Designer (Playwright + Chromium). Run: python -m pytest -q gui/tests/test_gui.py"""
import functools, http.server, io, json, os, subprocess, sys, tempfile, threading, zipfile
import pytest

pw = pytest.importorskip("playwright.sync_api")
GUI = os.path.join(os.path.dirname(__file__), "..")
REPO = os.path.join(GUI, "..")


@pytest.fixture(scope="module")
def server():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=GUI)
    h.log_message = lambda *a, **k: None
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d/index.html" % s.server_address[1]
    s.shutdown()


@pytest.fixture(scope="module")
def page(server):
    with pw.sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        ctx = b.new_context(viewport={"width": 1280, "height": 860}, accept_downloads=True)
        pg = ctx.new_page()
        pg.errors = []
        pg.on("pageerror", lambda e: pg.errors.append(str(e)))
        pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" and "fonts" not in m.text and "ERR_" not in m.text and "Failed to load resource" not in m.text else None)
        pg.goto(server)
        pg.wait_for_function("window.WDApp && WDApp.an")
        yield pg
        b.close()


def test_loads_clean_and_all_green(page):
    assert page.errors == []
    assert page.evaluate("WDApp.an.worst") == "ok"
    assert page.locator("#status").inner_text().strip() == "All checks green"
    page.screenshot(path=os.path.join(tempfile.gettempdir(), "wd_default.png"))


def test_feet_on_floor_and_hip_sign(page):
    page.click("#walk")                    # stop the animation so the test controls the pose
    page.evaluate("WDApp.applyPose({FL_hip:0,FL_knee:0,FR_hip:0,FR_knee:0,RL_hip:0,RL_knee:0,RR_hip:0,RR_knee:0})")
    for leg in ["FL", "FR", "RL", "RR"]:
        z = page.evaluate("WDApp.footWorld('%s')[2]" % leg)
        assert abs(z) < 0.6, (leg, z)
    for leg in ["FL", "FR", "RL", "RR"]:      # +hip moves every foot toward the front (+x)
        x0 = page.evaluate("WDApp.footWorld('%s')[0]" % leg)
        pose = {l + "_" + j: 0 for l in ["FL", "FR", "RL", "RR"] for j in ["hip", "knee"]}
        pose[leg + "_hip"] = 15
        page.evaluate("WDApp.applyPose(%s)" % json.dumps(pose))
        x1 = page.evaluate("WDApp.footWorld('%s')[0]" % leg)
        assert x1 > x0 + 3, (leg, x0, x1)
    # knee + lifts the foot
    pose = {l + "_" + j: 0 for l in ["FL", "FR", "RL", "RR"] for j in ["hip", "knee"]}
    pose["FR_knee"] = 20
    page.evaluate("WDApp.applyPose(%s)" % json.dumps(pose))
    assert page.evaluate("WDApp.footWorld('FR')[2]") > 5
    page.click("#walk")


def test_slider_changes_design_and_checks(page):
    page.click("#tabbtn-legs")
    before = page.evaluate("WDApp.d.standH")
    page.evaluate("(()=>{const e=document.getElementById('sl-femurLen');e.value=80;e.dispatchEvent(new Event('input',{bubbles:true}))})()")
    page.wait_for_timeout(150)
    assert page.evaluate("WDApp.d.standH") > before + 5
    assert page.evaluate("WDApp.p.femurLen") == 80
    page.evaluate("WDApp.set('femurLen',55)")


def test_presets_and_modes(page):
    page.click("text=Tiny crab")
    page.wait_for_timeout(150)
    assert page.evaluate("WDApp.p.legSplay") == 70
    page.click("text=Print plates")
    page.wait_for_timeout(100)
    page.screenshot(path=os.path.join(tempfile.gettempdir(), "wd_plates.png"))
    page.click("text=Robot")
    page.click("text=Starter walker")
    page.wait_for_timeout(150)
    assert page.evaluate("WDApp.an.worst") in ("ok", "warn")


def test_export_zip_validates(page):
    page.click("#tabbtn-finish")
    with page.expect_download() as dl:
        page.click("#make")
    path = dl.value.path()
    z = zipfile.ZipFile(path)
    names = z.namelist()
    assert "walker_design.json" in names and "robot_settings.txt" in names
    plates = [n for n in names if n.endswith(".3mf")]
    assert plates
    out = tempfile.mkdtemp()
    for n in plates:
        f = os.path.join(out, n)
        open(f, "wb").write(z.read(n))
        r = subprocess.run([sys.executable, os.path.join(REPO, "cad", "validate_3mf.py"), f], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


def test_mobile_layout_no_sideways_scroll(server, page):
    pg = page.context.browser.new_page(viewport={"width": 390, "height": 800})
    pg.goto(server)
    pg.wait_for_function("window.WDApp && WDApp.an")
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    pg.screenshot(path=os.path.join(tempfile.gettempdir(), "wd_mobile.png"))
    pg.close()
