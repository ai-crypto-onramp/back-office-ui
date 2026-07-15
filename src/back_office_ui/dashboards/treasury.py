"""Stage 2 — Treasury Dashboard (treasury-orchestration)."""

from __future__ import annotations

import streamlit as st

from ..data import client, empty_state, list_to_frame, safe_get, safe_post
from . import action_button, section


def render() -> None:
    st.header("🏛️ Treasury Dashboard")
    st.caption("Aggregate buy-order batches, float exposure, and wallet funding.")
    treas = client("treasury")

    section(
        "📦 Buy-order batches",
        "Batches group together customer buy orders so the treasury can fund and "
        "hedge them in one shot. This table shows every batch the system has created, "
        "what asset it covers, and whether it's still open or has been settled.",
    )
    batches_body = safe_get(treas, "/v1/batches")
    batches = list_to_frame(batches_body.get("batches") if isinstance(batches_body, dict) else None)
    if batches.empty:
        st.info("No batches yet — batches are produced by the tx.completed event consumer.")
    else:
        st.dataframe(batches, width="stretch", hide_index=True)

    section(
        "📝 Batch creation",
        "Create a funding request, which is the input the treasury uses to aggregate "
        "and fund a buy-order batch. Pick the destination wallet, the asset and amount "
        "you want funded, and where the funds should come from (the source venue/exchange).",
    )
    action_button("Create funding request", _funding_request_dialog, key="treasury_open_funding")

    st.divider()

    left, right = st.columns(2)

    with left:
        section(
            "💰 Float exposure",
            "Float exposure is the fiat we've collected from customers but haven't "
            "yet converted to crypto. Pick a currency to see how much short fiat is "
            "outstanding and the corresponding long crypto position.",
        )
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
        section(
            "👛 Hot/warm wallet funding requests",
            "These are pending requests to move funds into our hot or warm operational "
            "wallets so there's always enough liquidity to settle customer orders.",
        )
        fr_body = safe_get(treas, "/v1/funding-requests")
        fr = list_to_frame(
            fr_body.get("funding_requests") if isinstance(fr_body, dict) else None
        )
        empty_state("funding requests", fr)
        if not fr.empty:
            st.dataframe(fr, width="stretch", hide_index=True)

    section(
        "🔄 Rebalancing queue",
        "Rebalancing jobs move funds between hot, warm, and cold wallets to keep the "
        "right amount of each asset in the right place. This queue lists jobs that are "
        "waiting to run.",
    )
    reb_body = safe_get(treas, "/v1/rebalancing-jobs", params={"status": "pending"})
    reb = list_to_frame(
        reb_body.get("rebalancing_jobs") if isinstance(reb_body, dict) else None
    )
    empty_state("pending rebalancing jobs", reb)
    if not reb.empty:
        st.dataframe(reb, width="stretch", hide_index=True)

    section(
        "📊 Float utilization gauge",
        "This gauge compares how much fiat we've committed (collected from customers) "
        "against how much is available. A high ratio means we're close to fully "
        "deployed and may need to top up or hedge.",
    )
    if isinstance(float_body, dict):
        committed = float(float_body.get("short_fiat_amount", 0) or 0)
        available = st.session_state.get("float_available", max(committed * 2, 1.0))
        ratio = committed / available if available else 0.0
        st.progress(min(ratio, 1.0), text=f"{ratio:.0%} committed vs available")
    else:
        st.info("Float utilization unavailable.")


@st.dialog("Create a funding request")
def _funding_request_dialog() -> None:
    """Collect funding-request inputs and submit them to the treasury service."""
    treas = client("treasury")
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
