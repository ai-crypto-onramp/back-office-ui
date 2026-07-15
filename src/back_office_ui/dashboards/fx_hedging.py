"""Stage 4 — FX Hedging Monitor (fx-hedging)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..data import client, empty_state, list_to_frame, safe_get, safe_post
from . import action_button, section


def render() -> None:
    st.header("📈 FX Hedging Monitor")
    st.caption("Currency exposure, active hedge positions, PnL, and slippage.")
    fx = client("fx_hedging")

    section(
        "💱 Currency exposure",
        "Currency exposure is how much of a foreign currency we're holding (or owe). "
        "Recording an exposure tells the FX service to track that position; refreshing "
        "pulls the latest net amount from the backend.",
    )
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

    section(
        "📋 All currency exposures",
        "The current net exposure for every currency we're tracking, so you can "
        "see the full FX footprint at a glance.",
    )
    all_exp_body = safe_get(fx, "/v1/exposures")
    all_exp = list_to_frame(
        all_exp_body.get("exposures") if isinstance(all_exp_body, dict) else None
    )
    empty_state("exposures", all_exp)
    if not all_exp.empty:
        st.dataframe(all_exp, width="stretch", hide_index=True)

    section(
        "📝 Hedge execution",
        "A hedge is a trade that offsets currency exposure so we're protected if the "
        "exchange rate moves. Enter the currency, the notional amount to hedge, the "
        "tenor (how long the hedge lasts), and whether it's a spot or forward trade.",
    )
    action_button("Execute a new hedge", _hedge_dialog, key="fx_open_hedge")

    section(
        "📋 Hedge inventory",
        "Every hedge the FX service has executed, with currency, notional, tenor, "
        "status, and PnL. Filter by currency or status to focus on open vs settled "
        "positions.",
    )
    h_ccy_filter = st.text_input("currency filter (optional)", value="", key="fx_list_ccy")
    h_status_filter = st.selectbox(
        "status filter", ["", "pending", "executing", "executed", "failed"], key="fx_list_status"
    )
    h_params: dict[str, str] = {}
    if h_ccy_filter:
        h_params["currency"] = h_ccy_filter
    if h_status_filter:
        h_params["status"] = h_status_filter
    hedges_body = safe_get(fx, "/v1/hedges", params=h_params or None)
    hedges_list = list_to_frame(
        hedges_body.get("hedges") if isinstance(hedges_body, dict) else None
    )
    empty_state("hedges", hedges_list)
    if not hedges_list.empty:
        st.dataframe(hedges_list, width="stretch", hide_index=True)

    section(
        "🔍 Hedge position lookup",
        "Enter a hedge ID to inspect its status and fills.",
    )
    hedge_id = st.text_input("hedge ID", value="", key="fx_hedge_id")
    if hedge_id:
        hedge_body = safe_get(fx, f"/v1/hedges/{hedge_id}")
        if isinstance(hedge_body, dict):
            hcol1, hcol2, hcol3 = st.columns(3)
            hcol1.metric("Currency", hedge_body.get("currency", "-"))
            hcol2.metric("Notional", hedge_body.get("notional", "-"))
            hcol3.metric("Status", hedge_body.get("status", "-"))
            st.json(hedge_body)
        else:
            st.info("Hedge not found.")
    else:
        st.info("Enter a hedge ID above to view details.")

    section(
        "💰 PnL",
        "Profit and loss from hedging activity, split into realized (locked-in) and "
        "unrealized (still open) amounts, with a per-currency breakdown.",
    )
    pnl_body = safe_get(fx, "/v1/pnl")
    if isinstance(pnl_body, dict):
        total = pnl_body.get("total")
        if isinstance(total, dict):
            pcol1, pcol2, pcol3 = st.columns(3)
            pcol1.metric("Total PnL", total.get("total", 0))
            pcol2.metric("Realized", total.get("realized", 0))
            pcol3.metric("Unrealized", total.get("unrealized", 0))
        else:
            pcol1, pcol2 = st.columns(2)
            pcol1.metric("Total PnL", total if isinstance(total, (int, float)) else 0)
            pcol2.metric("Realized", pnl_body.get("realized", 0))
        by_ccy = pnl_body.get("by_currency")
        if isinstance(by_ccy, list) and by_ccy:
            st.dataframe(list_to_frame(by_ccy), width="stretch", hide_index=True)
        elif isinstance(by_ccy, dict) and by_ccy:
            st.dataframe(
                pd.DataFrame.from_dict(by_ccy, orient="index").astype(str),
                width="stretch",
            )
    else:
        st.info("No PnL data available.")

    section(
        "📉 Slippage vs benchmark",
        "Slippage measures how far the actual fill price of a hedge drifted from the "
        "benchmark rate. Pick a currency pair to see the aggregated slippage.",
    )
    pair = st.selectbox("pair", ["EUR/USD", "GBP/USD", "USD/JPY"], key="fx_pair")
    slip_body = safe_get(fx, "/v1/slippage", params={"pair": pair})
    if isinstance(slip_body, dict):
        scol1, scol2 = st.columns(2)
        scol1.metric("Pair", slip_body.get("pair", pair))
        agg = slip_body.get("aggregates")
        scol2.metric("Aggregates", "yes" if agg else "none")
        if isinstance(agg, list) and agg:
            st.dataframe(list_to_frame(agg), width="stretch", hide_index=True)
        elif isinstance(agg, dict) and agg:
            st.dataframe(
                pd.DataFrame.from_dict(agg, orient="index").astype(str),
                width="stretch",
            )
    else:
        st.info("No slippage data available.")

    section(
        "📋 Hedge execution log / settlement",
        "The settlement log records each hedge as it settles, so you can audit the "
        "execution trail end-to-end.",
    )
    set_body = safe_get(fx, "/v1/settlement")
    if isinstance(set_body, list) and set_body:
        st.dataframe(list_to_frame(set_body), width="stretch", hide_index=True)
    elif isinstance(set_body, dict) and set_body:
        st.json(set_body)
    else:
        st.info("No settlement data available.")


@st.dialog("Execute a new hedge")
def _hedge_dialog() -> None:
    """Collect hedge inputs and submit them to the FX hedging service."""
    fx = client("fx_hedging")
    h1, h2 = st.columns(2)
    h_ccy = h1.text_input("currency", value="EUR", key="fx_h_ccy")
    h_tenor = h2.selectbox("tenor", ["spot", "forward_1m", "forward_3m"], key="fx_h_tenor")
    h3, h4 = st.columns(2)
    h_notional = h3.number_input("notional", min_value=0.0, value=225000.0, step=10000.0, key="fx_h_notional")
    h_type = h4.selectbox("type", ["spot", "forward"], key="fx_h_type")
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
