"""Stage 8 — Settlement & Rail Status (payment-orchestration, rail-connectors)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..data import client, empty_state, list_to_frame, safe_get, safe_post


def _aging_bucket(ts: str | None) -> str:
    if not ts:
        return "unknown"
    try:
        t = pd.Timestamp(ts)
    except (ValueError, TypeError):
        return "unknown"
    hours = (pd.Timestamp.now('UTC') - t).total_seconds() / 3600
    if hours <= 1:
        return "0-1h"
    if hours <= 4:
        return "1-4h"
    if hours <= 24:
        return "4-24h"
    return "24h+"


def render() -> None:
    st.header("Settlement & Rail Status")
    st.caption("Payment settlement, chargebacks, 3DS auth, and rail health.")
    pay = client("payment")

    st.subheader("Create payment intent")
    with st.expander("New payment intent", expanded=False):
        with st.container(border=True):
            i1, i2 = st.columns(2)
            p_rail = i1.selectbox("rail", ["card", "ach", "sepa", "wire"], key="pay_rail")
            p_currency = i2.selectbox("currency", ["USD", "EUR", "GBP"], key="pay_ccy")
            i3, i4 = st.columns(2)
            p_amount = i3.number_input("amount", min_value=0, value=10000, step=100, key="pay_amount")
            p_3ds = i4.checkbox("three_ds_required", value=False, key="pay_3ds")
            p_payer = st.text_input("payer_ref", value="bo-ui-payer", key="pay_payer")
            if st.button("Submit intent", type="primary"):
                payload: dict = {
                    "rail": p_rail,
                    "amount": int(p_amount),
                    "currency": p_currency,
                    "payer_ref": p_payer,
                }
                if p_3ds:
                    payload["three_ds_required"] = True
                headers = {"Idempotency-Key": f"bo-ui-{pd.Timestamp.now('UTC').value}"}
                result = safe_post(pay, "/v1/payments/intents", json=payload, headers=headers)
                if result is not None:
                    st.success(f"Intent created: {result}")

    st.divider()

    st.subheader("Settlement status")
    payments_body = safe_get(pay, "/v1/payments")
    payments: list[dict] = []
    if isinstance(payments_body, dict):
        payments = payments_body.get("payments", []) or payments_body.get("items", []) or []
    elif isinstance(payments_body, list):
        payments = payments_body
    pdf = list_to_frame(payments)
    if not pdf.empty:
        ts_col = next(
            (c for c in ("settled_at", "captured_at", "created_at", "timestamp") if c in pdf.columns),
            None,
        )
        if ts_col:
            pdf = pdf.copy()
            pdf["aging_bucket"] = pdf[ts_col].map(_aging_bucket)
    empty_state("payments", pdf)
    if not pdf.empty:
        st.dataframe(pdf, use_container_width=True, hide_index=True)

    st.subheader("Payment detail")
    selected: str | None = None
    if not pdf.empty and "id" in pdf.columns:
        selected = st.selectbox("Select payment", options=pdf["id"].tolist(), key="pay_sel")
    if selected:
        detail = safe_get(pay, f"/v1/payments/{selected}")
        if isinstance(detail, dict):
            scol1, scol2 = st.columns(2)
            scol1.metric("Status", detail.get("status", "-"))
            scol2.metric("Rail", detail.get("rail", "-"))
            history = detail.get("history")
            if isinstance(history, list) and history:
                st.caption("History")
                st.dataframe(list_to_frame(history), use_container_width=True, hide_index=True)
            st.json(detail)

        acol1, acol2 = st.columns(2)
        with acol1:
            st.caption("Capture / Refund actions")
            cap_amount = st.number_input("capture amount", min_value=0, value=0, step=100, key="pay_cap")
            if st.button("Capture"):
                headers = {"Idempotency-Key": f"bo-ui-cap-{pd.Timestamp.now('UTC').value}"}
                result = safe_post(
                    pay, f"/v1/payments/{selected}/capture", json={"amount": int(cap_amount)}, headers=headers
                )
                if result is not None:
                    st.success(f"Captured: {result}")
            ref_amount = st.number_input("refund amount", min_value=0, value=0, step=100, key="pay_ref")
            if st.button("Refund"):
                headers = {"Idempotency-Key": f"bo-ui-ref-{pd.Timestamp.now('UTC').value}"}
                result = safe_post(
                    pay, f"/v1/payments/{selected}/refund", json={"amount": int(ref_amount)}, headers=headers
                )
                if result is not None:
                    st.success(f"Refunded: {result}")
        with acol2:
            if st.button("Void payment"):
                headers = {"Idempotency-Key": f"bo-ui-void-{pd.Timestamp.now('UTC').value}"}
                result = safe_post(pay, f"/v1/payments/{selected}/void", headers=headers)
                if result is not None:
                    st.success(f"Voided: {result}")

    st.subheader("Pending settlement aging")
    if not pdf.empty and "aging_bucket" in pdf.columns:
        counts = pdf["aging_bucket"].value_counts().reindex(
            ["0-1h", "1-4h", "4-24h", "24h+", "unknown"], fill_value=0
        )
        st.bar_chart(counts)
    else:
        st.info("No aging data — no payments to bucket.")

    st.subheader("3DS auth records")
    if not pdf.empty and "status" in pdf.columns:
        three_ds = pdf[pdf["status"].astype(str).str.contains("3ds", case=False, na=False)]
        if not three_ds.empty:
            st.dataframe(three_ds, use_container_width=True, hide_index=True)
        else:
            st.info("No 3DS-pending payments.")
    else:
        st.info("No payment data.")

    st.subheader("Chargebacks")
    st.info(
        "Chargeback endpoints are not exposed by payment-orchestration in the "
        "current API surface; chargeback visibility will be added when the "
        "dispute webhook surface lands."
    )

    st.subheader("Rail health & metrics")
    metrics_body = safe_get(pay, "/metrics")
    if isinstance(metrics_body, dict):
        mcol1, mcol2 = st.columns(2)
        mcol1.metric("Transitions", len(metrics_body.get("transitions", []) or []))
        mcol2.metric("Webhook backlog", metrics_body.get("webhook_backlog", 0))
        st.json(metrics_body)
    else:
        st.info("Metrics unavailable.")
