"""Integração local de perfil móvel em iframes fora do processo.

Execute com xvfb-run -a python tests/check_orientation_chrome.py.
Usa perfis temporários e páginas locais, sem acessar contas.
"""

import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from launcher.eightu_popup_blocker import NaveHubTitleSession, _CDPWebSocket


def wait(label, fn):
    for _ in range(100):
        value = fn()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError(label)


def targets(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=0.3) as r:
            return json.load(r)
    except OSError:
        return []


def request(ws, method, params=None):
    n = ws.call(method, params)
    while True:
        message = ws.recv()
        if message and message.get("id") == n:
            assert "error" not in message, message
            return message.get("result", {})


def evaluate(ws, expression):
    result = request(ws, "Runtime.evaluate", {"expression": expression, "returnByValue": True})
    assert "exceptionDetails" not in result, result
    return result["result"].get("value")


def shortcut(ws, repeat=False):
    request(
        ws,
        "Input.dispatchKeyEvent",
        {
            "type": "rawKeyDown",
            "key": "O",
            "code": "KeyO",
            "windowsVirtualKeyCode": 79,
            "modifiers": 9,
            "autoRepeat": repeat,
        },
    )
    if not repeat:
        request(
            ws,
            "Input.dispatchKeyEvent",
            {
                "type": "keyUp",
                "key": "O",
                "code": "KeyO",
                "windowsVirtualKeyCode": 79,
                "modifiers": 9,
            },
        )


def click(ws, side):
    rect = evaluate(
        ws,
        """JSON.stringify((()=>{
        const r=document.getElementById('navehub-orientation').getBoundingClientRect();
        return {x:r.x,y:r.y,width:r.width};
    })())""",
    )
    r = json.loads(rect)
    point = {
        "x": r["x"] + (30 if side == "retrato" else 100),
        "y": r["y"] + 18,
        "button": "left",
        "clickCount": 1,
    }
    for event in ["mousePressed", "mouseReleased"]:
        request(ws, "Input.dispatchMouseEvent", {"type": event, **point})


headers_seen: list[tuple[str | None, str, str | None, str | None]] = []


class Pages(BaseHTTPRequestHandler):
    def do_GET(self):
        headers_seen.append(
            (
                self.headers.get("Host"),
                self.path,
                self.headers.get("User-Agent"),
                self.headers.get("Sec-CH-UA-Mobile"),
            )
        )
        port = self.server.server_port
        if self.path == "/":
            html = '<script>window.reports={};addEventListener("message",e=>{if(e.data.name)reports[e.data.name]=e.data});</script>'
        else:
            name = self.path.split("?")[0]
            html = f"""<script>
                const report={{name:{json.dumps(name)},ua:navigator.userAgent,mobile:navigator.userAgentData?.mobile,angle:screen.orientation.angle}};
                window.currentReport=report;
                window.addEventListener('message',event=>{{
                    if(event.data?.query)top.postMessage({{...report,ua:navigator.userAgent,mobile:navigator.userAgentData?.mobile,angle:screen.orientation.angle}},'*');
                }});
                top.postMessage(report,'*');
            </script>"""
            if self.path.startswith("/frame"):
                html += f'<iframe src="http://c.test:{port}/nested"></iframe>'
        content = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *args):
        pass


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Pages)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix="navehub-mobile-frames-") as temp:
        process = None
        session = None
        ws = None
        try:
            profile = Path(temp)
            port = server.server_port
            process = subprocess.Popen(
                [
                    "google-chrome",
                    "--no-sandbox",
                    "--no-first-run",
                    "--disable-gpu",
                    "--disable-background-networking",
                    "--site-per-process",
                    "--no-proxy-server",
                    "--host-resolver-rules=MAP a.test 127.0.0.1, MAP b.test 127.0.0.1, MAP c.test 127.0.0.1",
                    f"--unsafely-treat-insecure-origin-as-secure=http://a.test:{port},http://b.test:{port},http://c.test:{port}",
                    "--remote-debugging-port=0",
                    f"--user-data-dir={profile}",
                    "--window-size=600,800",
                    f"--app=http://a.test:{port}/",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            active = profile / "DevToolsActivePort"
            wait("porta", active.exists)
            debug_port = int(active.read_text().splitlines()[0])
            target = wait(
                "aba", lambda: next((t for t in targets(debug_port) if t["type"] == "page"), None)
            )
            session = NaveHubTitleSession(process, profile, debug_port, "")
            session.start()
            ws = _CDPWebSocket(target["webSocketDebuggerUrl"])
            ws.connect()
            wait(
                "painel",
                lambda: evaluate(
                    ws,
                    'location.hostname==="a.test"&&!!document.getElementById("navehub-orientation")',
                ),
            )
            shortcut(ws)
            click(ws, "retrato")
            wait(
                "retrato na página principal",
                lambda: evaluate(ws, 'navigator.userAgent.includes("Android")'),
            )
            evaluate(
                ws,
                f'const f=document.createElement("iframe");f.src="http://b.test:{port}/frame";document.body.append(f)',
            )
            reports = wait(
                "dois iframes responderam",
                lambda: evaluate(ws, "Object.keys(reports).length===2&&reports"),
            )

            assert all(
                "Android" in report["ua"] and report["mobile"] is True
                for report in reports.values()
            ), "Iframe de outro domínio recebeu identidade desktop"
            frame_headers = [h for h in headers_seen if h[1] in ["/frame", "/nested"]]
            assert len(frame_headers) == 2
            assert all("Android" in h[2] and h[3] == "?1" for h in frame_headers), frame_headers
            click(ws, "paisagem")
            wait("paisagem", lambda: evaluate(ws, "screen.orientation.angle===90"))
            evaluate(
                ws,
                'reports={};document.querySelector("iframe").contentWindow.postMessage({query:true},"*")',
            )
            report = wait("iframe existente em paisagem", lambda: evaluate(ws, 'reports["/frame"]'))
            assert report["mobile"] is True, report
            click(ws, "paisagem")
            wait("modo original", lambda: evaluate(ws, '!navigator.userAgent.includes("Android")'))
            evaluate(
                ws,
                'reports={};document.querySelector("iframe").contentWindow.postMessage({query:true},"*")',
            )
            report = wait("iframe existente restaurado", lambda: evaluate(ws, 'reports["/frame"]'))
            assert "Android" not in report["ua"], report
            assert report["mobile"] is False, report
            shortcut(ws)
            shortcut(ws)
            click(ws, "retrato")
            wait("novo retrato", lambda: evaluate(ws, 'navigator.userAgent.includes("Android")'))
            evaluate(ws, 'reports={};document.querySelector("iframe").remove()')
            evaluate(
                ws,
                f'const newFrame=document.createElement("iframe");newFrame.src="http://b.test:{port}/frame";document.body.append(newFrame)',
            )
            reports = wait(
                "iframes após reativar",
                lambda: evaluate(ws, "Object.keys(reports).length===2&&reports"),
            )
            assert all(
                "Android" in report["ua"] and report["mobile"] for report in reports.values()
            ), reports
            request(ws, "Page.reload")
            wait(
                "lobby recarregado",
                lambda: evaluate(
                    ws,
                    'location.hostname==="a.test"&&!!document.getElementById("navehub-orientation")',
                ),
            )
            evaluate(
                ws,
                f'const game=document.createElement("iframe");game.src="http://b.test:{port}/frame";document.body.append(game)',
            )
            reports = wait(
                "jogo após reload", lambda: evaluate(ws, "Object.keys(reports).length===2&&reports")
            )
            assert all(
                "Android" in report["ua"] and report["mobile"] for report in reports.values()
            ), reports
            print(
                "VERIFICADO: dois iframes de outros domínios e requisições Mobile; paisagem; restauração desktop; reativação; jogo após reload."
            )
        finally:
            if ws:
                ws.close()
            if process:
                process.terminate()
            if session:
                session.stop()
            if process:
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            server.shutdown()


if __name__ == "__main__":
    main()
