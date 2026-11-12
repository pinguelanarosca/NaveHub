"""Controles de orientação da janela isolada de uma conta via CDP."""

import json
import time

ORIENTATION_SOURCE = r"""
(() => {
    if (window.__navehubOrientationShortcutInstalled) return;
    window.__navehubOrientationShortcutInstalled = true;
    const toggle = () => {
        const host = document.getElementById('navehub-orientation');
        if (host) host.hidden = !host.hidden;
    };
    window.addEventListener('keydown', event => {
        if (event.code !== 'KeyO' || !event.altKey || !event.shiftKey || event.ctrlKey || event.metaKey) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (event.repeat) return;
        if (window === window.top) toggle();
        else window.top.postMessage({navehubOrientation: 'toggle'}, '*');
    }, true);
    if (window !== window.top) return;
    window.addEventListener('message', event => {
        if (event.data?.navehubOrientation === 'toggle') toggle();
    });
    const mount = () => {
        if (!document.documentElement) return;
        const host = document.createElement('div');
        host.id = 'navehub-orientation';
        host.hidden = true;
        const root = host.attachShadow({mode: 'closed'});
        root.innerHTML = `<style>
            :host{position:fixed;top:8px;right:8px;z-index:2147483647}
            :host([hidden]){display:none!important}
            div{display:flex;gap:4px;padding:4px;background:#172233;border:1px solid #475569;border-radius:9px}
            button{border:0;border-radius:5px;padding:5px 8px;color:#f8fafc;background:#334155;font:600 12px system-ui;cursor:pointer}
            button[aria-pressed=true]{color:#082128;background:#67e8f9}
            button:disabled{opacity:.55}button:focus-visible{outline:2px solid white}
            p{max-width:210px;background:#172233;color:white;font:12px system-ui;margin:4px 0;padding:4px}
            p:empty{display:none}
        </style><div role="group" aria-label="Orientação desta conta">
            <button data-mode="retrato" aria-pressed="false">Retrato</button>
            <button data-mode="paisagem" aria-pressed="false">Paisagem</button>
        </div><p role="status"></p>`;
        const buttons = [...root.querySelectorAll('button')];
        window.__navehubOrientationResult = result => {
            buttons.forEach(button => {
                button.disabled = false;
                button.setAttribute('aria-pressed', String(button.dataset.mode === result.mode));
            });
            root.querySelector('p').textContent = result.error || (result.mode
                ? 'Recarregue o lobby e abra o jogo. Clique no modo ativo para restaurar.' : '');
        };
        buttons.forEach(button => button.onclick = () => {
            buttons.forEach(item => item.disabled = true);
            window.__navehubOrientation(JSON.stringify({mode: button.dataset.mode}));
        });
        document.documentElement.append(host);
        window.__navehubOrientation(JSON.stringify({mode: 'query'}));
    };
    if (document.documentElement) mount();
    else document.addEventListener('DOMContentLoaded', mount, {once:true});
})();
"""


class BrowserOrientation:
    def __init__(self, ws):
        self.ws = ws
        self.mode = None
        self.original = None
        self.window_id = None

    def request(self, method, params=None):
        request_id = self.ws.call(method, params)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                message = self.ws.recv()
            except TimeoutError:
                continue
            if not message or message.get('id') != request_id:
                continue
            if 'error' in message:
                raise RuntimeError(message['error'].get('message', 'Falha no controle da janela'))
            return message.get('result', {})
        raise TimeoutError('O Chrome não confirmou a orientação da janela.')

    def install(self):
        self.request('Runtime.enable')
        self.request('Runtime.addBinding', {'name': '__navehubOrientation'})
        self.request('Page.addScriptToEvaluateOnNewDocument', {'source': ORIENTATION_SOURCE})
        self.ws.call('Runtime.evaluate', {'expression': ORIENTATION_SOURCE})

    def restore(self):
        self.request('Emulation.clearDeviceMetricsOverride')
        self.request('Emulation.setUserAgentOverride', {'userAgent': ''})
        if self.original:
            self.request('Browser.setWindowBounds', {
                'windowId': self.window_id, 'bounds': {'windowState': 'normal'},
            })
            bounds = {key: self.original[key] for key in ('left', 'top', 'width', 'height')}
            self.request('Browser.setWindowBounds', {'windowId': self.window_id, 'bounds': bounds})
            if self.original['windowState'] != 'normal':
                self.request('Browser.setWindowBounds', {
                    'windowId': self.window_id,
                    'bounds': {'windowState': self.original['windowState']},
                })
        self.mode = None
        self.original = None

    def set_mode(self, mode):
        if mode == self.mode:
            self.restore()
            return
        if not self.original:
            window = self.request('Browser.getWindowForTarget')
            self.window_id = window['windowId']
            self.original = window['bounds']
        height = min(940, max(550, self.original.get('height', 850)))
        size = {'width': min(480, max(360, round(height * .56))), 'height': height}
        if mode == 'paisagem':
            size = {'width': 920, 'height': min(580, height)}
        self.request('Browser.setWindowBounds', {
            'windowId': self.window_id, 'bounds': {'windowState': 'normal'},
        })
        self.request('Browser.setWindowBounds', {'windowId': self.window_id, 'bounds': size})
        version = self.request('Browser.getVersion')['product'].split('/')[-1]
        self.request('Emulation.setUserAgentOverride', {
            'userAgent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9) AppleWebKit/537.36 '
                         f'(KHTML, like Gecko) Chrome/{version} Mobile Safari/537.36',
            'platform': 'Linux armv8l',
            'userAgentMetadata': {
                'brands': [], 'platform': 'Android', 'platformVersion': '14.0.0',
                'architecture': '', 'model': 'Pixel 9', 'mobile': True,
            },
        })
        self.request('Emulation.setDeviceMetricsOverride', {
            'width': 0, 'height': 0, 'deviceScaleFactor': 0, 'mobile': False,
            'dontSetVisibleSize': True,
            'screenOrientation': {
                'type': 'portraitPrimary' if mode == 'retrato' else 'landscapePrimary',
                'angle': 0 if mode == 'retrato' else 90,
            },
        })
        self.mode = mode

    def handle(self, message):
        if not message or message.get('method') != 'Runtime.bindingCalled':
            return
        params = message.get('params', {})
        if params.get('name') != '__navehubOrientation':
            return
        try:
            mode = json.loads(params['payload']).get('mode')
        except (KeyError, ValueError, AttributeError):
            return
        if mode not in ('retrato', 'paisagem', 'query'):
            return
        error = None
        try:
            if mode != 'query':
                self.set_mode(mode)
        except (OSError, RuntimeError, KeyError):
            try:
                self.restore()
            except (OSError, RuntimeError, KeyError):
                pass
            error = 'Não foi possível ajustar a janela. Feche o DevTools e tente novamente.'
        result = json.dumps({'mode': self.mode, 'error': error}, ensure_ascii=False)
        self.ws.call('Runtime.evaluate', {
            'expression': f'window.__navehubOrientationResult?.({result})',
            'contextId': params['executionContextId'],
        })
