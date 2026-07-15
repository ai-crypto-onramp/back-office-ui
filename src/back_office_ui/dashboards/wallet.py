"""Stage 7 — Wallet Inventory (wallet-management)."""

from __future__ import annotations

import streamlit as st

from ..data import client, empty_state, list_to_frame, safe_get, safe_post
from . import action_button, section


def render() -> None:
    st.header("👛 Wallet Inventory")
    st.caption("Wallet state, address derivation, and balances across chains.")
    wallet = client("wallet")

    section(
        "📋 Wallet inventory",
        "The wallet inventory lists every wallet we manage across all chains and "
        "types (hot, warm, cold). The charts break down how many wallets we hold per "
        "chain and per type so you can see our overall footprint.",
    )
    wl_body = safe_get(wallet, "/v1/wallets")
    wallets: list[dict] = []
    if isinstance(wl_body, dict):
        wallets = wl_body.get("wallets", []) or wl_body.get("items", []) or []
    elif isinstance(wl_body, list):
        wallets = wl_body
    wdf = list_to_frame(wallets)
    empty_state("wallets", wdf)
    if not wdf.empty:
        st.dataframe(wdf, width="stretch", hide_index=True)
        if "chain" in wdf.columns:
            st.subheader("📊 Wallets by chain")
            st.bar_chart(wdf["chain"].value_counts())
        if "type" in wdf.columns:
            st.subheader("📊 Wallets by type")
            st.bar_chart(wdf["type"].value_counts())

    section(
        "📝 Create wallet",
        "Provision a new wallet on a chosen chain (Ethereum, Bitcoin, Polygon, or "
        "Base) and type (hot, warm, or cold). Give it a label so you can recognise it "
        "later.",
    )
    action_button("New wallet", _wallet_dialog, key="wl_open_create")

    st.divider()

    section(
        "🔍 Wallet detail",
        "Select a wallet from the inventory to inspect its chain, type, and state, "
        "derive a fresh receive address, and view its current balances.",
    )
    selected: str | None = None
    if not wdf.empty and "id" in wdf.columns:
        selected = st.selectbox("Select wallet", options=wdf["id"].tolist(), key="wl_sel")
    if selected:
        detail = safe_get(wallet, f"/v1/wallets/{selected}")
        if isinstance(detail, dict):
            dcol1, dcol2, dcol3 = st.columns(3)
            dcol1.metric("Chain", detail.get("chain", "-"))
            dcol2.metric("Type", detail.get("type", "-"))
            dcol3.metric("State", detail.get("state", "-"))
            st.json(detail)

        st.subheader("🔑 Address derivation")
        if st.button("Derive new address"):
            result = safe_post(wallet, f"/v1/wallets/{selected}/addresses/derive")
            if result is not None:
                st.success(f"Derived: {result}")

        st.subheader("💰 Balances")
        bal_body = safe_get(wallet, f"/v1/wallets/{selected}/balances")
        if isinstance(bal_body, list) and bal_body:
            st.dataframe(list_to_frame(bal_body), width="stretch", hide_index=True)
        elif isinstance(bal_body, dict) and bal_body:
            st.json(bal_body)
        else:
            st.info("No balances recorded for this wallet.")

    section(
        "🔑 Key rotation status",
        "Key rotation (re-keying a wallet via a Distributed Key Generation ceremony) "
        "isn't exposed through the wallet REST surface. See the MPC Signing Monitor "
        "for ceremony events.",
    )
    st.info(
        "Key rotation / DKG schedule is not exposed via the wallet-management "
        "REST surface; see the MPC Signing Monitor for ceremony events."
    )


@st.dialog("New wallet")
def _wallet_dialog() -> None:
    """Collect wallet-creation inputs and submit them to the wallet service."""
    wallet = client("wallet")
    w1, w2 = st.columns(2)
    w_chain = w1.selectbox("chain", ["ethereum", "bitcoin", "polygon", "base"], key="wl_chain")
    w_type = w2.selectbox("type", ["hot", "warm", "cold"], key="wl_type")
    w_label = st.text_input("label", value="bo-ui-wallet", key="wl_label")
    if st.button("Create wallet", type="primary"):
        payload = {"chain": w_chain, "type": w_type, "label": w_label}
        result = safe_post(wallet, "/v1/wallets", json=payload)
        if result is not None:
            st.success(f"Wallet created: {result}")
