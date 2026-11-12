"""
Bloqueador de popups da plataforma 8U via Chrome DevTools Protocol.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import threading
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from launcher.browser_orientation import BrowserOrientation


def _build_popup_blocker_source(platform: str, installed_flag: str) -> str:
    configuration = json.dumps({"platform": platform, "installedFlag": installed_flag})
    return "(function(config) {" + r"""
    'use strict';
    if (window[config.installedFlag]) return;
    window[config.installedFlag] = true;

    // Estes seletores localizam contêineres; somente as regras abaixo os bloqueiam.
    const dialogs = '.van-popup, .van-dialog, [role="dialog"], [aria-modal="true"], .modal, .popup';
    const normalize = text => text.replace(/\s+/g, ' ').trim();
    const visible = element => {
        const style = getComputedStyle(element);
        return !element.hidden && style.display !== 'none' && style.visibility !== 'hidden'
            && element.getClientRects().length > 0;
    };
    const container = element => element.closest(dialogs);
    const imageMatches = image => {
        try {
            const url = new URL(image.getAttribute('src') || image.currentSrc || '', document.baseURI);
            if (url.hostname !== 'oss.goodofs.com') return false;
            if (config.platform === '8U') return url.pathname.startsWith('/images/poster/');
            return config.platform === '777'
                && url.pathname === '/images/poster/e6pd1793534757854761.png';
        } catch { return false; }
    };
    const notificationPrompt = popup => {
        if (config.platform !== '777') return false;
        const titles = popup.querySelectorAll(
            '.van-dialog__header, .van-popup__title, [role="heading"], h1, h2, h3, .title'
        );
        return Array.from(titles).some(title =>
            normalize(title.textContent) === 'Aviso de Permissão' && container(title) === popup
        ) && /notifica[çc][aãõo]/i.test(popup.textContent)
            && Boolean(popup.querySelector('button, [role="button"], .van-button'));
    };
    const targetPopups = () => {
        const targets = new Set();
        document.querySelectorAll('.dialog-apknoty').forEach(marker => {
            targets.add(container(marker) || marker);
        });
        if (config.platform !== '365GG') {
            document.querySelectorAll('img').forEach(image => {
                if (!imageMatches(image)) return;
                const popup = config.platform === '8U' ? image.closest('.van-popup') : container(image);
                if (popup) targets.add(popup);
            });
        }
        if (config.platform === '777') {
            document.querySelectorAll(dialogs).forEach(popup => {
                if (notificationPrompt(popup)) targets.add(popup);
            });
        }
        return targets;
    };
    const sameLayer = (overlay, popup) => {
        const a = getComputedStyle(overlay).zIndex;
        const b = getComputedStyle(popup).zIndex;
        if (a === 'auto' || b === 'auto') return true;
        const overlayLevel = Number(a);
        const popupLevel = Number(b);
        // Vant normalmente coloca a máscara um nível abaixo da janela:
        // overlay 2001 / popup 2002, overlay 2004 / popup 2005, etc.
        return Number.isFinite(overlayLevel) && Number.isFinite(popupLevel)
            && (overlayLevel === popupLevel || overlayLevel + 1 === popupLevel);
    };
    const overlayOwner = overlay => {
        const controls = normalize(overlay.getAttribute('aria-controls') || '');
        const references = overlay.id
            ? Array.from(document.querySelectorAll('[data-overlay-id]'))
                .filter(item => item.getAttribute('data-overlay-id') === overlay.id) : [];
        if (controls || references.length) {
            const owners = new Set(references);
            controls.split(' ').filter(Boolean).forEach(id => {
                const owner = document.getElementById(id);
                if (owner) owners.add(owner);
            });
            return owners.size === 1 ? Array.from(owners)[0] : null;
        }
        const next = overlay.nextElementSibling;
        const previous = overlay.previousElementSibling;
        const ownerSelectors = dialogs + ', .dialog-apknoty';
        // Vant posiciona a camada imediatamente antes do seu diálogo.
        if (next?.matches(ownerSelectors) && sameLayer(overlay, next)) return next;
        // Aceitar camada posterior só quando ela não estiver antes de outro diálogo.
        if (!next?.matches(ownerSelectors) && previous?.matches(ownerSelectors) && sameLayer(overlay, previous)) {
            return previous;
        }
        return null;
    };
    const associatedOverlays = popup => {
        const overlays = new Set();
        const explicitId = popup.getAttribute('data-overlay-id');
        if (explicitId) {
            const overlay = document.getElementById(explicitId);
            if (overlay?.matches('.van-overlay') && overlayOwner(overlay) === popup) overlays.add(overlay);
        }
        if (popup.id) {
            document.querySelectorAll('.van-overlay[aria-controls]').forEach(overlay => {
                if (overlayOwner(overlay) === popup) overlays.add(overlay);
            });
        }
        [popup.previousElementSibling, popup.nextElementSibling].forEach(overlay => {
            if (overlay?.matches('.van-overlay') && overlayOwner(overlay) === popup) overlays.add(overlay);
        });
        return overlays;
    };
    let pendingScrollUnlock = false;
    const restoreScroll = () => {
        if (!pendingScrollUnlock) return;
        const modalOpen = Array.from(document.querySelectorAll(dialogs + ', .dialog-apknoty'))
            .some(visible);
        const overlayOpen = Array.from(document.querySelectorAll('.van-overlay')).some(visible);
        if (modalOpen || overlayOpen) return;
        [document.body, document.documentElement].forEach(element => {
            if (!element) return;
            element.classList.remove('van-overflow-hidden');
            ['overflow', 'overflow-x', 'overflow-y'].forEach(property => {
                if (['hidden', 'clip'].includes(element.style.getPropertyValue(property))) {
                    element.style.removeProperty(property);
                }
            });
        });
        pendingScrollUnlock = false;
    };
    const removeTargets = () => {
        const targets = targetPopups();
        // Resolver todas as associações antes de alterar a ordem dos irmãos no DOM.
        const overlays = new Set();
        targets.forEach(popup => associatedOverlays(popup).forEach(overlay => overlays.add(overlay)));
        if (targets.size) pendingScrollUnlock = true;
        targets.forEach(popup => popup.remove());
        overlays.forEach(overlay => overlay.remove());
        restoreScroll();
    };
    const start = () => {
        if (!document.body) return;
        let scheduled = false;
        const observer = new MutationObserver(() => {
            if (scheduled) return;
            scheduled = true;
            queueMicrotask(() => { scheduled = false; removeTargets(); });
        });
        observer.observe(document.body, {
            childList: true, subtree: true, characterData: true, attributes: true,
            attributeFilter: ['src', 'srcset', 'class', 'style', 'hidden', 'aria-hidden',
                'aria-controls', 'data-overlay-id']
        });
        // Mudanças no bloqueio de scroll da raiz também podem acompanhar o fechamento.
        observer.observe(document.documentElement, {attributes: true, attributeFilter: ['class', 'style']});
        removeTargets();
    };
    if (document.body) start();
    else document.addEventListener('DOMContentLoaded', start, {once: true});
""" + "})(" + configuration + ");"


EIGHTU_POPUP_BLOCKER_SOURCE = _build_popup_blocker_source("8U", "__navehub8uPopupBlockerInstalled")
SEVEN_SEVEN_POPUP_BLOCKER_SOURCE = _build_popup_blocker_source("777", "__navehub777PopupBlockerInstalled")
THREE_SIXTY_FIVE_GG_POPUP_BLOCKER_SOURCE = _build_popup_blocker_source(
    "365GG", "__navehub365ggPopupBlockerInstalled"
)

NINETY_THREE_H_POPUP_BLOCKER_SOURCE = r"""
(function() {
    'use strict';

    if (window.__navehub93hPopupBlockerInstalled) {
        return;
    }
    window.__navehub93hPopupBlockerInstalled = true;

    const shouldRemovePopup = (popup) => {
        if (popup.querySelector('.dialog-apknoty')) {
            return true;
        }

        // Banner automático sem conteúdo interativo, usado pelo site ao
        // iniciar. Modais normais continuam disponíveis para o usuário.
        return Boolean(
            popup.querySelector('img[src*="/images/poster/"]') &&
            !popup.textContent.trim()
        );
    };

    const removeTargetPopups = () => {
        document.querySelectorAll('.van-popup').forEach((popup) => {
            if (!shouldRemovePopup(popup)) {
                return;
            }
            [popup.previousElementSibling, popup.nextElementSibling]
                .filter((element) => element && element.matches('.van-overlay'))
                .forEach((backdrop) => backdrop.remove());
            popup.remove();
        });
    };

    const start = () => {
        if (!document.body) {
            return;
        }

        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.addedNodes.length) {
                    removeTargetPopups();
                }
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        removeTargetPopups();
    };

    if (document.body) {
        start();
    } else {
        document.addEventListener('DOMContentLoaded', start, { once: true });
    }
})();
"""


def build_page_title_source(title: str) -> str:
    """Mantém o título da janela Chromium igual à legenda persistida da conta."""
    title_json = json.dumps(title, ensure_ascii=False)
    return f"""
(function() {{
    'use strict';

    const accountTitle = {title_json};
    const applyTitle = () => {{
        if (document.title !== accountTitle) {{
            document.title = accountTitle;
        }}
    }};

    const observeTitle = () => {{
        const root = document.documentElement;
        if (!root) {{
            document.addEventListener('DOMContentLoaded', observeTitle, {{ once: true }});
            return;
        }}
        applyTitle();
        new MutationObserver(applyTitle).observe(root, {{
            childList: true,
            subtree: true,
            characterData: true,
        }});
    }};

    observeTitle();
}})();
"""


class _CDPWebSocket:
    def __init__(self, websocket_url: str, timeout: float = 2.0):
        self._url = websocket_url
        self._timeout = timeout
        self._socket: socket.socket | None = None
        self._next_id = 1

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        self.close()

    def connect(self):
        parsed = urlparse(self._url)
        if parsed.scheme != "ws" or parsed.hostname not in ("127.0.0.1", "localhost"):
            raise OSError("Endpoint CDP inválido.")

        port = parsed.port or 80
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ).encode("ascii")

        sock = socket.create_connection((parsed.hostname, port), timeout=self._timeout)
        sock.settimeout(self._timeout)
        try:
            sock.sendall(request)
            response = b""
            while b"\r\n\r\n" not in response:
                chunk = sock.recv(4096)
                if not chunk:
                    raise OSError("Handshake CDP encerrado.")
                response += chunk
                if len(response) > 65536:
                    raise OSError("Handshake CDP excedeu o limite.")

            header = response.split(b"\r\n\r\n", 1)[0].decode("iso-8859-1", "replace")
            accept_seed = key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
            expected_accept = base64.b64encode(hashlib.sha1(accept_seed.encode("ascii")).digest()).decode("ascii")
            if " 101 " not in header or expected_accept not in header:
                raise OSError("Handshake CDP recusado.")
        except Exception:
            sock.close()
            raise

        self._socket = sock

    def close(self):
        if self._socket is None:
            return
        try:
            self._send_frame(b"", opcode=0x8)
        except OSError:
            pass
        try:
            self._socket.close()
        finally:
            self._socket = None

    def call(self, method: str, params: dict | None = None, session_id: str | None = None):
        message_id = self._next_id
        self._next_id += 1
        payload = {"id": message_id, "method": method}
        if params is not None:
            payload["params"] = params
        if session_id is not None:
            payload["sessionId"] = session_id
        self._send_frame(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        return message_id

    def recv(self):
        return self._recv_frame()

    def _send_frame(self, payload: bytes, opcode: int = 0x1):
        if self._socket is None:
            raise OSError("WebSocket CDP desconectado.")

        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.extend((0x80 | 126, *struct.pack("!H", length)))
        else:
            header.extend((0x80 | 127, *struct.pack("!Q", length)))

        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self._socket.sendall(bytes(header) + mask + masked)

    def _recv_exact(self, size: int) -> bytes:
        if self._socket is None:
            raise OSError("WebSocket CDP desconectado.")

        chunks = bytearray()
        while len(chunks) < size:
            chunk = self._socket.recv(size - len(chunks))
            if not chunk:
                raise OSError("WebSocket CDP encerrado.")
            chunks.extend(chunk)
        return bytes(chunks)

    def _recv_frame(self):
        first, second = self._recv_exact(2)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]

        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length) if length else b""
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))

        if opcode == 0x8:
            raise OSError("WebSocket CDP fechado.")
        if opcode == 0x9:
            self._send_frame(payload, opcode=0xA)
            return None
        if opcode != 0x1:
            return None

        return json.loads(payload.decode("utf-8"))


class _CDPPopupBlockerSession:
    def __init__(self, process, profile_dir: Path, port: int, source: str, thread_prefix: str):
        self._process = process
        self._profile_dir = Path(profile_dir)
        self._port = int(port)
        self._source = source
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name=f"{thread_prefix}-{self._profile_dir.name}",
            daemon=True,
        )

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=1.0)

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def _run(self):
        while not self._stop_event.is_set() and self._process.poll() is None:
            target_url = self._find_page_websocket()
            if not target_url:
                self._stop_event.wait(0.25)
                continue

            try:
                self._apply_to_target(target_url)
                self._wait_until_target_closes()
            except Exception:
                self._stop_event.wait(0.5)

    def _find_page_websocket(self) -> str | None:
        try:
            request = urllib.request.Request(f"http://127.0.0.1:{self._port}/json/list")
            with urllib.request.urlopen(request, timeout=0.5) as response:
                targets = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError):
            return None

        if not isinstance(targets, list):
            return None
        for target in targets:
            if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                return target["webSocketDebuggerUrl"]
        return None

    def _apply_to_target(self, websocket_url: str):
        with _CDPWebSocket(websocket_url) as ws:
            ws.call("Page.enable")
            ws.call(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": self._source},
            )
            ws.call(
                "Runtime.evaluate",
                {"expression": self._source, "awaitPromise": False},
            )
            orientation = BrowserOrientation(ws)
            orientation.install()
            if getattr(self, 'initial_url', None):
                orientation.set_mode('retrato')
                orientation.request('Page.navigate', {'url': self.initial_url})
                self.initial_url = None
            while not self._stop_event.is_set() and self._process.poll() is None:
                try:
                    orientation.handle(orientation.next_event())
                except TimeoutError:
                    continue

    def _wait_until_target_closes(self):
        if self._process.poll() is not None:
            return
        self._stop_event.wait(0.25)


class NaveHubTitleSession(_CDPPopupBlockerSession):
    def __init__(self, process, profile_dir: Path, port: int, title_source: str):
        super().__init__(
            process,
            profile_dir,
            port,
            title_source,
            "navehub-title-cdp",
        )


class EightUPopupBlockerSession(_CDPPopupBlockerSession):
    def __init__(self, process, profile_dir: Path, port: int, title_source: str = ""):
        super().__init__(
            process,
            profile_dir,
            port,
            f"{title_source}\n{EIGHTU_POPUP_BLOCKER_SOURCE}",
            "navehub-8u-cdp",
        )


class SevenSevenPopupBlockerSession(_CDPPopupBlockerSession):
    def __init__(self, process, profile_dir: Path, port: int, title_source: str = ""):
        super().__init__(
            process,
            profile_dir,
            port,
            f"{title_source}\n{SEVEN_SEVEN_POPUP_BLOCKER_SOURCE}",
            "navehub-777-cdp",
        )


class ThreeSixtyFiveGGPopupBlockerSession(_CDPPopupBlockerSession):
    def __init__(self, process, profile_dir: Path, port: int, title_source: str = ""):
        super().__init__(
            process,
            profile_dir,
            port,
            f"{title_source}\n{THREE_SIXTY_FIVE_GG_POPUP_BLOCKER_SOURCE}",
            "navehub-365gg-cdp",
        )


class NinetyThreeHPopupBlockerSession(_CDPPopupBlockerSession):
    def __init__(self, process, profile_dir: Path, port: int, title_source: str = ""):
        super().__init__(
            process,
            profile_dir,
            port,
            f"{title_source}\n{NINETY_THREE_H_POPUP_BLOCKER_SOURCE}",
            "navehub-93h-cdp",
        )
