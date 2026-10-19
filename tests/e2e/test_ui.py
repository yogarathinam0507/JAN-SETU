"""Browser end-to-end tests (Playwright + Chromium). They start their own server on a separate, freshly
seeded database. Skipped automatically if Playwright/Chromium is unavailable."""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e
pw = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def server():
    tmp = Path(tempfile.mkdtemp(prefix="jansetu-e2e-"))
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp / 'e2e.db'}", "UPLOAD_DIR": str(tmp / "up"),
           "ENABLE_BACKGROUND_JOBS": "false", "SECRET_KEY": "e2e-secret-0123456789abcdef0123456789",
           "RATE_LIMIT_PER_MINUTE": "100000", "AUTH_RATE_LIMIT_PER_MINUTE": "100000", "PUBLIC_BASE_URL": ""}
    backend = ROOT / "backend"
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=backend, env=env, check=True, capture_output=True)
    subprocess.run([sys.executable, "-m", "app.seed"], cwd=backend, env=env, check=True, capture_output=True)
    port = _free_port()
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)], cwd=backend, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            import httpx
            if httpx.get(base + "/api/health", timeout=1).status_code == 200:
                break
        except Exception:  # noqa: BLE001
            time.sleep(0.25)
    yield base
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Chromium not available: {exc}")
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    # Map tiles come from an external tile server that may be unreachable in CI; those load errors are expected.
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    yield pg
    ctx.close()
    assert not errors, errors


def set_lang(page, code):
    page.select_option("#lang-select", code)
    page.wait_for_timeout(500)


def login_demo(page, base, username, add=False):
    page.goto(base + ("/login?add=1" if add else "/login"))
    page.wait_for_selector(".test-accounts summary")
    page.click(".test-accounts summary")
    page.locator(f".test-accounts td:text-is('{username}')").click()
    page.wait_for_function("() => location.pathname === '/dashboard'")
    page.wait_for_selector(".kpi-grid")


def test_site_opens_on_sign_in_page_and_guards_every_page(page, server):
    for path in ["/", "/citizen", "/officer", "/map", "/dashboard"]:
        page.goto(server + path)
        page.wait_for_selector("#login-h")
        assert page.url.startswith(server + "/login")
    # public policy pages stay readable without signing in
    page.goto(server + "/accessibility")
    page.wait_for_selector("#app h1")
    assert "Accessibility" in page.locator("#app h1").inner_text()


def test_no_emoji_or_demo_wording_on_login_page(page, server):
    page.goto(server + "/login")
    page.wait_for_selector("#login-h")
    text = page.locator("body").inner_text()
    import re
    assert not re.search("[\U0001F300-\U0001FAFF\u2600-\u27BF]", text)
    for word in ("demo", "Demo", "PS1", "PS 1", "rule-based", "Rule-based"):
        assert word not in text


def test_staff_password_login_lands_on_dashboard(page, server):
    page.goto(server + "/login")
    page.click("button[role=tab]:has-text('Department login')")
    page.fill("#staff-user", "ka.officer.water")
    page.fill("#staff-pass", "Demo@1234")
    page.click("#staff-form button[type=submit]")
    page.wait_for_selector(".kpi-grid")
    assert page.url.endswith("/dashboard")
    assert "Smt. Kavya Shetty" in page.locator(".account-btn").inner_text()
    assert page.locator(".kpi").count() >= 6
    page.reload()  # session survives a reload (no "session expired")
    page.wait_for_selector(".kpi-grid")
    assert "Smt. Kavya Shetty" in page.locator(".account-btn").inner_text()


@pytest.mark.parametrize("username", ["ka.citizen1", "ka.nodal", "ka.agent1", "ka.hod", "ka.vendor", "ka.auditor", "ka.content", "ka.admin"])
def test_every_role_has_a_dashboard(page, server, username):
    login_demo(page, server, username)
    assert page.locator(".kpi").count() >= 4
    assert page.locator("#nav a").count() >= 2


def test_citizen_otp_login(page, server):
    page.goto(server + "/login")
    page.fill("input[autocomplete=tel]", "9123400009")
    page.click("button:has-text('Send code')")
    page.wait_for_selector("button:has-text('Verify and sign in')")
    page.click("button:has-text('Verify and sign in')")
    page.wait_for_selector(".kpi-grid")


def test_routing_panel_empty_before_input(page, server):
    login_demo(page, server, "ka.citizen2")
    page.goto(server + "/citizen")
    panel = page.locator("aside.card")
    panel.wait_for()
    text = panel.inner_text()
    assert "Routing details appear here" in text
    for leaked in ("Streetlight", "Rule", "rule-based", "Medium", "Department"):
        assert leaked not in text


def test_citizen_files_complaint_sees_assigned_officer_and_officer_sees_it(page, server, browser):
    login_demo(page, server, "ka.citizen2")
    page.goto(server + "/citizen")
    page.fill("textarea", "Dirty water from the tap in Indiranagar since yesterday")
    page.click("button:has-text('Continue')")
    page.wait_for_selector("text=Confirm language and text")
    assert "Water Supply" in page.locator("aside.card").inner_text()
    page.click("button:has-text('Continue')")
    page.wait_for_selector("text=Where will this go?")
    assert "BWSSB" in page.locator("#app").inner_text()
    page.click("button:has-text('Continue')")
    page.check("input[type=checkbox]")
    page.click("button:has-text('Submit complaint')")
    page.wait_for_selector("text=Complaint registered")
    notice = page.locator(".assign-notice").inner_text()
    assert "Smt. Kavya Shetty" in notice and "Assistant Executive Engineer (Water Supply)" in notice
    ticket = page.locator("p.mono").first.inner_text().strip()
    assert ticket.startswith("GRV-")
    ctx = browser.new_context()
    off = ctx.new_page()
    login_demo(off, server, "ka.officer.water")
    off.goto(server + "/officer")
    off.wait_for_selector("table tbody tr")
    assert ticket in off.locator("table").inner_text()
    off.click(f"tr:has-text('{ticket}')")
    off.wait_for_selector(f"h2:has-text('{ticket}')")
    assert "******0002" in off.locator("#app").inner_text()  # phone masked for staff
    off.click("[aria-label=Notifications]")
    off.wait_for_selector(".notif-menu")
    assert ticket in off.locator(".notif-menu").inner_text()
    ctx.close()


def test_human_review_for_unclear_complaint(page, server):
    login_demo(page, server, "ka.citizen2")
    page.goto(server + "/citizen")
    page.fill("textarea", "asdkj qwe zzkx plmnb")
    page.click("button:has-text('Continue')")
    page.wait_for_selector("text=Confirm language and text")
    page.click("button:has-text('Continue')")
    page.wait_for_selector("text=A human officer will route this complaint.")


def test_language_switch_changes_interface_and_rtl(page, server):
    login_demo(page, server, "ka.citizen1")
    page.goto(server + "/citizen")
    set_lang(page, "hi")
    assert page.locator("#app h1").inner_text() == "शिकायत दर्ज करें"
    set_lang(page, "kn")
    assert page.locator("#app h1").inner_text() == "ದೂರು ನೀಡಿ"
    set_lang(page, "ur")
    assert page.evaluate("document.documentElement.dir") == "rtl"
    set_lang(page, "en")


def test_officer_table_loads_rows(page, server):
    login_demo(page, server, "ka.nodal")
    page.goto(server + "/officer")
    page.wait_for_selector("table tbody tr")
    assert page.locator("table tbody tr").count() > 3


def test_analytics_filters_change_data(page, server):
    login_demo(page, server, "ka.hod")
    page.goto(server + "/analytics")
    page.wait_for_selector(".kpi .v")
    total_30 = page.locator(".kpi .v").first.inner_text()
    page.click("button:has-text('7 days')")
    page.wait_for_timeout(800)
    total_7 = page.locator(".kpi .v").first.inner_text()
    assert int(total_7) < int(total_30)


def test_monitoring_labels_synthetic_probes(page, server):
    login_demo(page, server, "ka.admin")
    page.goto(server + "/monitoring")
    page.wait_for_selector("table")
    body = page.locator("#app").inner_text()
    assert "Synthetic probe (test data)" in body and "Planned - not monitored" in body and "Real (this application)" in body


@pytest.mark.parametrize("path", ["/login", "/dashboard", "/citizen", "/citizen/tickets", "/benefits"])
def test_mobile_layout_has_no_horizontal_scroll(browser, server, path):
    ctx = browser.new_context(viewport={"width": 375, "height": 800}, is_mobile=True)
    pg = ctx.new_page()
    if path != "/login":
        login_demo(pg, server, "ka.citizen1")
    pg.goto(server + path)
    pg.wait_for_timeout(900)
    overflow = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    ctx.close()
    assert overflow <= 1, f"{path} overflows by {overflow}px"


def test_theme_toggle_light_dark_and_persists(page, server):
    page.goto(server + "/login")
    page.wait_for_selector("#theme-toggle")
    seen = set()
    for _ in range(3):
        page.click("#theme-toggle")
        page.wait_for_timeout(150)
        seen.add((page.evaluate("document.documentElement.dataset.themePref"), page.evaluate("document.documentElement.dataset.theme")))
    assert {p for p, _ in seen} == {"system", "light", "dark"}
    assert ("dark", "dark") in seen and ("light", "light") in seen
    while page.evaluate("document.documentElement.dataset.themePref") != "dark":
        page.click("#theme-toggle")
    page.reload()
    page.wait_for_selector("#login-h")
    assert page.evaluate("document.documentElement.dataset.theme") == "dark"
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(14, 20, 28)"


def test_text_size_buttons(page, server):
    page.goto(server + "/login")
    page.wait_for_selector("#font-lg")
    page.click("#font-lg")
    assert page.evaluate("getComputedStyle(document.documentElement).fontSize") == "18px"
    page.click("#font-md")
    assert page.evaluate("getComputedStyle(document.documentElement).fontSize") == "16px"


def test_multi_account_switch_and_sign_out(page, server):
    login_demo(page, server, "ka.citizen1")
    login_demo(page, server, "ka.nodal", add=True)
    page.click(".account-btn")
    assert page.locator(".account-menu .acct").count() == 2
    page.click(".account-menu .acct:has-text('Lakshmi')")
    page.wait_for_selector(".kpi-grid")
    assert "Lakshmi" in page.locator(".account-btn").inner_text()
    page.click(".account-btn")
    page.click(".account-menu .menu-item:has-text('Sign out of all accounts')")
    page.wait_for_selector("#login-h")
    assert page.locator(".account-btn").count() == 0


def test_live_map_shows_pins_and_team_sharing(page, server):
    login_demo(page, server, "ka.nodal")
    page.goto(server + "/map")
    page.wait_for_selector(".leaflet-container")
    page.wait_for_function("document.querySelectorAll('path.leaflet-interactive').length > 3")
    page.click("button:has-text('Set on map')")
    box = page.locator("#live-map").bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_selector(".team-pin", timeout=15000)
    assert "Sharing position set on map" in page.locator("#app").inner_text()
    page.click("button:has-text('Stop sharing')")
    page.wait_for_timeout(300)


def test_citizen_map_pin_from_gps(browser, server):
    ctx = browser.new_context(geolocation={"latitude": 12.9352, "longitude": 77.6245}, permissions=["geolocation"])
    pg = ctx.new_page()
    login_demo(pg, server, "ka.citizen1")
    pg.goto(server + "/citizen")
    pg.wait_for_selector(".leaflet-container")
    pg.click("button:has-text('Use my location')")
    pg.wait_for_selector(".pick-pin")
    assert "12.93520" in pg.locator("#app").inner_text()
    pg.fill("textarea", "Garbage not collected for a week")
    pg.click("button:has-text('Continue')")
    pg.wait_for_selector("text=Confirm language and text")
    assert "Koramangala" in pg.locator("aside.card").inner_text()  # ward from GPS pin
    ctx.close()
