import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from launcher.profile_launcher import ProfileLauncher
from main import load_config


def test_load_config_returns_required_keys():
    config = load_config()
    assert "browser" in config
    assert "homepage" in config


def test_default_homepage_lookup():
    assert ProfileLauncher.get_default_homepage("8U") == "https://8u111.com/index.html#/home"
