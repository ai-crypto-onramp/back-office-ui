"""Stage 8 — Settlement & Rail Status (payment-orchestration, rail-connectors)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..data import client, empty_state, list_to_frame, safe_get, safe_post
from . import action_button, section


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
    st.header("💳 Settlement & Rail Status")
    st.caption("Payment settlement, chargebacks, 3DS auth, and rail health.")
    pay = client("payment")

    section(
        "📝 Create payment intent",
        "A payment intent represents our intent to collect money from a payer via a "
        "rail (card, ACH, SEPA, or wire). Enter the rail, amount, currency, payer "
        "reference, and whether 3DS authentication is required.",
    )
    action_button("New payment intent", _intent_dialog, key="pay_open_intent")

    st.divider()

    section(
        "📋 Payment inventory",
        "Every payment intent the service has created, with its rail, amount, "
        "currency, and current status. Filter by status or rail to focus on "
        "in-flight or settled payments.",
    )
    pay_status = st.selectbox(
        "Filter by status",
        ["", "intent", "authorized", "3ds_pending", "captured", "settled", "refunding", "refunded", "voided", "failed", "charged_back"],
        key="pay_list_status",
    )
    pay_rail = st.selectbox(
        "Filter by rail", ["", "card", "ach", "sepa", "wire", "pix", "upi"], key="pay_list_rail"
    )
    pay_params: dict[str, str] = {}
    if pay_status:
        pay_params["status"] = pay_status
    if pay_rail:
        pay_params["rail"] = pay_rail
    pay_list_body = safe_get(pay, "/v1/payments", params=pay_params or None)
    pay_list = list_to_frame(
        pay_list_body.get("payments") if isinstance(pay_list_body, dict) else None
    )
    empty_state("payments", pay_list)
    if not pay_list.empty:
        st.dataframe(pay_list, width="stretch", hide_index=True)

    section(
        "🔍 Payment lookup",
        "Enter a payment ID to inspect its status, history, and actions.",
    )
    payment_id = st.text_input("payment ID", value="", key="pay_id")
    detail_body = safe_get(pay, f"/v1/payments/{payment_id}") if payment_id else None
    detail: dict | None = detail_body if isinstance(detail_body, dict) else None
    if isinstance(detail, dict):
        scol1, scol2 = st.columns(2)
        scol1.metric("Status", detail.get("status", "-"))
        scol2.metric("Rail", detail.get("rail", "-"))
        history = detail.get("history")
        if isinstance(history, list) and history:
            st.caption("History")
            st.dataframe(list_to_frame(history), width="stretch", hide_index=True)
        st.json(detail)

        st.session_state["pay_selected_id"] = payment_id
        st.caption("Capture / Refund / Void actions")
        acol1, acol2, acol3 = st.columns(3)
        with acol1:
            action_button("Capture", _capture_dialog, key="pay_open_capture")
        with acol2:
            action_button("Refund", _refund_dialog, key="pay_open_refund")
        with acol3:
            action_button("Void payment", _void_dialog, key="pay_open_void")
    elif payment_id:
        st.info("Payment not found.")
    else:
        st.info("Enter a payment ID above to view details.")

    section(
        "⏳ Pending settlement aging",
        "Aging analysis shows how long pending settlements have been waiting. Use "
        "the payment inventory above filtered by status to inspect pending "
        "settlements and their individual timelines.",
    )
    st.info(
        "For aging analysis, filter the payment inventory above by status "
        "(e.g. 'captured' or 'settled') and inspect individual payment timelines "
        "via the payment lookup below."
    )

    section(
        "🔐 3DS auth records",
        "3DS (3-D Secure) authentication challenges are embedded inside individual "
        "payment intents. Use the payment lookup above to inspect 3DS challenge "
        "status per payment.",
    )
    st.info(
        "3DS records are embedded in individual payment intents. Use the "
        "payment lookup above to inspect 3DS challenge status per payment."
    )

    section(
        "⚖️ Chargebacks",
        "Chargebacks (payment disputes raised by a customer's bank) aren't exposed "
        "by payment-orchestration yet. Visibility will be added when the dispute "
        "webhook surface lands.",
    )
    st.info(
        "Chargeback endpoints are not exposed by payment-orchestration in the "
        "current API surface; chargeback visibility will be added when the "
        "dispute webhook surface lands."
    )

    section(
        "🚄 Rail health & metrics",
        "Rail health summarises how each payment rail is performing, including how "
        "many state transitions are in flight and the webhook backlog.",
    )
    metrics_body = safe_get(pay, "/metrics")
    if isinstance(metrics_body, dict):
        mcol1, mcol2 = st.columns(2)
        mcol1.metric("Transitions", len(metrics_body.get("transitions", []) or []))
        mcol2.metric("Webhook backlog", metrics_body.get("webhook_backlog", 0))
        st.json(metrics_body)
    else:
        st.info("Metrics unavailable.")


@st.dialog("New payment intent")
def _intent_dialog() -> None:
    """Collect payment-intent inputs and submit them to the payment service."""
    pay = client("payment")
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


@st.dialog("Capture payment")
def _capture_dialog() -> None:
    """Collect a capture amount and capture funds for the selected payment."""
    pay = client("payment")
    payment_id = st.session_state.get("pay_selected_id")
    if not payment_id:
        st.warning("No payment selected.")
        return
    cap_amount = st.number_input("capture amount", min_value=0, value=0, step=100, key="pay_cap")
    if st.button("Capture", type="primary"):
        headers = {"Idempotency-Key": f"bo-ui-cap-{pd.Timestamp.now('UTC').value}"}
        result = safe_post(
            pay, f"/v1/payments/{payment_id}/capture", json={"amount": int(cap_amount)}, headers=headers
        )
        if result is not None:
            st.success(f"Captured: {result}")


@st.dialog("Refund payment")
def _refund_dialog() -> None:
    """Collect a refund amount and refund funds for the selected payment."""
    pay = client("payment")
    payment_id = st.session_state.get("pay_selected_id")
    if not payment_id:
        st.warning("No payment selected.")
        return
    ref_amount = st.number_input("refund amount", min_value=0, value=0, step=100, key="pay_ref")
    if st.button("Refund", type="primary"):
        headers = {"Idempotency-Key": f"bo-ui-ref-{pd.Timestamp.now('UTC').value}"}
        result = safe_post(
            pay, f"/v1/payments/{payment_id}/refund", json={"amount": int(ref_amount)}, headers=headers
        )
        if result is not None:
            st.success(f"Refunded: {result}")


@st.dialog("Void payment")
def _void_dialog() -> None:
    """Confirm and void the selected payment."""
    pay = client("payment")
    payment_id = st.session_state.get("pay_selected_id")
    if not payment_id:
        st.warning("No payment selected.")
        return
    st.write(f"Void payment **{payment_id}**?")
    if st.button("Void payment", type="primary"):
        headers = {"Idempotency-Key": f"bo-ui-void-{pd.Timestamp.now('UTC').value}"}
        result = safe_post(pay, f"/v1/payments/{payment_id}/void", headers=headers)
        if result is not None:
            st.success(f"Voided: {result}")
