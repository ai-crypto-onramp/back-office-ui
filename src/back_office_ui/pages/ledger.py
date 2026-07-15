"""Stage 5 — Ledger Viewer (ledger-accounting)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..data import client, empty_state, list_to_frame, safe_get, safe_post


def render() -> None:
    st.header("Ledger Viewer")
    st.caption("Double-entry ledger: accounts, postings, trial balance, and export.")
    ledger = client("ledger")

    st.subheader("Chart of accounts")
    coa_body = safe_get(ledger, "/v1/chart-of-accounts")
    account_types: list[dict] = []
    if isinstance(coa_body, dict):
        account_types = coa_body.get("account_types", []) or []
    coa_df = list_to_frame(account_types)
    if coa_df.empty:
        st.info("No chart of accounts returned.")
    else:
        st.dataframe(coa_df, use_container_width=True, hide_index=True)

    st.subheader("Create account")
    with st.expander("New account", expanded=False):
        with st.container(border=True):
            a1, a2, a3 = st.columns(3)
            types = (
                coa_df["type"].tolist()
                if not coa_df.empty and "type" in coa_df.columns
                else ["user_custodial", "user_payable", "fee_revenue"]
            )
            a_type = a1.selectbox("type", types, key="ledger_type")
            a_class = a2.selectbox("asset_class", ["fiat", "crypto"], key="ledger_class")
            a_label = a3.text_input("label", value="bo-ui-account")
            if st.button("Create account", type="primary"):
                payload = {"type": a_type, "asset_class": a_class, "label": a_label}
                result = safe_post(ledger, "/v1/accounts", json=payload)
                if result is not None:
                    st.success(f"Account created: {result}")

    st.divider()

    st.subheader("Journal entry search")
    with st.container(border=True):
        s1, s2, s3 = st.columns(3)
        search_tx = s1.text_input("posting_id", value="", key="ledger_search_tx")
        search_asset = s2.text_input("asset filter", value="", key="ledger_search_asset")
        search_limit = s3.number_input("limit", min_value=1, value=20, step=5, key="ledger_limit")

    if search_tx:
        entry = safe_get(ledger, f"/v1/postings/{search_tx}")
        if isinstance(entry, dict):
            st.json(entry)
            entries = entry.get("entries")
            if isinstance(entries, list) and entries:
                st.dataframe(list_to_frame(entries), use_container_width=True, hide_index=True)
        else:
            st.info("Posting not found.")

    st.subheader("Create posting")
    with st.expander("New balanced posting", expanded=False):
        with st.container(border=True):
            p_debit_acc = st.text_input("debit account_id", value="", key="post_debit_acc")
            p_credit_acc = st.text_input("credit account_id", value="", key="post_credit_acc")
            p1, p2 = st.columns(2)
            p_amount = p1.number_input("amount", min_value=0.0, value=100.0, step=10.0, key="post_amount")
            p_asset = p2.text_input("asset", value="USD", key="post_asset")
            p_memo = st.text_input("memo", value="bo-ui posting", key="post_memo")
            if st.button("Submit posting", type="primary"):
                if not (p_debit_acc and p_credit_acc):
                    st.error("Both debit and credit account_ids are required.")
                else:
                    payload = {
                        "posting_id": f"bo-ui-{pd.Timestamp.now('UTC').value}",
                        "entries": [
                            {
                                "account_id": p_debit_acc,
                                "direction": "debit",
                                "amount": float(p_amount),
                                "asset": p_asset,
                            },
                            {
                                "account_id": p_credit_acc,
                                "direction": "credit",
                                "amount": float(p_amount),
                                "asset": p_asset,
                            },
                        ],
                        "memo": p_memo,
                    }
                    result = safe_post(ledger, "/v1/postings", json=payload)
                    if result is not None:
                        st.success(f"Posting created: {result}")

    st.subheader("Account ledger & balance")
    acc_id = st.text_input("account_id", value="", key="ledger_acc_id")
    if acc_id:
        lcol, rcol = st.columns(2)
        with lcol:
            bal_body = safe_get(ledger, f"/v1/accounts/{acc_id}/balance", params={"asset": search_asset or "USD"})
            if isinstance(bal_body, dict):
                st.metric("Balance", bal_body.get("balance", 0))
                st.caption(f"Asset: {bal_body.get('asset', search_asset or 'USD')}")
            else:
                st.info("No balance for this account/asset.")
        with rcol:
            led_body = safe_get(ledger, f"/v1/accounts/{acc_id}/ledger", params={"limit": int(search_limit)})
            entries = led_body.get("entries") if isinstance(led_body, dict) else None
            led_df = list_to_frame(entries)
            empty_state("ledger entries", led_df)
            if not led_df.empty:
                st.dataframe(led_df, use_container_width=True, hide_index=True)
                if isinstance(led_body, dict) and "final_balance" in led_body:
                    st.caption(f"Final balance: {led_body['final_balance']}")

    st.subheader("Chain verification")
    chain_body = safe_get(ledger, "/v1/chain/verify")
    if isinstance(chain_body, dict):
        ok = chain_body.get("ok")
        if ok is True:
            st.success("Hash chain verified.")
        elif ok is False:
            st.error("Hash chain verification failed!")
        else:
            st.json(chain_body)
    else:
        st.info("Chain verification unavailable.")

    st.subheader("Reconciliation: user custodial sum")
    uc_body = safe_get(ledger, "/v1/reconciliation/user-custodial-sum")
    if isinstance(uc_body, dict):
        st.metric("User custodial sum", uc_body.get("user_custodial_sum", 0))
    else:
        st.info("User custodial sum unavailable.")

    st.subheader("Export to CSV")
    if not coa_df.empty:
        st.download_button(
            "Download chart of accounts (CSV)",
            coa_df.to_csv(index=False).encode(),
            file_name="chart_of_accounts.csv",
            mime="text/csv",
        )
