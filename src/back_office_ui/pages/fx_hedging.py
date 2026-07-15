"""Stage 4 — FX Hedging Monitor (fx-hedging)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..data import client, empty_state, list_to_frame, safe_get, safe_post


def render() -> None:
    st.header("FX Hedging Monitor")
    st.caption("Currency exposure, active hedge positions, PnL, and slippage.")
    fx = client("fx_hedging")

    st.subheader("Currency exposure")
    ccy = st.selectbox("Currency", ["EUR", "GBP", "JPY", "USD"], key="fx_ccy")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Record exposure", help="POST /v1/exposure/{ccy}"):
            result = safe_post(fx, f"/v1/exposure/{ccy}", json={"amount": 250000})
            if result is not None:
                st.success(f"Exposure updated: {result}")
    with col2:
        if st.button("Refresh exposure"):
            st.rerun()

    exp_body = safe_get(fx, f"/v1/exposure/{ccy}")
    if isinstance(exp_body, dict):
        ecol1, ecol2 = st.columns(2)
        ecol1.metric("Net amount", exp_body.get("net_amount", 0))
        ecol2.metric("Currency", exp_body.get("currency", ccy))
    else:
        st.info("No exposure data available.")

    st.subheader("Hedge execution")
    with st.expander("Execute a new hedge", expanded=False):
        with st.container(border=True):
            h1, h2 = st.columns(2)
            h_ccy = h1.text_input("currency", value="EUR")
            h_tenor = h2.selectbox("tenor", ["spot", "forward_1m", "forward_3m"])
            h3, h4 = st.columns(2)
            h_notional = h3.number_input("notional", min_value=0.0, value=225000.0, step=10000.0)
            h_type = h4.selectbox("type", ["spot", "forward"])
            if st.button("Submit hedge", type="primary"):
                payload = {
                    "currency": h_ccy,
                    "notional": float(h_notional),
                    "tenor": h_tenor,
                    "type": h_type,
                }
                result = safe_post(fx, "/v1/hedges", json=payload)
                if result is not None:
                    st.success(f"Hedge executed: {result}")

    st.subheader("Active hedge positions")
    hedge_body = safe_get(fx, "/v1/hedges")
    hedges: list[dict] = []
    if isinstance(hedge_body, dict):
        hedges = hedge_body.get("hedges", []) or hedge_body.get("items", [])
    elif isinstance(hedge_body, list):
        hedges = hedge_body
    hdf = list_to_frame(hedges)
    empty_state("hedges", hdf)
    if not hdf.empty:
        st.dataframe(hdf, use_container_width=True, hide_index=True)
        if {"notional", "quoted_rate"}.issubset(hdf.columns):
            st.caption("PnL is derived from mark vs entry rate — see PnL endpoint below.")

    st.subheader("PnL")
    pnl_body = safe_get(fx, "/v1/pnl")
    if isinstance(pnl_body, dict):
        pcol1, pcol2 = st.columns(2)
        pcol1.metric("Total PnL", pnl_body.get("total", 0))
        pcol2.metric("Currencies", len(pnl_body.get("by_currency", {}) or {}))
        by_ccy = pnl_body.get("by_currency")
        if isinstance(by_ccy, dict) and by_ccy:
            st.dataframe(
                pd.DataFrame.from_dict(by_ccy, orient="index"),
                use_container_width=True,
            )
        elif isinstance(by_ccy, list) and by_ccy:
            st.dataframe(list_to_frame(by_ccy), use_container_width=True, hide_index=True)
    else:
        st.info("No PnL data available.")

    st.subheader("Slippage vs benchmark")
    pair = st.selectbox("pair", ["EUR/USD", "GBP/USD", "USD/JPY"], key="fx_pair")
    slip_body = safe_get(fx, "/v1/slippage", params={"pair": pair})
    if isinstance(slip_body, dict):
        scol1, scol2 = st.columns(2)
        scol1.metric("Pair", slip_body.get("pair", pair))
        agg = slip_body.get("aggregates")
        scol2.metric("Aggregates", "yes" if agg else "none")
        if isinstance(agg, list) and agg:
            st.dataframe(list_to_frame(agg), use_container_width=True, hide_index=True)
        elif isinstance(agg, dict) and agg:
            st.dataframe(
                pd.DataFrame.from_dict(agg, orient="index"),
                use_container_width=True,
            )
    else:
        st.info("No slippage data available.")

    st.subheader("Hedge execution log / settlement")
    set_body = safe_get(fx, "/v1/settlement")
    if isinstance(set_body, list) and set_body:
        st.dataframe(list_to_frame(set_body), use_container_width=True, hide_index=True)
    elif isinstance(set_body, dict) and set_body:
        st.json(set_body)
    else:
        st.info("No settlement data available.")
