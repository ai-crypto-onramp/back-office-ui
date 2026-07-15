"""Stage 3 — Liquidity Routing Console (liquidity-routing, exchange-connectors)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..data import client, empty_state, list_to_frame, safe_get, safe_post
from . import action_button, section


def render() -> None:
    st.header("🔄 Liquidity Routing Console")
    st.caption("Venue health, active child orders, and TWAP execution progress.")
    liq = client("liquidity")

    section(
        "📝 Create parent order",
        "A parent order is a large order that the liquidity router splits into "
        "smaller child orders and executes over time using a strategy like TWAP, "
        "VWAP, or POV. Choose the asset, direction (buy/sell), total size, strategy, "
        "and a reference price so the router can measure slippage.",
    )
    action_button("New parent order", _parent_order_dialog, key="liq_open_parent")

    st.divider()

    section(
        "🔍 Parent order lookup",
        "The liquidity-routing API exposes parent orders by ID, not as a list. "
        "Enter a parent order ID to inspect its status, child orders, and fills.",
    )
    parent_id = st.text_input("parent order ID", value="", key="liq_parent_id")
    if parent_id:
        detail = safe_get(liq, f"/v1/parent-orders/{parent_id}")
        if isinstance(detail, dict):
            parent = detail.get("parent", {})
            dcol1, dcol2, dcol3 = st.columns(3)
            dcol1.metric("Status", parent.get("status", "-"))
            slicing = detail.get("slicing_progress")
            dcol2.metric("Slicing progress", slicing if slicing is not None else "-")
            dcol3.metric("Strategy", parent.get("strategy", "-"))

            children = detail.get("child_orders")
            cdf = list_to_frame(children if isinstance(children, list) else None)
            empty_state("child orders", cdf)
            if not cdf.empty:
                st.dataframe(cdf, width="stretch", hide_index=True)

            fills_body = safe_get(liq, f"/v1/parent-orders/{parent_id}/fills")
            fills = list_to_frame(
                fills_body.get("fills") if isinstance(fills_body, dict) else None
            )
            empty_state("fills", fills)
            if not fills.empty:
                st.dataframe(fills, width="stretch", hide_index=True)
                if {"expected_price", "fill_price"}.issubset(fills.columns):
                    st.subheader("📊 Slippage analysis")
                    fills = fills.copy()
                    fills["slippage_bps"] = (
                        (fills["fill_price"] - fills["expected_price"])
                        / fills["expected_price"]
                        * 10000
                    )
                    st.bar_chart(fills.set_index(fills.index)["slippage_bps"])

    section(
        "🏬 Venue health (exchange-connectors)",
        "Venue health summarises whether each connected exchange (e.g. Kraken, "
        "Coinbase) is reachable and accepting orders. The exchange connectors "
        "don't yet expose a dedicated health endpoint, so venue status is inferred "
        "from parent-order fills here.",
    )
    st.info(
        "Exchange connectors do not expose a venue-health REST endpoint in the "
        "current API surface; venue status is inferred from parent-order fills."
    )


@st.dialog("New parent order")
def _parent_order_dialog() -> None:
    """Collect parent-order inputs and submit them to the liquidity router."""
    liq = client("liquidity")
    c1, c2 = st.columns(2)
    asset = c1.selectbox("asset", ["BTC", "ETH", "USDC"], key="liq_asset")
    side = c2.selectbox("side", ["buy", "sell"], key="liq_side")
    c3, c4 = st.columns(2)
    notional = c3.number_input("notional", min_value=0.0, value=50000.0, step=1000.0, key="liq_notional")
    strategy = c4.selectbox("strategy", ["twap", "vwap", "pov"], key="liq_strategy")
    c5, c6 = st.columns(2)
    client_req = c5.text_input(
        "client_request_id", value=f"bo-ui-{pd.Timestamp.now('UTC').value}", key="liq_creq"
    )
    quoted_mid = c6.number_input("quoted_mid", min_value=0.0, value=65000.0, step=100.0, key="liq_mid")
    if st.button("Submit parent order", type="primary"):
        payload = {
            "asset": asset,
            "side": side,
            "notional": float(notional),
            "strategy": strategy,
            "client_request_id": client_req,
            "quoted_mid": float(quoted_mid),
        }
        result = safe_post(liq, "/v1/parent-orders", json=payload)
        if result is not None:
            st.success(f"Parent order created: {result}")
