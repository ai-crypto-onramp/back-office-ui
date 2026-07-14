from __future__ import annotations

import pytest

from back_office_ui.config import Settings, get_settings


def test_default_settings() -> None:
    s = get_settings()
    assert isinstance(s, Settings)
    assert s.port == 8501


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STREAMLIT_SERVER_PORT", "9999")
    s = get_settings()
    assert s.port == 9999


def test_settings_from_env_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TREASURY_URL", "http://treasury.example:9000")
    s = get_settings()
    assert s.treasury_url == "http://treasury.example:9000"
