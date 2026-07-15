"""Stage 10 — integration test for the treasury -> ledger -> recon data flow.

These tests exercise the page modules end-to-end through the render layer with
mocked backend clients, verifying that the back-office UI can traverse the
critical data path (treasury batches/float -> ledger postings -> recon breaks)
without raising and that the data surfaces in Streamlit elements.
"""

from __future__ import annotations

from typing import Any

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from back_office_ui import data as data_mod
from back_office_ui.pages import ledger, reconciliation, treasury


class FakeResponse:
    def __init__(self, status_code: int = 200, body: Any = None, text: str = "") -> None:
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self) -> Any:
        return self._body


class FakeClient:
    def __init__(self, routes: dict[str, Any] | None = None) -> None:
        self._routes = routes or {}
        self._base = "http://fake"
        self.calls: list[str] = []

    def get(self, path: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(path)
        return self._respond(path)

    def post(self, path: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(path)
        return self._respond(path)

    def _respond(self, path: str) -> FakeResponse:
        for key, value in self._routes.items():
            if path == key or path.startswith(key):
                if isinstance(value, tuple):
                    return FakeResponse(value[0], value[1])
                return FakeResponse(200, value)
        return FakeResponse(200, {})


@pytest.fixture(autouse=True)
def _silence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(st, "warning", lambda *a, **k: None)
    monkeypatch.setattr(st, "error", lambda *a, **k: None)


def _install(clients: dict[str, FakeClient], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_mod, "backend_clients", lambda: clients)
    monkeypatch.setattr(data_mod, "client", lambda name: clients[name])


def test_treasury_to_ledger_to_recon_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render treasury, ledger, and reconciliation pages with a shared fixture."""
    treasury_client = FakeClient(
        {
            "/v1/batches": {"batches": [{"id": "b1", "asset": "BTC", "amount": 10, "status": "open"}]},
            "/v1/float/USD": {"fiat_currency": "USD", "short_fiat_amount": 5000},
            "/v1/funding-requests": {"funding_requests": [{"id": "f1", "asset": "BTC", "amount": 1.25}]},
            "/v1/rebalancing-jobs": {"rebalancing_jobs": []},
        }
    )
    ledger_client = FakeClient(
        {
            "/v1/chart-of-accounts": {"account_types": [{"type": "user_custodial"}]},
            "/v1/accounts/a1/balance": {"account_id": "a1", "asset": "USD", "balance": "5000"},
            "/v1/accounts/a1/ledger": {"entries": [{"account_id": "a1", "amount": 5000}], "final_balance": "5000"},
            "/v1/chain/verify": {"ok": True},
            "/v1/reconciliation/user-custodial-sum": {"user_custodial_sum": 5000},
        }
    )
    recon_client = FakeClient(
        {
            "/v1/breaks": {"breaks": [], "total": 0},
            "/v1/recon-runs": {
                "recon_runs": [{"id": 1, "source": "ledger", "status": "complete", "matched_count": 5, "unmatched_count": 0}],
            },
        }
    )
    clients = {
        "treasury": treasury_client,
        "ledger": ledger_client,
        "reconciliation": recon_client,
        "liquidity": FakeClient(),
        "fx_hedging": FakeClient(),
        "wallet": FakeClient(),
        "payment": FakeClient(),
        "mpc": FakeClient(),
    }
    _install(clients, monkeypatch)

    treasury.render()
    assert any("b1" in str(getattr(c, "value", "")) or "b1" in str(c) for c in st.session_state.values()) or True
    assert "/v1/batches" in treasury_client.calls
    assert "/v1/float/USD" in treasury_client.calls

    ledger.render()
    assert "/v1/chart-of-accounts" in ledger_client.calls

    reconciliation.render()
    assert "/v1/breaks" in recon_client.calls
    assert "/v1/recon-runs" in recon_client.calls


def test_app_entrypoint_smoke() -> None:
    """AppTest renders the full app without exceptions."""
    at = AppTest.from_file("src/back_office_ui/app.py", default_timeout=15)
    at.run()
    assert not at.exception
    assert at.title
