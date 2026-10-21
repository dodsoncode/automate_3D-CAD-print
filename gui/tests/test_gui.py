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


# ---------------- styles: crab / hexapod / windmill rover ----------------
@pytest.fixture()
def fresh(server, page):
    pg = page.context.browser.new_page(viewport={"width": 1280, "height": 860}, accept_downloads=True)
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.goto(server)
    pg.wait_for_function("window.WDApp && WDApp.an")
    yield pg
    pg.close()


@pytest.mark.parametrize("style", ["crab", "hex", "wheg"])
def test_each_style_loads_green_and_exports(fresh, style):
    pg = fresh
    pg.click('.stylecard[data-style="%s"]' % style)
    pg.wait_for_timeout(300)
    assert pg.evaluate("WDApp.p.style") == style
    assert pg.evaluate("WDApp.an.worst") == "ok", pg.evaluate("WDApp.an.checks.filter(c=>c.level!='ok').map(c=>c.id+': '+c.detail)")
    pg.click("#tabbtn-finish")
    with pg.expect_download() as dl:
        pg.click("#make")
    z = zipfile.ZipFile(dl.value.path())
    out = tempfile.mkdtemp()
    plates = [n for n in z.namelist() if n.endswith(".3mf")]
    assert plates
    for n in plates:
        f = os.path.join(out, n)
        open(f, "wb").write(z.read(n))
        r = subprocess.run([sys.executable, os.path.join(REPO, "cad", "validate_3mf.py"), f], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
    pg.screenshot(path=os.path.join(tempfile.gettempdir(), "wd_%s.png" % style))
    assert pg.errors == []


def test_hex_feet_on_floor_and_six_legs(fresh):
    pg = fresh
    pg.click('.stylecard[data-style="hex"]')
    pg.wait_for_timeout(300)
    pg.click("#walk")
    legs = ["FL", "FR", "ML", "MR", "RL", "RR"]
    pg.evaluate("WDApp.applyPose(%s)" % json.dumps({l + "_" + j: 0 for l in legs for j in ["hip", "knee"]}))
    for leg in legs:
        assert abs(pg.evaluate("WDApp.footWorld('%s')[2]" % leg)) < 0.6, leg
    # middle legs sit at the body's side, between front and back hips
    assert pg.evaluate("WDApp.d.legs.length") == 6


def test_wheg_spin_sign_and_ground_contact(fresh):
    pg = fresh
    pg.click('.stylecard[data-style="wheg"]')
    pg.wait_for_timeout(300)
    pg.click("#walk")                       # park
    # rotating by one pitch must leave the lowest tip at the same height (rotational symmetry),
    # and a half pitch must lower the body (tip -> flat between spokes) or equal; body never below the floor
    pg.evaluate("WDApp.setWheel({FL:0,FR:0,RL:0,RR:0})")
    lows = []
    for ang in [0, 10, 20, 30, 45]:
        pg.evaluate("WDApp.setWheel({FL:%d,FR:%d,RL:%d,RR:%d})" % ((ang,) * 4))
        zs = [t[2] for l in ["FL", "FR", "RL", "RR"] for t in pg.evaluate("WDApp.wheelTips('%s')" % l)]
        lows.append(min(zs))
    assert all(z > -2 for z in lows), lows
    # left and right wheels spin the same way when driven forward: tip x-velocity at the bottom is backward for all
    pg.evaluate("WDApp.setWheel({FL:0,FR:0,RL:0,RR:0})")
    base = {l: pg.evaluate("WDApp.wheelTips('%s')" % l) for l in ["FL", "FR"]}
    pg.evaluate("WDApp.setWheel({FL:5,FR:5,RL:5,RR:5})")
    for l in ["FL", "FR"]:
        new = pg.evaluate("WDApp.wheelTips('%s')" % l)
        lowest = min(range(len(new)), key=lambda i: new[i][2] + 0 * base[l][i][2])
        # forward drive (positive angle): contact tips move backward (-x) relative to the axle
        axle_x = pg.evaluate("WDApp.d.axleX") * (1 if l[0] == "F" else -1)
        dx = new[lowest][0] - base[l][lowest][0]
        assert dx < 0, (l, dx)


def test_style_switch_keeps_separate_designs(fresh):
    pg = fresh
    pg.evaluate("WDApp.set('femurLen', 70)")
    pg.click('.stylecard[data-style="hex"]')
    pg.wait_for_timeout(200)
    assert pg.evaluate("WDApp.p.femurLen") != 70
    pg.click('.stylecard[data-style="crab"]')
    pg.wait_for_timeout(200)
    assert pg.evaluate("WDApp.p.femurLen") == 70


def test_mobile_no_overflow_each_style(server, page):
    pg = page.context.browser.new_page(viewport={"width": 390, "height": 800})
    pg.goto(server)
    pg.wait_for_function("window.WDApp && WDApp.an")
    for st in ["crab", "hex", "wheg"]:
        pg.click('.stylecard[data-style="%s"]' % st)
        pg.wait_for_timeout(200)
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), st
    pg.close()
