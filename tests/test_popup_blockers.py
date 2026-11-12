"""Regras executadas no DOM de um Chrome real com páginas e perfil descartáveis."""

import hashlib
import json
import shutil
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from launcher.eightu_popup_blocker import (
    EIGHTU_POPUP_BLOCKER_SOURCE,
    NINETY_THREE_H_POPUP_BLOCKER_SOURCE,
    SEVEN_SEVEN_POPUP_BLOCKER_SOURCE,
    THREE_SIXTY_FIVE_GG_POPUP_BLOCKER_SOURCE,
    EightUPopupBlockerSession,
    _CDPWebSocket,
)

SOURCES = {
    "8U": EIGHTU_POPUP_BLOCKER_SOURCE,
    "777": SEVEN_SEVEN_POPUP_BLOCKER_SOURCE,
    "365GG": THREE_SIXTY_FIVE_GG_POPUP_BLOCKER_SOURCE,
}
POSTER = "https://oss.goodofs.com/images/poster/e6pd1793534757854761.png"
OTHER_POSTER = "https://oss.goodofs.com/images/poster/other.png"


@pytest.fixture(scope="module")
def chrome(tmp_path_factory):
    binary = shutil.which("google-chrome-stable") or shutil.which("google-chrome")
    if not binary:
        pytest.skip("Chrome não instalado; teste de DOM NÃO VERIFICADO")
    profile = tmp_path_factory.mktemp("popup-chrome")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<!doctype html><title>Popup fixture</title><body></body>")

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    process = subprocess.Popen(
        [
            binary,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-background-networking",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-debugging-port=0",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        port_file = profile / "DevToolsActivePort"
        for _ in range(150):
            if port_file.exists():
                break
            assert process.poll() is None, "Chrome encerrou antes do teste"
            time.sleep(0.05)
        assert port_file.exists(), "Chrome não disponibilizou CDP"
        port = int(port_file.read_text().splitlines()[0])
        yield port, f"http://127.0.0.1:{server.server_port}/", process, profile
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def page(chrome):
    port, url, *_ = chrome
    req = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?{url}", method="PUT")
    with urllib.request.urlopen(req, timeout=3) as response:
        target = json.load(response)
    with _CDPWebSocket(target["webSocketDebuggerUrl"], timeout=10) as ws:
        def evaluate(expression):
            number = ws.call(
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": True, "awaitPromise": True},
            )
            while True:
                message = ws.recv()
                if message and message.get("id") == number:
                    assert "error" not in message, message
                    result = message["result"]
                    assert "exceptionDetails" not in result, result
                    return result["result"].get("value")

        for _ in range(100):
            if evaluate("document.readyState === 'complete' && location.protocol === 'http:'"):
                break
            time.sleep(0.02)
        assert evaluate("Boolean(document.body)")
        # Impedir que as imagens de fixtures façam requisições aos sites reais.
        evaluate("document.head.innerHTML = `<meta http-equiv='Content-Security-Policy' content=\"img-src 'none'\">`")
        yield evaluate
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/close/{target['id']}", timeout=3):
        pass


def settle(page):
    page("new Promise(resolve => setTimeout(resolve, 30))")


def setup(page, platform, html, *, dynamic=False):
    if dynamic:
        page(SOURCES[platform])
    page("document.body.innerHTML = " + json.dumps(html))
    if not dynamic:
        page(SOURCES[platform])
    settle(page)


def pair(content, name="bad"):
    return (
        f'<div class="van-overlay" id="{name}-overlay"></div>'
        f'<div class="van-popup" id="{name}">{content}</div>'
    )


@pytest.mark.parametrize(
    ("platform", "content"),
    [
        ("8U", f'<img src="{OTHER_POSTER}">'),
        ("777", f'<img src="{POSTER}?v=1">'),
        ("8U", '<div class="dialog-apknoty">Instalar</div>'),
        ("777", '<div class="dialog-apknoty">Instalar</div>'),
        ("365GG", '<div class="dialog-apknoty">Instalar</div>'),
        ("777", '<h2>Aviso de Permissão</h2><p>Ativar notificações?</p><button>Permitir</button>'),
    ],
)
@pytest.mark.parametrize("dynamic", [False, True])
def test_target_and_own_overlay_removed(page, platform, content, dynamic):
    setup(page, platform, pair(content), dynamic=dynamic)
    assert page("document.querySelectorAll('#bad, #bad-overlay').length") == 0


@pytest.mark.parametrize("platform", SOURCES)
def test_legitimate_modals_and_interactions_preserved(page, platform):
    html = """
      <div class="van-overlay" id="login-overlay"></div>
      <div class="van-popup" id="login"><form><input value="editado"><button>Entrar</button></form></div>
      <div class="van-dialog" id="register">Registro <button>Criar conta</button></div>
      <div class="modal" id="deposit">Depósito <button>Confirmar</button></div>
      <div role="dialog" id="withdraw">Saque <button>Sacar</button></div>
      <div class="popup" id="confirmation">Confirmação <button>OK</button></div>
      <div class="goldbox-content" id="pop-recode">Recompensa</div>
      <div id="rb-layer">Camada</div><div id="rb-layer2">Camada 2</div>
      <div id="gold-coin-container">Moedas</div>
    """
    setup(page, platform, html, dynamic=True)
    assert page("document.body.innerHTML") == html
    assert page("document.querySelector('input').value") == "editado"
    page("document.querySelector('#deposit button').onclick=()=>window.confirmed=true;document.querySelector('#deposit button').click()")
    assert page("window.confirmed")
    assert page("document.body.style.overflow") == ""


@pytest.mark.parametrize(
    ("platform", "content"),
    [
        ("777", f'<img src="{OTHER_POSTER}">'),
        ("777", '<img src="https://oss.goodofs.com/images/poster/nurk1787078713673359.png">'),
        ("777", '<img src="https://example.test/static/images/c4/syscom/pwav2/pwa_update_banner.png?v=1.0">'),
        ("365GG", f'<img src="{POSTER}">'),
        ("365GG", '<h2>Aviso de Permissão</h2><p>Ativar notificações?</p><button>Permitir</button>'),
        ("8U", '<h2>Aviso de Permissão</h2><p>Ativar notificações?</p><button>Permitir</button>'),
        ("777", '<h2>Aviso de Permissão</h2><p>Permitir localização?</p><button>Permitir</button>'),
        ("777", '<p>Texto de ajuda: Aviso de Permissão para notificações.</p><button>OK</button>'),
        ("8U", '<img src="https://other.test/oss.goodofs.com/images/poster/fake.png">'),
        ("777", '<img src="https://oss.goodofs.com.evil.test/images/poster/e6pd1793534757854761.png">'),
    ],
)
def test_rules_do_not_cross_platforms_or_match_unrelated_content(page, platform, content):
    setup(page, platform, pair(content), dynamic=True)
    assert page("document.querySelectorAll('#bad, #bad-overlay').length") == 2


@pytest.mark.parametrize("platform", SOURCES)
def test_other_modal_keeps_overlay_and_scroll_locked_until_close(page, platform):
    html = pair('<div class="dialog-apknoty">Instalar</div>') + pair('<button>Depositar</button>', "legit")
    page("document.body.className='van-overflow-hidden'; document.body.style.overflow='hidden'; document.documentElement.style.overflow='hidden'")
    setup(page, platform, html, dynamic=True)
    assert page("document.querySelectorAll('#bad, #bad-overlay').length") == 0
    assert page("document.querySelectorAll('#legit, #legit-overlay').length") == 2
    assert page("document.body.style.overflow") == "hidden"
    page("document.querySelector('#legit').remove();document.querySelector('#legit-overlay').remove()")
    settle(page)
    assert page("document.body.style.overflow") == ""
    assert page("document.documentElement.style.overflow") == ""
    assert not page("document.body.classList.contains('van-overflow-hidden')")


def test_scroll_unlock_without_overwriting_unrelated_styles(page):
    page("document.body.style.cssText='overflow-y:hidden;color:red';document.documentElement.style.overflow='clip'")
    setup(page, "8U", pair(f'<img src="{OTHER_POSTER}">'))
    assert page("document.body.style.overflowY") == ""
    assert page("document.body.style.color") == "red"
    assert page("document.documentElement.style.overflow") == ""


def test_no_target_does_not_change_scroll(page):
    page("document.body.style.overflow='hidden'")
    setup(page, "365GG", "<div>Conteúdo comum</div>")
    assert page("document.body.style.overflow") == "hidden"


def test_do_not_steal_overlay_before_another_dialog(page):
    html = '<div class="van-popup" id="bad"><div class="dialog-apknoty"></div></div>' + pair('<button>Sacar</button>', "legit")
    setup(page, "777", html)
    assert not page("Boolean(document.querySelector('#bad'))")
    assert page("document.querySelectorAll('#legit, #legit-overlay').length") == 2


def test_explicit_overlay_link_and_shared_overlay_preserved(page):
    html = """
      <div class="van-overlay" id="own" aria-controls="bad"></div><span>Separador</span>
      <div class="van-popup" id="bad"><div class="dialog-apknoty"></div></div>
      <div class="van-overlay" id="shared" aria-controls="bad2 legit"></div>
      <div class="van-popup" id="bad2"><div class="dialog-apknoty"></div></div>
      <div class="van-popup" id="legit">Confirmação</div>
    """
    setup(page, "777", html)
    assert page("document.querySelectorAll('#own, #bad, #bad2').length") == 0
    assert page("document.querySelectorAll('#shared, #legit').length") == 2


def test_attribute_and_text_changes_are_detected(page):
    setup(page, "777", pair('<img src="https://example.test/ok.png">'))
    assert page("Boolean(document.querySelector('#bad'))")
    page("document.querySelector('#bad img').src=" + json.dumps(POSTER))
    settle(page)
    assert page("document.querySelectorAll('#bad, #bad-overlay').length") == 0
    page("document.body.innerHTML=" + json.dumps(pair('<h2>Outro título</h2><p>Ativar notificações?</p><button>Permitir</button>')))
    settle(page)
    page("document.querySelector('h2').firstChild.data='Aviso de Permissão'")
    settle(page)
    assert page("document.querySelectorAll('#bad, #bad-overlay').length") == 0


def test_93h_source_unchanged():
    assert hashlib.sha256(NINETY_THREE_H_POPUP_BLOCKER_SOURCE.encode()).hexdigest() == (
        "4846bda28626b1d1f06d9c37e5a7d83b09d6bbf61ac32b1815f088f07f7fbe2b"
    )


def test_shared_overlay_with_data_attributes_is_preserved(page):
    html = """
      <div class="van-overlay" id="shared"></div>
      <div class="van-popup" data-overlay-id="shared" id="bad"><div class="dialog-apknoty"></div></div>
      <div class="van-popup" data-overlay-id="shared" id="legit">Login</div>
    """
    setup(page, "365GG", html)
    assert not page("Boolean(document.querySelector('#bad'))")
    assert page("document.querySelectorAll('#shared, #legit').length") == 2


@pytest.mark.parametrize("overlay_first", [False, True])
def test_standalone_apk_dialog_and_its_overlay(page, overlay_first):
    popup = '<div class="dialog-apknoty" id="bad">Instalar</div>'
    overlay = '<div class="van-overlay" id="bad-overlay"></div>'
    setup(page, "365GG", overlay + popup if overlay_first else popup + overlay)
    assert page("document.querySelectorAll('#bad, #bad-overlay').length") == 0


def test_scroll_waits_for_other_modal_to_be_hidden(page):
    setup(page, "8U", pair('<div class="dialog-apknoty"></div>') + pair("Registro", "legit"))
    page("document.body.style.overflow='hidden';document.querySelector('#legit').hidden=true;document.querySelector('#legit-overlay').style.display='none'")
    settle(page)
    assert page("document.body.style.overflow") == ""


def test_real_cdp_session_reinjects_after_reload(page, chrome):
    port, _url, process, profile = chrome
    session = EightUPopupBlockerSession(process, profile, port)
    session.start()
    try:
        for _ in range(100):
            if page("Boolean(window.__navehub8uPopupBlockerInstalled)"):
                break
            time.sleep(0.05)
        assert page("Boolean(window.__navehub8uPopupBlockerInstalled)")
        page("document.body.innerHTML=" + json.dumps(pair(f'<img src="{OTHER_POSTER}">')))
        settle(page)
        assert page("document.querySelectorAll('#bad, #bad-overlay').length") == 0
        page("location.reload()")
        for _ in range(100):
            if page("document.readyState==='complete' && Boolean(window.__navehub8uPopupBlockerInstalled)"):
                break
            time.sleep(0.05)
        assert page("Boolean(window.__navehub8uPopupBlockerInstalled)")
        page("document.body.innerHTML=" + json.dumps(pair('<div class="dialog-apknoty"></div>')))
        settle(page)
        assert page("document.querySelectorAll('#bad, #bad-overlay').length") == 0
    finally:
        session.stop()


def test_account_starts_with_mobile_portrait(page, chrome):
    port, url, process, profile = chrome
    session = EightUPopupBlockerSession(process, profile, port)
    session.initial_url = url
    session.start()
    try:
        for _ in range(100):
            if page("navigator.userAgent.includes('Android') && screen.orientation.angle === 0"):
                break
            time.sleep(0.05)
        assert page("navigator.userAgent.includes('Android') && navigator.userAgentData.mobile")
        assert page("screen.orientation.type === 'portrait-primary'")
    finally:
        session.stop()
