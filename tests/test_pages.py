from __future__ import annotations

from typing import Any

import pytest
import streamlit as st

from back_office_ui import data as data_mod
from back_office_ui.dashboards import (
    fx_hedging,
    ledger,
    liquidity,
    mpc_signing,
    reconciliation,
    settlement,
    treasury,
    wallet,
)


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
    def __init__(self, routes: dict[str, Any] | None = None) -> None:
        self._routes = routes or {}
        self._base = "http://fake"

    def get(self, path: str, **kwargs: Any) -> FakeResponse:
        return self._respond(path)

    def post(self, path: str, **kwargs: Any) -> FakeResponse:
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
        return FakeResponse(200, {})


def _make_clients(**overrides: FakeClient) -> dict[str, FakeClient]:
    default = FakeClient()
    names = ["treasury", "liquidity", "fx_hedging", "ledger", "reconciliation", "wallet", "payment", "mpc"]
    return {name: overrides.get(name, default) for name in names}


@pytest.fixture(autouse=True)
def _silence_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(st, "warning", lambda *a, **k: None)
    monkeypatch.setattr(st, "error", lambda *a, **k: None)


def _run_page(page_mod: Any, clients: dict[str, FakeClient], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_mod, "backend_clients", lambda: clients)
    monkeypatch.setattr(data_mod, "client", lambda name: clients[name])
    page_mod.render()


def test_treasury_page_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(
        treasury=FakeClient(
            {
                "/v1/batches": {"batches": [{"id": "b1", "asset": "BTC", "amount": 10, "status": "open"}]},
                "/v1/float/USD": {"fiat_currency": "USD", "short_fiat_amount": 5000},
                "/v1/funding-requests": {"funding_requests": [{"id": "f1", "asset": "BTC", "amount": 1.25}]},
                "/v1/rebalancing-jobs": {"rebalancing_jobs": [{"id": "r1", "status": "pending"}]},
            }
        )
    )
    _run_page(treasury, clients, monkeypatch)


def test_treasury_page_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _run_page(treasury, _make_clients(treasury=FakeClient()), monkeypatch)


def test_liquidity_page_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(
        liquidity=FakeClient(
            {
                "/v1/parent-orders/po1": {
                    "parent": {"id": "po1", "status": "pending", "strategy": "twap"},
                    "child_orders": [{"id": "c1", "venue": "kraken", "side": "buy", "amount": 5, "filled": 2, "status": "working"}],
                    "slicing_progress": 0.4,
                },
                "/v1/parent-orders/po1/fills": {
                    "fills": [{"id": "c1", "expected_price": 65000, "fill_price": 65100}]
                },
            }
        )
    )
    _run_page(liquidity, clients, monkeypatch)


def test_liquidity_page_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _run_page(liquidity, _make_clients(liquidity=FakeClient()), monkeypatch)


def test_fx_hedging_page_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(
        fx_hedging=FakeClient(
            {
                "/v1/exposure/EUR": {"currency": "EUR", "net_amount": 250000},
                "/v1/hedges/h1": {"id": "h1", "currency": "EUR", "notional": 225000, "quoted_rate": 1.1, "status": "executed"},
                "/v1/pnl": {"total": {"currency": "TOTAL", "realized": 500, "unrealized": 734, "total": 1234}, "by_currency": [{"currency": "EUR", "total": 1234}]},
                "/v1/slippage": {"pair": "EUR/USD", "aggregates": [{"b": 1}]},
                "/v1/settlement": [{"id": "s1"}],
            }
        )
    )
    _run_page(fx_hedging, clients, monkeypatch)


def test_fx_hedging_page_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _run_page(fx_hedging, _make_clients(fx_hedging=FakeClient()), monkeypatch)


def test_ledger_page_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    coa = {"account_types": [{"type": "user_custodial"}, {"type": "user_payable"}]}
    clients = _make_clients(
        ledger=FakeClient(
            {
                "/v1/chart-of-accounts": coa,
                "/v1/postings/tx1": {
                    "posting_id": "tx1",
                    "status": "posted",
                    "entries": [{"account_id": "a1", "direction": "debit", "amount": 100}],
                },
                "/v1/accounts/a1/balance": {"account_id": "a1", "asset": "USD", "balance": "100"},
                "/v1/accounts/a1/ledger": {
                    "entries": [{"account_id": "a1", "amount": 100}],
                    "final_balance": "100",
                },
                "/v1/chain/verify": {"ok": True},
                "/v1/reconciliation/user-custodial-sum": {"user_custodial_sum": 1000},
            }
        )
    )
    _run_page(ledger, clients, monkeypatch)


def test_ledger_page_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _run_page(ledger, _make_clients(ledger=FakeClient()), monkeypatch)


def test_reconciliation_page_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    breaks = [{"id": 1, "status": "open", "source": "ledger", "created_at": "2026-07-15T00:00:00Z"}]
    clients = _make_clients(
        reconciliation=FakeClient(
            {
                "/v1/breaks": {"breaks": breaks, "total": 1},
                "/v1/breaks/1": {"id": 1, "status": "open", "expected_amount": 100, "actual_amount": 99},
                "/v1/recon-runs/10": {"id": 10, "source": "ledger", "status": "complete", "matched_count": 5, "unmatched_count": 1},
            }
        )
    )
    _run_page(reconciliation, clients, monkeypatch)


def test_reconciliation_page_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _run_page(reconciliation, _make_clients(reconciliation=FakeClient()), monkeypatch)


def test_wallet_page_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    wallets = [{"id": "w1", "chain": "ethereum", "type": "hot", "state": "active"}]
    clients = _make_clients(
        wallet=FakeClient(
            {
                "/v1/wallets": {"wallets": wallets},
                "/v1/wallets/w1": {"id": "w1", "chain": "ethereum", "type": "hot", "state": "active"},
                "/v1/wallets/w1/balances": [],
            }
        )
    )
    _run_page(wallet, clients, monkeypatch)


def test_wallet_page_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _run_page(wallet, _make_clients(wallet=FakeClient()), monkeypatch)


def test_settlement_page_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(
        payment=FakeClient(
            {
                "/v1/payments/pm1": {
                    "id": "pm1",
                    "status": "captured",
                    "rail": "card",
                    "history": [{"status": "authorized"}],
                },
                "/metrics": {"transitions": [{"a": 1}], "webhook_backlog": 0},
            }
        )
    )
    _run_page(settlement, clients, monkeypatch)


def test_settlement_page_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _run_page(settlement, _make_clients(payment=FakeClient()), monkeypatch)


def test_mpc_signing_page_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    _run_page(mpc_signing, _make_clients(mpc=FakeClient({"/healthz": {"status": "ok"}})), monkeypatch)


def test_mpc_signing_page_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _run_page(mpc_signing, _make_clients(mpc=FakeClient()), monkeypatch)
