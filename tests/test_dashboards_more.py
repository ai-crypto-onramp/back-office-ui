from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest
import streamlit as st

from back_office_ui import data as data_mod
from back_office_ui.dashboards import (
    fx_hedging,
    ledger,
    liquidity,
    mpc_signing,
    notification,
    pricing_quote,
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
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def get(self, path: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("GET", path, kwargs))
        return self._respond(path)

    def post(self, path: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("POST", path, kwargs))
        return self._respond(path)

    def _respond(self, path: str) -> FakeResponse:
        if path in self._routes:
            return self._coerce(self._routes[path])
        best_key = ""
        for key in self._routes:
            if path.startswith(key) and len(key) > len(best_key):
                best_key = key
        if best_key:
            return self._coerce(self._routes[best_key])
        return FakeResponse(404, {"error": "not found"}, "not found")

    @staticmethod
    def _coerce(value: Any) -> FakeResponse:
        if isinstance(value, Exception):
            raise value
        if isinstance(value, FakeResponse):
            return value
        if isinstance(value, tuple):
            return FakeResponse(value[0], value[1])
        return FakeResponse(200, value)


def _make_clients(**overrides: FakeClient) -> dict[str, FakeClient]:
    default = FakeClient()
    names = [
        "treasury", "liquidity", "fx_hedging", "ledger", "reconciliation",
        "wallet", "payment", "mpc", "pricing", "notification",
    ]
    return {name: overrides.get(name, default) for name in names}


class _SSDict:
    """A dict-like stand-in for st.session_state that is reusable across runs."""

    def __init__(self) -> None:
        self._d: dict[str, Any] = {}

    def __getitem__(self, k: str) -> Any:
        return self._d[k]

    def __setitem__(self, k: str, v: Any) -> None:
        self._d[k] = v

    def __delitem__(self, k: str) -> None:
        del self._d[k]

    def __contains__(self, k: str) -> bool:
        return k in self._d

    def get(self, k: str, default: Any = None) -> Any:
        return self._d.get(k, default)

    def setdefault(self, k: str, default: Any = None) -> Any:
        return self._d.setdefault(k, default)


@pytest.fixture(autouse=True)
def _silence(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("warning", "error", "info", "success", "caption"):
        monkeypatch.setattr(st, name, lambda *a, **k: None)
    monkeypatch.setattr(st, "rerun", lambda *a, **k: None)
    ss = _SSDict()
    monkeypatch.setattr(st, "session_state", ss)


def _patch_data(monkeypatch: pytest.MonkeyPatch, clients: dict[str, FakeClient]) -> None:
    monkeypatch.setattr(data_mod, "backend_clients", lambda: clients)
    monkeypatch.setattr(data_mod, "client", lambda name: clients[name])


def _patch_widgets(
    monkeypatch: pytest.MonkeyPatch,
    text_inputs: dict[str, str] | None = None,
    selectboxes: dict[str, Any] | None = None,
    buttons_return: bool = False,
    buttons_true_keys: set[str] | None = None,
    number_inputs: dict[str, Any] | None = None,
    checkboxes: dict[str, bool] | None = None,
) -> None:
    """Override widget return values by key.

    In bare mode (no ScriptRunContext), Streamlit widgets return their
    ``value=`` default and ignore ``st.session_state`` pre-seeds, so to drive a
    specific widget value we patch the widget method on the DeltaGenerator
    mixin class (which both ``st.text_input`` and ``column.text_input`` use).
    """
    from streamlit.elements.widgets.button import ButtonMixin
    from streamlit.elements.widgets.checkbox import CheckboxMixin
    from streamlit.elements.widgets.number_input import NumberInputMixin
    from streamlit.elements.widgets.selectbox import SelectboxMixin
    from streamlit.elements.widgets.text_widgets import TextWidgetsMixin

    text_inputs = text_inputs or {}
    selectboxes = selectboxes or {}
    number_inputs = number_inputs or {}
    checkboxes = checkboxes or {}
    buttons_true_keys = buttons_true_keys or set()

    def fake_text_input(self: Any, *args: Any, **k: Any) -> str:
        key = k.get("key")
        if key in text_inputs:
            return text_inputs[key]
        return _orig_text_input(self, *args, **k)

    def fake_selectbox(self: Any, *args: Any, **k: Any) -> Any:
        key = k.get("key")
        if key in selectboxes:
            return selectboxes[key]
        return _orig_selectbox(self, *args, **k)

    def fake_button(self: Any, *args: Any, **k: Any) -> bool:
        key = k.get("key")
        if key in buttons_true_keys:
            return True
        return buttons_return

    def fake_number_input(self: Any, *args: Any, **k: Any) -> Any:
        key = k.get("key")
        if key in number_inputs:
            return number_inputs[key]
        return _orig_number_input(self, *args, **k)

    def fake_checkbox(self: Any, *args: Any, **k: Any) -> bool:
        key = k.get("key")
        if key in checkboxes:
            return checkboxes[key]
        return _orig_checkbox(self, *args, **k)

    _orig_text_input = TextWidgetsMixin.text_input
    _orig_selectbox = SelectboxMixin.selectbox
    _orig_number_input = NumberInputMixin.number_input
    _orig_checkbox = CheckboxMixin.checkbox

    monkeypatch.setattr(TextWidgetsMixin, "text_input", fake_text_input)
    monkeypatch.setattr(SelectboxMixin, "selectbox", fake_selectbox)
    monkeypatch.setattr(ButtonMixin, "button", fake_button)
    monkeypatch.setattr(NumberInputMixin, "number_input", fake_number_input)
    monkeypatch.setattr(CheckboxMixin, "checkbox", fake_checkbox)
    # Rebind the module-level st.* references (bound methods of the DeltaGenerator
    # singleton) so they pick up the patched class method.
    _dg = st.text_input.__self__
    monkeypatch.setattr(st, "text_input", fake_text_input.__get__(_dg))
    monkeypatch.setattr(st, "selectbox", fake_selectbox.__get__(_dg))
    monkeypatch.setattr(st, "button", fake_button.__get__(_dg))
    monkeypatch.setattr(st, "number_input", fake_number_input.__get__(_dg))
    monkeypatch.setattr(st, "checkbox", fake_checkbox.__get__(_dg))


def _run(
    page_mod: Any,
    clients: dict[str, FakeClient],
    monkeypatch: pytest.MonkeyPatch,
    *,
    text_inputs: dict[str, str] | None = None,
    selectboxes: dict[str, Any] | None = None,
    buttons: bool = False,
    buttons_true_keys: set[str] | None = None,
    number_inputs: dict[str, Any] | None = None,
    checkboxes: dict[str, bool] | None = None,
    noop_action_button: bool = False,
) -> None:
    _patch_data(monkeypatch, clients)
    if (
        text_inputs
        or selectboxes
        or buttons
        or buttons_true_keys
        or number_inputs
        or checkboxes
    ):
        _patch_widgets(
            monkeypatch,
            text_inputs=text_inputs,
            selectboxes=selectboxes,
            buttons_return=buttons,
            buttons_true_keys=buttons_true_keys,
            number_inputs=number_inputs,
            checkboxes=checkboxes,
        )
    if noop_action_button:
        # When forcing all buttons True, action_button() would invoke @st.dialog
        # functions (which call open() and fail outside a script run). Neuter it.
        import back_office_ui.dashboards as dashboards_pkg

        monkeypatch.setattr(dashboards_pkg, "action_button", lambda *a, **k: None)
        # Page modules that imported action_button by name need patching too.
        if hasattr(page_mod, "action_button"):
            monkeypatch.setattr(page_mod, "action_button", lambda *a, **k: None)
    page_mod.render()


def _run_dialog(
    fn: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    text_inputs: dict[str, str] | None = None,
    selectboxes: dict[str, Any] | None = None,
    number_inputs: dict[str, Any] | None = None,
    checkboxes: dict[str, bool] | None = None,
) -> None:
    """Invoke the raw body of an @st.dialog-decorated function.

    Dialog bodies only POST when their internal ``st.button("Submit ...")``
    returns True; in bare mode Streamlit returns False, so we force buttons to
    True. Widget overrides by key are also applied via ``_patch_widgets``.
    """
    inner = getattr(fn, "__wrapped__", fn)
    _patch_widgets(
        monkeypatch,
        text_inputs=text_inputs,
        selectboxes=selectboxes,
        buttons_return=True,
        number_inputs=number_inputs,
        checkboxes=checkboxes,
    )
    inner()


# ---------------------------------------------------------------------------
# Treasury
# ---------------------------------------------------------------------------


def test_treasury_with_float_and_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(
        treasury=FakeClient(
            {
                "/v1/batches": {"batches": [{"id": "b1", "asset": "BTC", "status": "open"}]},
                "/v1/float/USD": {
                    "fiat_currency": "USD",
                    "short_fiat_amount": 5000,
                    "long_crypto_amount": 0.5,
                },
                "/v1/float": {"float_positions": [{"fiat_currency": "USD", "short_fiat_amount": 5000}]},
                "/v1/funding-requests": {"funding_requests": [{"id": "f1"}]},
                "/v1/rebalancing-jobs": {"rebalancing_jobs": [{"id": "r1"}]},
                "/v1/aggregate-orders": {"aggregate_orders": [{"id": "a1"}]},
            }
        )
    )
    _run(treasury, clients, monkeypatch)


def test_treasury_funding_dialog_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/funding-requests": (201, {"id": "fr1"})})
    clients = _make_clients(treasury=fc)
    _patch_data(monkeypatch, clients)
    _run_dialog(treasury._funding_request_dialog, monkeypatch)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/funding-requests"


# ---------------------------------------------------------------------------
# Liquidity
# ---------------------------------------------------------------------------


def test_liquidity_with_fills_slippage(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(
        liquidity=FakeClient(
            {
                "/v1/parent-orders": {"parent_orders": [{"id": "p1", "status": "executing"}]},
                "/v1/parent-orders/p1": {
                    "parent": {"id": "p1", "status": "executing", "strategy": "twap"},
                    "child_orders": [{"id": "c1", "side": "buy", "filled": 2, "status": "working"}],
                    "slicing_progress": 0.5,
                },
                "/v1/parent-orders/p1/fills": {
                    "fills": [
                        {"id": "f1", "expected_price": 65000, "fill_price": 65100},
                        {"id": "f2", "expected_price": 65000, "fill_price": 64900},
                    ]
                },
                "/v1/venue-states": {"venue_states": [{"venue": "kraken", "status": "online"}]},
            }
        )
    )
    # Pre-seed the parent id text_input value via session_state.
    st.session_state["liq_parent_id"] = "p1"
    _run(liquidity, clients, monkeypatch, text_inputs={"liq_parent_id": "p1"})


def test_liquidity_parent_dialog_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/parent-orders": (201, {"id": "po1"})})
    clients = _make_clients(liquidity=fc)
    _patch_data(monkeypatch, clients)
    _run_dialog(liquidity._parent_order_dialog, monkeypatch)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/parent-orders"


def test_liquidity_status_filter_param(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/parent-orders": {"parent_orders": []}})
    clients = _make_clients(liquidity=fc)
    _run(liquidity, clients, monkeypatch, selectboxes={"liq_list_status": "executing"})
    gets = [c for c in fc.calls if c[0] == "GET" and c[1] == "/v1/parent-orders"]
    assert gets and gets[0][2].get("params") == {"status": "executing"}


# ---------------------------------------------------------------------------
# FX hedging
# ---------------------------------------------------------------------------


def test_fx_hedging_full_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(
        fx_hedging=FakeClient(
            {
                "/v1/exposure/EUR": {"currency": "EUR", "net_amount": 250000},
                "/v1/exposures": {"exposures": [{"currency": "EUR", "net_amount": 250000}]},
                "/v1/hedges": {"hedges": [{"id": "h1", "currency": "EUR", "status": "executed"}]},
                "/v1/hedges/h1": {"id": "h1", "currency": "EUR", "notional": 225000, "status": "executed"},
                "/v1/pnl": {
                    "total": {"currency": "TOTAL", "realized": 500, "unrealized": 734, "total": 1234},
                    "by_currency": [{"currency": "EUR", "total": 1234}],
                },
                "/v1/slippage": {"pair": "EUR/USD", "aggregates": [{"b": 1}]},
                "/v1/settlement": [{"id": "s1", "status": "settled"}],
            }
        )
    )
    st.session_state["fx_hedge_id"] = "h1"
    _run(fx_hedging, clients, monkeypatch, text_inputs={"fx_hedge_id": "h1"})


def test_fx_hedging_pnl_dict_by_currency(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(
        fx_hedging=FakeClient(
            {
                "/v1/exposure/EUR": {"currency": "EUR", "net_amount": 100},
                "/v1/exposures": {"exposures": []},
                "/v1/hedges": {"hedges": []},
                "/v1/pnl": {
                    "total": 1234,
                    "realized": 500,
                    "by_currency": {"EUR": {"total": 1234}, "GBP": {"total": 0}},
                },
                "/v1/slippage": {"pair": "EUR/USD", "aggregates": {"avg": 1.0, "max": 2.0}},
                "/v1/settlement": {"id": "s1"},
            }
        )
    )
    _run(fx_hedging, clients, monkeypatch)


def test_fx_hedging_record_exposure_and_hedge_dialog(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient(
        {
            "/v1/exposure/EUR": {"currency": "EUR", "net_amount": 250000},
            "/v1/exposures": {"exposures": []},
            "/v1/hedges": {"hedges": []},
            "/v1/pnl": {},
            "/v1/slippage": {},
            "/v1/settlement": None,
            "/v1/exposure/EUR/": (200, {"ok": True}),
        }
    )
    clients = _make_clients(fx_hedging=fc)
    _patch_data(monkeypatch, clients)
    # "Record exposure" button has no key, so we use buttons=True and accept
    # that action_button dialogs will be invoked (they hit the open() error).
    # Instead, exercise the POST by directly calling the dialog body.
    _run_dialog(fx_hedging._hedge_dialog, monkeypatch)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert any(p[1] == "/v1/hedges" for p in posts)


def test_fx_hedging_hedge_dialog_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/hedges": (201, {"id": "h9"})})
    clients = _make_clients(fx_hedging=fc)
    _patch_data(monkeypatch, clients)
    _run_dialog(fx_hedging._hedge_dialog, monkeypatch)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/hedges"


def test_fx_hedging_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(fx_hedging=FakeClient({}))
    _run(fx_hedging, clients, monkeypatch)


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


def test_ledger_full_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    coa = {"account_types": [{"type": "user_custodial"}, {"type": "user_payable"}, {"type": "fee_revenue"}]}
    clients = _make_clients(
        ledger=FakeClient(
            {
                "/v1/chart-of-accounts": coa,
                "/v1/accounts": {"accounts": [{"id": "a1", "type": "user_custodial"}]},
                "/v1/postings/tx1": {
                    "posting_id": "tx1",
                    "status": "posted",
                    "entries": [{"account_id": "a1", "direction": "debit", "amount": 100}],
                },
                "/v1/postings": {"postings": [{"posting_id": "p1"}]},
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
    st.session_state["ledger_search_tx"] = "tx1"
    st.session_state["ledger_acc_id"] = "a1"
    _run(
        ledger,
        clients,
        monkeypatch,
        text_inputs={"ledger_search_tx": "tx1", "ledger_acc_id": "a1"},
    )


def test_ledger_chain_failed_and_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    # chain verify False -> error branch
    clients = _make_clients(
        ledger=FakeClient({"/v1/chain/verify": {"ok": False}})
    )
    _run(ledger, clients, monkeypatch)


def test_ledger_chain_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(ledger=FakeClient({}))
    _run(ledger, clients, monkeypatch)


def test_ledger_account_dialog_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/accounts": (201, {"id": "a9"})})
    clients = _make_clients(ledger=fc)
    _patch_data(monkeypatch, clients)
    _run_dialog(ledger._account_dialog, monkeypatch)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/accounts"


def test_ledger_posting_dialog_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/postings": (201, {"id": "p1"})})
    clients = _make_clients(ledger=fc)
    _patch_data(monkeypatch, clients)
    # Default text_input values are "" so debit/credit missing -> st.error branch (no POST).
    _run_dialog(ledger._posting_dialog, monkeypatch)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts == []


def test_ledger_posting_dialog_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/postings": (201, {"id": "p1"})})
    clients = _make_clients(ledger=fc)
    _patch_data(monkeypatch, clients)
    st.session_state["post_debit_acc"] = "a1"
    st.session_state["post_credit_acc"] = "a2"
    _run_dialog(
        ledger._posting_dialog,
        monkeypatch,
        text_inputs={"post_debit_acc": "a1", "post_credit_acc": "a2"},
    )
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/postings"


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


def _recon_full_routes() -> dict[str, Any]:
    return {
        "/v1/breaks": {
            "breaks": [
                {"id": 1, "status": "open", "source": "ledger", "created_at": "2026-07-15T00:00:00Z"},
                {"id": 2, "status": "resolved", "source": "bank", "created_at": "2026-07-19T00:00:00Z"},
            ],
            "total": 2,
        },
        "/v1/breaks/1": {"id": 1, "status": "open", "expected_amount": 100, "actual_amount": 99},
        "/v1/breaks/2": {"id": 2, "status": "resolved"},
        "/v1/recon-runs": {"recon_runs": [{"id": 10, "source": "ledger", "status": "complete"}]},
        "/v1/recon-runs/10": {"id": 10, "source": "ledger", "status": "complete"},
        "/v1/recon-runs/10/report": {"rows": [], "summary": "ok"},
        "/v1/recon-rules": {"recon_rules": [{"id": "r1", "source": "ledger"}]},
        "/v1/breaks-export": (200, "id,status\n1,open\n"),
    }


def test_reconciliation_full_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(reconciliation=FakeClient(_recon_full_routes()))
    _run(reconciliation, clients, monkeypatch)


def test_reconciliation_csv_report(monkeypatch: pytest.MonkeyPatch) -> None:
    routes = _recon_full_routes()
    routes["/v1/recon-runs/10/report"] = FakeResponse(200, "id,status\n1,open\n", text="id,status\n1,open\n")
    fc = FakeClient(routes)
    clients = _make_clients(reconciliation=fc)
    st.session_state["recon_run_id"] = "10"
    _run(reconciliation, clients, monkeypatch, text_inputs={"recon_run_id": "10"})


def test_reconciliation_export_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    routes = _recon_full_routes()
    routes["/v1/breaks-export"] = (500, {"error": "boom"})
    fc = FakeClient(routes)
    clients = _make_clients(reconciliation=fc)
    _run(reconciliation, clients, monkeypatch)


def test_reconciliation_resolve_dialog(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/breaks/1/resolve": (200, {"id": 1, "status": "resolved"})})
    clients = _make_clients(reconciliation=fc)
    _patch_data(monkeypatch, clients)
    st.session_state["recon_selected_break"] = 1
    _run_dialog(reconciliation._resolve_dialog, monkeypatch)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/breaks/1/resolve"


def test_reconciliation_resolve_dialog_no_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient()
    clients = _make_clients(reconciliation=fc)
    _patch_data(monkeypatch, clients)
    _run_dialog(reconciliation._resolve_dialog, monkeypatch)
    assert all(c[0] != "POST" for c in fc.calls)


def test_reconciliation_escalate_dialog(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/breaks/1/escalate": (200, {"id": 1, "status": "escalated"})})
    clients = _make_clients(reconciliation=fc)
    _patch_data(monkeypatch, clients)
    st.session_state["recon_selected_break"] = 1
    _run_dialog(reconciliation._escalate_dialog, monkeypatch)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/breaks/1/escalate"


def test_reconciliation_recon_run_dialog(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/recon-runs": (201, {"id": 99})})
    clients = _make_clients(reconciliation=fc)
    _patch_data(monkeypatch, clients)
    _run_dialog(reconciliation._recon_run_dialog, monkeypatch)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/recon-runs"


def test_reconciliation_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(reconciliation=FakeClient())
    _run(reconciliation, clients, monkeypatch)


# ---------------------------------------------------------------------------
# Settlement
# ---------------------------------------------------------------------------


def test_settlement_full_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(
        payment=FakeClient(
            {
                "/v1/payments": {"payments": [{"id": "pm1", "status": "captured", "rail": "card"}]},
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
    st.session_state["pay_id"] = "pm1"
    _run(settlement, clients, monkeypatch, text_inputs={"pay_id": "pm1"})


def test_settlement_status_and_rail_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/payments": {"payments": []}, "/metrics": {}})
    clients = _make_clients(payment=fc)
    st.session_state["pay_list_status"] = "captured"
    st.session_state["pay_list_rail"] = "card"
    _run(
        settlement,
        clients,
        monkeypatch,
        selectboxes={"pay_list_status": "captured", "pay_list_rail": "card"},
    )
    gets = [c for c in fc.calls if c[0] == "GET" and c[1] == "/v1/payments"]
    assert gets and gets[0][2].get("params") == {"status": "captured", "rail": "card"}


def test_settlement_payment_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(payment=FakeClient({"/v1/payments": {"payments": []}}))
    st.session_state["pay_id"] = "missing"
    _run(settlement, clients, monkeypatch, text_inputs={"pay_id": "missing"})


def test_settlement_metrics_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(payment=FakeClient({"/v1/payments": {"payments": []}, "/metrics": (500, {})}))
    _run(settlement, clients, monkeypatch)


def test_settlement_intent_dialog_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/payments/intents": (201, {"id": "pm2"})})
    clients = _make_clients(payment=fc)
    _patch_data(monkeypatch, clients)
    st.session_state["pay_3ds"] = True
    _run_dialog(settlement._intent_dialog, monkeypatch, checkboxes={"pay_3ds": True})
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/payments/intents"
    assert posts[0][2]["json"].get("three_ds_required") is True


def test_settlement_capture_dialog_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient()
    clients = _make_clients(payment=fc)
    _patch_data(monkeypatch, clients)
    st.session_state["pay_selected_id"] = "pm1"
    _run_dialog(settlement._capture_dialog, monkeypatch)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/payments/pm1/capture"


def test_settlement_capture_dialog_no_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient()
    clients = _make_clients(payment=fc)
    _patch_data(monkeypatch, clients)
    _run_dialog(settlement._capture_dialog, monkeypatch)
    assert all(c[0] != "POST" for c in fc.calls)


def test_settlement_refund_dialog_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient()
    clients = _make_clients(payment=fc)
    _patch_data(monkeypatch, clients)
    st.session_state["pay_selected_id"] = "pm1"
    _run_dialog(settlement._refund_dialog, monkeypatch)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/payments/pm1/refund"


def test_settlement_void_dialog_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient()
    clients = _make_clients(payment=fc)
    _patch_data(monkeypatch, clients)
    st.session_state["pay_selected_id"] = "pm1"
    _run_dialog(settlement._void_dialog, monkeypatch)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/payments/pm1/void"


# ---------------------------------------------------------------------------
# Wallet
# ---------------------------------------------------------------------------


def test_wallet_full_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(
        wallet=FakeClient(
            {
                "/v1/wallets": {"wallets": [{"id": "w1", "chain": "ethereum", "type": "hot", "state": "active"}]},
                "/v1/wallets/w1": {"id": "w1", "chain": "ethereum", "type": "hot", "state": "active"},
                "/v1/wallets/w1/addresses": [{"id": "addr1", "address": "0xabc"}],
                "/v1/wallets/w1/balances": [{"asset": "ETH", "amount": "1.0"}],
                "/v1/wallets/w1/funding-requests": {"funding_requests": [{"id": "fr1"}]},
                "/v1/withdrawals": {"withdrawals": [{"id": "wd1", "state": "pending"}]},
            }
        )
    )
    _run(wallet, clients, monkeypatch)


def test_wallet_balances_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(
        wallet=FakeClient(
            {
                "/v1/wallets": {"wallets": [{"id": "w1", "chain": "ethereum", "type": "hot", "state": "active"}]},
                "/v1/wallets/w1": {"id": "w1", "chain": "ethereum", "type": "hot", "state": "active"},
                "/v1/wallets/w1/addresses": [],
                "/v1/wallets/w1/balances": {"ETH": "1.0", "USDC": "100"},
                "/v1/wallets/w1/funding-requests": {"funding_requests": []},
                "/v1/withdrawals": {"withdrawals": []},
            }
        )
    )
    _run(wallet, clients, monkeypatch)


def test_wallet_create_dialog_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/wallets": (201, {"id": "w2"})})
    clients = _make_clients(wallet=fc)
    _patch_data(monkeypatch, clients)
    _run_dialog(wallet._wallet_dialog, monkeypatch)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/wallets"


def test_wallet_derive_address(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient(
        {
            "/v1/wallets": {"wallets": [{"id": "w1", "chain": "ethereum", "type": "hot", "state": "active"}]},
            "/v1/wallets/w1": {"id": "w1", "chain": "ethereum", "type": "hot", "state": "active"},
            "/v1/wallets/w1/addresses/derive": (201, {"address": "0xnew"}),
            "/v1/wallets/w1/addresses": [],
            "/v1/wallets/w1/balances": [],
            "/v1/wallets/w1/funding-requests": {"funding_requests": []},
            "/v1/withdrawals": {"withdrawals": []},
        }
    )
    clients = _make_clients(wallet=fc)
    _patch_data(monkeypatch, clients)
    _run(wallet, clients, monkeypatch, buttons=True, noop_action_button=True)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert any(p[1] == "/v1/wallets/w1/addresses/derive" for p in posts)


def test_wallet_state_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient(
        {
            "/v1/wallets": {"wallets": []},
            "/v1/withdrawals": {"withdrawals": []},
        }
    )
    clients = _make_clients(wallet=fc)
    st.session_state["wl_wd_state"] = "pending"
    _run(wallet, clients, monkeypatch, selectboxes={"wl_wd_state": "pending"})
    gets = [c for c in fc.calls if c[0] == "GET" and c[1] == "/v1/withdrawals"]
    assert gets and gets[0][2].get("params") == {"state": "pending"}


# ---------------------------------------------------------------------------
# MPC signing
# ---------------------------------------------------------------------------


def test_mpc_signing_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(mpc=FakeClient({}))
    _run(mpc_signing, clients, monkeypatch)


def test_mpc_signing_webhook_probe_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient(
        {
            "/healthz": {"status": "ok"},
            "/v1/custody/webhook": (200, {"ok": True}),
        }
    )
    clients = _make_clients(mpc=fc)
    _patch_data(monkeypatch, clients)
    _run(mpc_signing, clients, monkeypatch, buttons=True, noop_action_button=True)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert any(p[1] == "/v1/custody/webhook" for p in posts)


def test_mpc_signing_webhook_probe_text(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient(
        {
            "/healthz": {"status": "ok"},
            "/v1/custody/webhook": FakeResponse(501, body=None, text="not implemented"),
        }
    )
    clients = _make_clients(mpc=fc)
    _patch_data(monkeypatch, clients)
    _run(mpc_signing, clients, monkeypatch, buttons=True, noop_action_button=True)


def test_mpc_signing_webhook_probe_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient(
        {
            "/healthz": {"status": "ok"},
            "/v1/custody/webhook": ConnectionError("down"),
        }
    )
    clients = _make_clients(mpc=fc)
    _patch_data(monkeypatch, clients)
    _run(mpc_signing, clients, monkeypatch, buttons=True, noop_action_button=True)


# ---------------------------------------------------------------------------
# Pricing quote
# ---------------------------------------------------------------------------


def test_pricing_quote_full_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(
        pricing=FakeClient(
            {
                "/v1/quotes": {
                    "quotes": [
                        {
                            "quote_id": "q1", "from": "USD", "to": "BTC", "amount": "100",
                            "rate": "0.00001625", "spread_bps": 80, "fee": "2.50",
                            "fee_currency": "USD", "total": "97.50", "crypto_amount": "0.00808125",
                            "user_tier": "tier_2", "side": "buy", "status": "open",
                            "source_venue": "kraken", "created_at": "2026-07-16T00:00:00Z",
                            "expires_at": "2026-07-16T00:00:30Z",
                        }
                    ]
                },
                "/v1/quotes/q1": {"quote_id": "q1", "from": "USD", "to": "BTC", "status": "open"},
                "/v1/fee-schedules": {
                    "fee_schedules": [
                        {"id": 1, "user_tier": "tier_1", "asset": "BTC", "side": "buy", "spread_bps": 80, "enabled": True}
                    ]
                },
                "/v1/rate-sources": {
                    "rate_sources": [{"name": "kraken", "priority": 0, "enabled": True, "weight": 2}]
                },
                "/v1/audit-events": {"events": [{"type": "quote.issued", "quote_id": "q1"}]},
                "/internal/v1/fee-schedules/reload": (200, {"ok": True}),
            }
        )
    )
    st.session_state["pq_lookup_id"] = "q1"
    _run(pricing_quote, clients, monkeypatch, text_inputs={"pq_lookup_id": "q1"})


def test_pricing_quote_reload_button(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient(
        {
            "/v1/quotes": {"quotes": []},
            "/v1/fee-schedules": {"fee_schedules": []},
            "/v1/rate-sources": {"rate_sources": []},
            "/v1/audit-events": {"events": []},
            "/internal/v1/fee-schedules/reload": (200, {"ok": True}),
        }
    )
    clients = _make_clients(pricing=fc)
    _patch_data(monkeypatch, clients)
    _run(pricing_quote, clients, monkeypatch, buttons=True, noop_action_button=True)
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert any(p[1] == "/internal/v1/fee-schedules/reload" for p in posts)


def test_pricing_quote_quote_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(pricing=FakeClient({}))
    st.session_state["pq_lookup_id"] = "nope"
    _run(pricing_quote, clients, monkeypatch, text_inputs={"pq_lookup_id": "nope"})


def test_pricing_quote_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(pricing=FakeClient())
    _run(pricing_quote, clients, monkeypatch)


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------


def test_notification_full_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(
        notification=FakeClient(
            {
                "/v1/notifications": {
                    "notifications": [
                        {
                            "id": "n1", "event_type": "tx.confirmed", "channel": "email",
                            "recipient": "user@example.com", "user_id": "usr_1",
                            "template_id": "tx_confirmed_en", "status": "delivered",
                            "traffic_class": "transactional", "locale": "en",
                            "created_at": "2026-07-16T00:00:00Z", "sent_at": "2026-07-16T00:00:01Z",
                        }
                    ]
                },
                "/v1/notifications/n1": {
                    "notification": {"id": "n1", "event_type": "tx.confirmed", "channel": "email",
                                     "recipient": "u@example.com", "status": "delivered", "template_id": "tx_confirmed_en"},
                    "attempts": [{"channel": "email", "provider": "ses", "status": "delivered", "attempt_no": 1}],
                },
                "/v1/notifications/n1/status": {
                    "notification_id": "n1", "overall_status": "delivered",
                    "channels": {"email": {"status": "delivered", "attempts": 1, "last_error": None}},
                },
                "/v1/preferences": {"preferences": [{"user_id": "usr_1", "locale": "en", "channels": {"email": True}}]},
                "/v1/preferences/usr_1": {
                    "user_id": "usr_1", "locale": "en",
                    "channels": {"email": True, "sms": False, "push": True, "webhook": True},
                    "quiet_hours": {"start": "22:00", "end": "07:00"},
                },
                "/v1/webhooks/partners": {
                    "webhooks": [{"id": "wh1", "url": "https://partner.example/hook", "status": "active", "batch_window": 1000}]
                },
                "/v1/audit-events": {
                    "events": [{"type": "notification.requested", "notification_id": "n1", "channel": "email",
                                "status": "pending", "created_at": "2026-07-16T00:00:00Z"}]
                },
            }
        )
    )
    st.session_state["nf_lookup_id"] = "n1"
    st.session_state["nf_pref_user"] = "usr_1"
    _run(
        notification,
        clients,
        monkeypatch,
        text_inputs={"nf_lookup_id": "n1", "nf_pref_user": "usr_1"},
    )


def test_notification_lookup_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(notification=FakeClient({}))
    st.session_state["nf_lookup_id"] = "missing"
    _run(notification, clients, monkeypatch, text_inputs={"nf_lookup_id": "missing"})


def test_notification_preferences_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(notification=FakeClient({}))
    st.session_state["nf_pref_user"] = "usr_new"
    _run(notification, clients, monkeypatch, text_inputs={"nf_pref_user": "usr_new"})


def test_notification_preferences_dialog_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/preferences/usr_1": (200, {"ok": True})})
    clients = _make_clients(notification=fc)
    _patch_data(monkeypatch, clients)
    st.session_state["nf_pref_user_editing"] = "usr_1"
    st.session_state["nf_pref_qs"] = "22:00"
    st.session_state["nf_pref_qe"] = "07:00"
    _run_dialog(
        notification._preferences_dialog,
        monkeypatch,
        text_inputs={"nf_pref_qs": "22:00", "nf_pref_qe": "07:00"},
    )
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/preferences/usr_1"
    assert "quiet_hours" in posts[0][2]["json"]


def test_notification_preferences_dialog_no_user(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient()
    clients = _make_clients(notification=fc)
    _patch_data(monkeypatch, clients)
    _run_dialog(notification._preferences_dialog, monkeypatch)
    assert all(c[0] != "POST" for c in fc.calls)


def test_notification_webhook_dialog_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/webhooks/partners": (201, {"id": "wh2"})})
    clients = _make_clients(notification=fc)
    _patch_data(monkeypatch, clients)
    st.session_state["nf_wh_secret"] = "s3cr3t"
    _run_dialog(
        notification._webhook_dialog,
        monkeypatch,
        text_inputs={"nf_wh_secret": "s3cr3t"},
    )
    posts = [c for c in fc.calls if c[0] == "POST"]
    assert posts and posts[0][1] == "/v1/webhooks/partners"


def test_notification_webhook_dialog_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = FakeClient({"/v1/webhooks/partners": (201, {"id": "wh2"})})
    clients = _make_clients(notification=fc)
    _patch_data(monkeypatch, clients)
    st.session_state["nf_wh_secret"] = ""
    _run_dialog(
        notification._webhook_dialog,
        monkeypatch,
        text_inputs={"nf_wh_secret": ""},
    )
    assert all(c[0] != "POST" for c in fc.calls)


def test_notification_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _make_clients(notification=FakeClient())
    _run(notification, clients, monkeypatch)


# ---------------------------------------------------------------------------
# dashboards.__init__ helper (action_button truthy branch)
# ---------------------------------------------------------------------------


def test_action_button_triggers_dialog(monkeypatch: pytest.MonkeyPatch) -> None:
    from back_office_ui.dashboards import action_button

    called = {"n": 0}

    def fake_dialog() -> None:
        called["n"] += 1

    monkeypatch.setattr(st, "button", lambda *a, **k: True)
    action_button("label", fake_dialog, key="x")
    assert called["n"] == 1


def test_action_button_does_not_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    from back_office_ui.dashboards import action_button

    called = {"n": 0}

    def fake_dialog() -> None:
        called["n"] += 1

    monkeypatch.setattr(st, "button", lambda *a, **k: False)
    action_button("label", fake_dialog, key="x")
    assert called["n"] == 0


def test_section_with_icon(monkeypatch: pytest.MonkeyPatch) -> None:
    from back_office_ui.dashboards import section

    section("Title", "explanation", icon="💡")


# ---------------------------------------------------------------------------
# data.py: extra coverage
# ---------------------------------------------------------------------------


def test_safe_get_non_json(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient({"/v1/x": FakeResponse(200, body=None)})
    monkeypatch.setattr(st, "warning", lambda *a, **k: None)
    assert data_mod.safe_get(fake, "/v1/x") is None


def test_safe_post_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient({"/v1/x": (500, {"error": "boom"})})
    monkeypatch.setattr(st, "warning", lambda *a, **k: None)
    assert data_mod.safe_post(fake, "/v1/x", json={"a": 1}) is None


def test_safe_post_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient({"/v1/x": ConnectionError("down")})
    monkeypatch.setattr(st, "warning", lambda *a, **k: None)
    assert data_mod.safe_post(fake, "/v1/x") is None


def test_safe_post_non_json(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient({"/v1/x": FakeResponse(200, body=None)})
    monkeypatch.setattr(st, "warning", lambda *a, **k: None)
    assert data_mod.safe_post(fake, "/v1/x") is None


def test_list_to_frame_list_of_strings_column() -> None:
    df = data_mod.list_to_frame([{"tags": ["a", "b"]}, {"tags": ["c"]}])
    assert "tags" in df.columns
    assert df["tags"].iloc[0] == ["a", "b"]


def test_list_to_frame_mixed_object_column() -> None:
    df = data_mod.list_to_frame([{"v": {"a": 1}}, {"v": [1, 2]}])
    assert df["v"].dtype == object


def test_backend_clients_caches_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    ss = _SSDict()
    monkeypatch.setattr(st, "session_state", ss)
    monkeypatch.setattr(
        "back_office_ui.data.BackendClient",
        lambda url, timeout=5.0: object(),
    )
    c1 = data_mod.backend_clients()
    assert "settings" in ss._d
    c2 = data_mod.backend_clients()
    assert "treasury" in c1 and "treasury" in c2


def test_client_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    ss = _SSDict()
    monkeypatch.setattr(st, "session_state", ss)
    monkeypatch.setattr(
        "back_office_ui.data.BackendClient",
        lambda url, timeout=5.0: {"base": url},
    )
    assert data_mod.client("ledger") == {"base": "http://ledger-accounting:8080"}


def test_health_check_ok() -> None:
    class C:
        def get(self, path: str, **kwargs: Any) -> FakeResponse:
            return FakeResponse(200, {"status": "ok"})

    assert data_mod.health_check(C()) is True


def test_health_check_error() -> None:
    class C:
        def get(self, path: str, **kwargs: Any) -> FakeResponse:
            raise ConnectionError("down")

    assert data_mod.health_check(C()) is False


def test_health_check_500() -> None:
    class C:
        def get(self, path: str, **kwargs: Any) -> FakeResponse:
            return FakeResponse(500, {})

    assert data_mod.health_check(C()) is False


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_settlement_aging_buckets() -> None:
    from back_office_ui.dashboards.settlement import _aging_bucket

    assert _aging_bucket(None) == "unknown"
    assert _aging_bucket("not-a-date") == "unknown"
    recent = pd.Timestamp.now("UTC").isoformat()
    assert _aging_bucket(recent) == "0-1h"
    old = (pd.Timestamp.now("UTC") - pd.Timedelta(hours=10)).isoformat()
    assert _aging_bucket(old) == "4-24h"
    very_old = (pd.Timestamp.now("UTC") - pd.Timedelta(hours=48)).isoformat()
    assert _aging_bucket(very_old) == "24h+"


def test_reconciliation_aging_buckets() -> None:
    from back_office_ui.dashboards.reconciliation import _aging_bucket

    assert _aging_bucket(None) == "unknown"
    assert _aging_bucket("garbage") == "unknown"
    recent = (pd.Timestamp.now("UTC") - pd.Timedelta(hours=2)).isoformat()
    assert _aging_bucket(recent) == "1-4h"
