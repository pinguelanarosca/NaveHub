import json
from collections import deque

from launcher.browser_orientation import IFRAME_ATTACH, BrowserOrientation
from launcher.eightu_popup_blocker import _CDPWebSocket


class FakeSocket:
    def __init__(self):
        self.commands = []
        self.messages = deque()
        self.error_method = None

    def call(self, method, params=None, session_id=None):
        request_id = len(self.commands) + 1
        self.commands.append((method, params, session_id))
        result = {}
        if method == 'Browser.getWindowForTarget':
            result = {'windowId': 7, 'bounds': {
                'left': 20, 'top': 30, 'width': 600, 'height': 800, 'windowState': 'normal',
            }}
        if method == 'Browser.getVersion':
            result = {'product': 'Chrome/157.0.8103.38'}
        if method == 'Runtime.evaluate':
            result = {'result': {'value': [{'brand': 'Chromium', 'version': '157'}]}}
        if method == self.error_method:
            self.messages.append({'id': request_id, 'error': {'message': 'Session closed'}})
        else:
            self.messages.append({'id': request_id, 'result': result})
        return request_id

    def recv(self):
        return self.messages.popleft()


def test_interleaved_iframe_event_is_preserved_and_configured_before_resume():
    ws = FakeSocket()
    orientation = BrowserOrientation(ws)
    orientation.mode = 'retrato'
    event = {'method': 'Target.attachedToTarget', 'params': {'sessionId': 'game-frame'}}
    ws.messages.append(event)
    orientation.request('Page.enable')
    assert orientation.next_event() == event
    orientation.handle(event)
    commands = [command for command in ws.commands if command[2] == 'game-frame']
    assert commands[0][0] == 'Emulation.setUserAgentOverride'
    profile = commands[0][1]
    assert 'Android' in profile['userAgent']
    assert profile['userAgentMetadata']['mobile'] is True
    assert profile['userAgentMetadata']['brands'] == [{'brand': 'Chromium', 'version': '157'}]
    assert commands[1] == ('Target.setAutoAttach', IFRAME_ATTACH, 'game-frame')
    assert commands[3][0] == 'Runtime.runIfWaitingForDebugger'
    assert orientation.frames == {'game-frame'}


def test_restoring_mode_clears_mobile_in_all_sessions_and_original_window_bounds():
    ws = FakeSocket()
    orientation = BrowserOrientation(ws)
    orientation.set_mode('retrato')
    orientation.frames.update(['game', 'nested-game'])
    orientation.set_mode('paisagem')
    orientation.set_mode('paisagem')
    for session_id in ['game', 'nested-game', None]:
        assert ('Emulation.setUserAgentOverride', {'userAgent': ''}, session_id) in ws.commands
        assert ('Target.setAutoAttach', {'autoAttach': False, 'waitForDebuggerOnStart': False, 'flatten': True}, session_id) in ws.commands
    assert orientation.mode is None
    assert orientation.original is None
    assert not orientation.frames
    assert ws.commands[-1] == ('Browser.setWindowBounds', {
        'windowId': 7, 'bounds': {'left': 20, 'top': 30, 'width': 600, 'height': 800},
    }, None)


def test_closed_iframe_still_attempts_resume_and_does_not_prevent_next_event():
    ws = FakeSocket()
    ws.error_method = 'Emulation.setUserAgentOverride'
    orientation = BrowserOrientation(ws)
    orientation.mode = 'retrato'
    orientation.handle({'method': 'Target.attachedToTarget', 'params': {'sessionId': 'closed'}})
    assert ('Runtime.runIfWaitingForDebugger', {}, 'closed') in ws.commands
    assert not orientation.frames


def test_cdp_transport_places_iframe_session_id_in_message_envelope():
    ws = _CDPWebSocket('ws://127.0.0.1/test')
    packets = []
    ws._send_frame = lambda payload: packets.append(json.loads(payload))
    ws.call('Emulation.setUserAgentOverride', {'userAgent': 'test'}, session_id='game')
    assert packets == [{
        'id': 1, 'method': 'Emulation.setUserAgentOverride',
        'params': {'userAgent': 'test'}, 'sessionId': 'game',
    }]
