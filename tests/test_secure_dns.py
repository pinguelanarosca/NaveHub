import json
import os
import socket

import pytest

from launcher.secure_dns import CLOUDFLARE_DOH, configure_secure_dns


def test_profiles_keep_independent_state(tmp_path):
    for name in ("conta-a", "conta-b"):
        profile = tmp_path / name
        profile.mkdir()
        original = {"profile": {"info_cache": {name: {"name": name}}}, "other": name}
        state = profile / "Local State"
        state.write_text(json.dumps(original))
        assert configure_secure_dns(profile)
        updated = json.loads(state.read_text())
        assert updated.pop("dns_over_https") == CLOUDFLARE_DOH
        assert updated == original
        modified = state.stat().st_mtime_ns
        assert configure_secure_dns(profile)
        assert state.stat().st_mtime_ns == modified


def test_new_profile_and_running_profile(tmp_path):
    profile = tmp_path / "new"
    assert configure_secure_dns(profile)
    state = profile / "Local State"
    assert json.loads(state.read_text())["dns_over_https"] == CLOUDFLARE_DOH
    state.write_text('{"preserve":true}')
    (profile / "SingletonLock").symlink_to(f"{socket.gethostname()}-{os.getpid()}")
    assert not configure_secure_dns(profile)
    assert state.read_text() == '{"preserve":true}'


def test_invalid_state_preserved(tmp_path):
    state = tmp_path / "Local State"
    state.write_text('{invalid')
    with pytest.raises(ValueError):
        configure_secure_dns(tmp_path)
    assert state.read_text() == '{invalid'
