from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from back_office_ui import data as data_mod
from back_office_ui.data import empty_state, list_to_frame


class FakeResponse:
    def __init__(self, status_code: int = 200, body: Any = None, text: str = "") -> None:
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self) -> Any:
        return self._body

    @property
    def content(self) -> bytes:
        if isinstance(self._body, str):
            return self._body.encode()
        return str(self._body).encode()


class FakeClient:
    """In-memory stand-in for BackendClient with scripted responses."""

    def __init__(self, routes: dict[str, Any] | None = None) -> None:
        self._routes = routes or {}
        self._base = "http://fake"
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def get(self, path: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("GET", path, kwargs))
        return self._respond(path)

    def post(self, path: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("POST", path, kwargs))
        return self._respond(path)

    def _respond(self, path: str) -> FakeResponse:
        for key, value in self._routes.items():
            if path == key or path.startswith(key):
                if isinstance(value, Exception):
                    raise value
                if isinstance(value, FakeResponse):
                    return value
                if isinstance(value, tuple):
                    return FakeResponse(value[0], value[1])
                return FakeResponse(200, value)
        return FakeResponse(404, {"error": "not found"}, "not found")


def _patch_clients(monkeypatch: pytest.MonkeyPatch, clients: dict[str, FakeClient]) -> None:
    def fake_backend_clients() -> dict[str, Any]:
        return clients

    monkeypatch.setattr(data_mod, "backend_clients", fake_backend_clients)


def test_list_to_frame_empty() -> None:
    assert list_to_frame(None).empty
    assert list_to_frame([]).empty


def test_list_to_frame_filled() -> None:
    df = list_to_frame([{"a": 1}, {"a": 2}])
    assert list_to_frame([{"a": 1}, {"a": 2}]).equals(df)
    assert len(df) == 2


def test_empty_state_shows_info() -> None:
    import streamlit as st

    called = {"info": False}
    orig = st.info

    def fake_info(*args: Any, **kwargs: Any) -> None:
        called["info"] = True

    monkey = pytest.MonkeyPatch()
    monkey.setattr(st, "info", fake_info)
    try:
        empty_state("things", pd.DataFrame())
        assert called["info"] is True
    finally:
        monkey.setattr(st, "info", orig)


def test_safe_get_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient({"/v1/x": {"ok": True}})
    assert data_mod.safe_get(fake, "/v1/x") == {"ok": True}


def test_safe_get_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient({"/v1/x": (500, {"error": "boom"})})
    monkeypatch.setattr("streamlit.warning", lambda *a, **k: None)
    assert data_mod.safe_get(fake, "/v1/x") is None


def test_safe_get_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient({"/v1/x": ConnectionError("down")})
    monkeypatch.setattr("streamlit.warning", lambda *a, **k: None)
    assert data_mod.safe_get(fake, "/v1/x") is None


def test_safe_post_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient({"/v1/x": {"created": True}})
    assert data_mod.safe_post(fake, "/v1/x", json={"a": 1}) == {"created": True}
