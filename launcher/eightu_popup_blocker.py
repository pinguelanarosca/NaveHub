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
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


EIGHTU_POPUP_BLOCKER_SOURCE = r"""
(function() {
    'use strict';

    if (window.__navehub8uPopupBlockerInstalled) {
        return;
    }
    window.__navehub8uPopupBlockerInstalled = true;

    const removePopups = () => {
        const selectors = [
            '.van-popup',
            '.van-overlay',
            '.dialog-apknoty'
        ];

        selectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => el.remove());
        });

        if (document.body) {
            document.body.style.overflow = 'auto';
            document.body.classList.remove('van-overflow-hidden');
        }

        document.documentElement.style.overflow = 'auto';
    };

    const start = () => {
        if (!document.body) {
            return;
        }

        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.addedNodes.length) {
                    removePopups();
                }
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        removePopups();
    };

    if (document.body) {
        start();
    } else {
        document.addEventListener('DOMContentLoaded', start, { once: true });
    }
})();
"""

SEVEN_SEVEN_POPUP_BLOCKER_SOURCE = r"""
(function() {
    'use strict';

    if (window.__navehub777PopupBlockerInstalled) {
        return;
    }
    window.__navehub777PopupBlockerInstalled = true;

    const permissionText = 'Aviso de Permissão';
    const imageSources = [
        'oss.goodofs.com/images/poster/nurk1787078713673359.png',
        'static/images/c4/syscom/pwav2/pwa_update_banner.png?v=1.0'
    ];
    const popupSelectors = [
        '.van-popup',
        '.van-dialog',
        '.dialog-apknoty',
        '[role="dialog"]',
        '.popup',
        '.modal'
    ];

    const findPopup = (element) => {
        if (!element || !element.closest) {
            return null;
        }

        const closest = element.closest(popupSelectors.join(','));
        if (closest && closest !== document.body && closest !== document.documentElement) {
            return closest;
        }

        let current = element.parentElement;
        let depth = 0;
        while (current && current !== document.body && current !== document.documentElement && depth < 6) {
            const role = current.getAttribute('role');
            const className = String(current.className || '').toLowerCase();
            if (
                role === 'dialog' ||
                className.includes('popup') ||
                className.includes('dialog') ||
                className.includes('modal')
            ) {
                return current;
            }
            current = current.parentElement;
            depth += 1;
        }

        return null;
    };

    const containsTargetImage = (popup) => {
        return Array.from(popup.querySelectorAll('img')).some((img) => {
            const src = img.getAttribute('src') || '';
            return imageSources.some((target) => src.includes(target));
        });
    };

    const shouldRemovePopup = (popup) => {
        if (!popup || popup === document.body || popup === document.documentElement) {
            return false;
        }
        return popup.textContent.includes(permissionText) || containsTargetImage(popup);
    };

    const findAssociatedOverlay = (popup) => {
        if (!popup || !popup.parentElement) {
            return null;
        }

        if (popup.previousElementSibling && popup.previousElementSibling.matches('.van-overlay')) {
            return popup.previousElementSibling;
        }
        if (popup.nextElementSibling && popup.nextElementSibling.matches('.van-overlay')) {
            return popup.nextElementSibling;
        }

        let previous = popup.previousElementSibling;
        let previousDistance = 0;
        while (previous && previousDistance < 3) {
            if (previous.matches('.van-overlay')) {
                return previous;
            }
            previous = previous.previousElementSibling;
            previousDistance += 1;
        }

        let next = popup.nextElementSibling;
        let nextDistance = 0;
        while (next && nextDistance < 3) {
            if (next.matches('.van-overlay')) {
                return next;
            }
            next = next.nextElementSibling;
            nextDistance += 1;
        }

        return null;
    };

    const removeTargetPopups = () => {
        const targets = new Set();
        const overlays = new Set();

        document.querySelectorAll(popupSelectors.join(',')).forEach((popup) => {
            if (shouldRemovePopup(popup)) {
                targets.add(popup);
                const overlay = findAssociatedOverlay(popup);
                if (overlay) {
                    overlays.add(overlay);
                }
            }
        });

        document.querySelectorAll('img').forEach((img) => {
            const src = img.getAttribute('src') || '';
            if (imageSources.some((target) => src.includes(target))) {
                const popup = findPopup(img);
                if (popup && shouldRemovePopup(popup)) {
                    targets.add(popup);
                    const overlay = findAssociatedOverlay(popup);
                    if (overlay) {
                        overlays.add(overlay);
                    }
                }
            }
        });

        targets.forEach((popup) => popup.remove());
        overlays.forEach((overlay) => overlay.remove());
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

THREE_SIXTY_FIVE_GG_POPUP_BLOCKER_SOURCE = r"""
(function() {
    'use strict';

    if (window.__navehub365ggPopupBlockerInstalled) {
        return;
    }
    window.__navehub365ggPopupBlockerInstalled = true;

    const selectors = [
        '.van-overlay',
        '.van-popup',
        '.goldbox-content',
        '#pop-recode',
        '#rb-layer',
        '#rb-layer2',
        '#gold-coin-container'
    ];

    const hideTargets = () => {
        selectors.forEach((selector) => {
            document.querySelectorAll(selector).forEach((el) => {
                el.style.display = 'none';
            });
        });
    };

    const start = () => {
        if (!document.body) {
            return;
        }

        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.addedNodes.length) {
                    hideTargets();
                }
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        hideTargets();
    };

    if (document.body) {
        start();
    } else {
        document.addEventListener('DOMContentLoaded', start, { once: true });
    }
})();
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

    def call(self, method: str, params: dict | None = None):
        message_id = self._next_id
        self._next_id += 1
        payload = {"id": message_id, "method": method}
        if params is not None:
            payload["params"] = params
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
            while not self._stop_event.is_set() and self._process.poll() is None:
                try:
                    ws.recv()
                except socket.timeout:
                    continue

    def _wait_until_target_closes(self):
        if self._process.poll() is not None:
            return
        self._stop_event.wait(0.25)


class EightUPopupBlockerSession(_CDPPopupBlockerSession):
    def __init__(self, process, profile_dir: Path, port: int):
        super().__init__(
            process,
            profile_dir,
            port,
            EIGHTU_POPUP_BLOCKER_SOURCE,
            "navehub-8u-cdp",
        )


class SevenSevenPopupBlockerSession(_CDPPopupBlockerSession):
    def __init__(self, process, profile_dir: Path, port: int):
        super().__init__(
            process,
            profile_dir,
            port,
            SEVEN_SEVEN_POPUP_BLOCKER_SOURCE,
            "navehub-777-cdp",
        )


class ThreeSixtyFiveGGPopupBlockerSession(_CDPPopupBlockerSession):
    def __init__(self, process, profile_dir: Path, port: int):
        super().__init__(
            process,
            profile_dir,
            port,
            THREE_SIXTY_FIVE_GG_POPUP_BLOCKER_SOURCE,
            "navehub-365gg-cdp",
        )
