"""Stage 3 — Liquidity Routing Console (liquidity-routing, exchange-connectors)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..data import client, empty_state, list_to_frame, safe_get, safe_post


def render() -> None:
    st.header("Liquidity Routing Console")
    st.caption("Venue health, active child orders, and TWAP execution progress.")
    liq = client("liquidity")

    st.subheader("Create parent order")
    with st.expander("New parent order", expanded=False):
        with st.container(border=True):
            c1, c2 = st.columns(2)
            asset = c1.selectbox("asset", ["BTC", "ETH", "USDC"], key="liq_asset")
            side = c2.selectbox("side", ["buy", "sell"])
            c3, c4 = st.columns(2)
            notional = c3.number_input("notional", min_value=0.0, value=50000.0, step=1000.0)
            strategy = c4.selectbox("strategy", ["twap", "vwap", "pov"])
            c5, c6 = st.columns(2)
            client_req = c5.text_input("client_request_id", value=f"bo-ui-{pd.Timestamp.now('UTC').value}")
            quoted_mid = c6.number_input("quoted_mid", min_value=0.0, value=65000.0, step=100.0)
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

    st.divider()

    st.subheader("Parent orders")
    parent_body = safe_get(liq, "/v1/parent-orders")
    parents: list[dict] = []
    if isinstance(parent_body, dict):
        parents = parent_body.get("parent_orders", []) or parent_body.get("parents", [])
    elif isinstance(parent_body, list):
        parents = parent_body
    pdf = list_to_frame(parents)
    empty_state("parent orders", pdf)
    if not pdf.empty:
        st.dataframe(pdf, use_container_width=True, hide_index=True)

    st.subheader("Active child orders & TWAP progress")
    selected_parent: str | None = None
    if not pdf.empty and "id" in pdf.columns:
        selected_parent = st.selectbox(
            "Select parent order", options=pdf["id"].tolist(), key="liq_parent_sel"
        )
    if selected_parent:
        detail = safe_get(liq, f"/v1/parent-orders/{selected_parent}")
        if isinstance(detail, dict):
            dcol1, dcol2, dcol3 = st.columns(3)
            dcol1.metric("Status", detail.get("parent", {}).get("status", "-"))
            slicing = detail.get("slicing_progress")
            dcol2.metric("Slicing progress", slicing if slicing is not None else "-")
            dcol3.metric("Strategy", detail.get("parent", {}).get("strategy", "-"))

        fills_body = safe_get(liq, f"/v1/parent-orders/{selected_parent}/fills")
        fills = list_to_frame(
            fills_body.get("fills") if isinstance(fills_body, dict) else None
        )
        empty_state("fills", fills)
        if not fills.empty:
            st.dataframe(fills, use_container_width=True, hide_index=True)
            if {"expected_price", "fill_price"}.issubset(fills.columns):
                st.subheader("Slippage analysis")
                fills = fills.copy()
                fills["slippage_bps"] = (
                    (fills["fill_price"] - fills["expected_price"])
                    / fills["expected_price"]
                    * 10000
                )
                st.bar_chart(fills.set_index(fills.index)["slippage_bps"])

    st.subheader("Venue health (exchange-connectors)")
    st.info(
        "Exchange connectors do not expose a venue-health REST endpoint in the "
        "current API surface; venue status is inferred from parent-order fills."
    )
