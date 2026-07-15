"""Stage 2 — Treasury Dashboard (treasury-orchestration)."""

from __future__ import annotations

import streamlit as st

from ..data import client, empty_state, list_to_frame, safe_get, safe_post


def render() -> None:
    st.header("Treasury Dashboard")
    st.caption("Aggregate buy-order batches, float exposure, and wallet funding.")
    treas = client("treasury")

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Service", "treasury-orchestration")
    col_b.metric("Batches endpoint", "/v1/batches")
    col_c.metric("Float endpoint", "/v1/float/{ccy}")

    st.subheader("Buy-order batches")
    batches_body = safe_get(treas, "/v1/batches")
    batches = list_to_frame(batches_body.get("batches") if isinstance(batches_body, dict) else None)
    if batches.empty:
        st.info("No batches yet — batches are produced by the tx.completed event consumer.")
    else:
        st.dataframe(batches, use_container_width=True, hide_index=True)

    st.subheader("Batch creation")
    with st.expander("Create a funding request (aggregation input)", expanded=False):
        with st.container(border=True):
            wallet_id = st.text_input("wallet_id", value="bo-ui-wallet")
            asset = st.selectbox("asset", ["BTC", "ETH", "USDC", "USD"], index=0)
            amount = st.number_input("amount", min_value=0.0, value=1.0, step=0.1)
            source_venue = st.text_input("source_venue", value="kraken")
            if st.button("Submit funding request", type="primary"):
                payload = {
                    "wallet_id": wallet_id,
                    "asset": asset,
                    "amount": float(amount),
                    "source_venue": source_venue,
                }
                result = safe_post(treas, "/v1/funding-requests", json=payload)
                if result is not None:
                    st.success(f"Funding request created: {result}")

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Float exposure")
        ccy = st.selectbox("Currency", ["USD", "EUR", "GBP", "BTC", "ETH"], key="float_ccy")
        float_body = safe_get(treas, f"/v1/float/{ccy}")
        if isinstance(float_body, dict):
            fcol1, fcol2 = st.columns(2)
            fcol1.metric("Short fiat amount", float_body.get("short_fiat_amount", 0))
            fcol2.metric("Fiat currency", float_body.get("fiat_currency", ccy))
            if "long_crypto_amount" in float_body:
                st.metric("Long crypto amount", float_body.get("long_crypto_amount", 0))
        else:
            st.info("No float data available.")

    with right:
        st.subheader("Hot/warm wallet funding requests")
        fr_body = safe_get(treas, "/v1/funding-requests")
        fr = list_to_frame(
            fr_body.get("funding_requests") if isinstance(fr_body, dict) else None
        )
        empty_state("funding requests", fr)
        if not fr.empty:
            st.dataframe(fr, use_container_width=True, hide_index=True)

    st.subheader("Rebalancing queue")
    reb_body = safe_get(treas, "/v1/rebalancing-jobs", params={"status": "pending"})
    reb = list_to_frame(
        reb_body.get("rebalancing_jobs") if isinstance(reb_body, dict) else None
    )
    empty_state("pending rebalancing jobs", reb)
    if not reb.empty:
        st.dataframe(reb, use_container_width=True, hide_index=True)

    st.subheader("Float utilization gauge")
    if isinstance(float_body, dict):
        committed = float(float_body.get("short_fiat_amount", 0) or 0)
        available = st.session_state.get("float_available", max(committed * 2, 1.0))
        ratio = committed / available if available else 0.0
        st.progress(min(ratio, 1.0), text=f"{ratio:.0%} committed vs available")
    else:
        st.info("Float utilization unavailable.")
