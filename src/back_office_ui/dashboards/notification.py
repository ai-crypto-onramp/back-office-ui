"""Notification dashboard (notification service).

Surfaces the notification service's admin REST surface:

- ``GET /v1/notifications``        — list all notifications (newest first)
- ``GET /v1/notifications/:id``     — notification + its delivery attempts
- ``GET /v1/notifications/:id/status`` — aggregated per-channel status
- ``GET /v1/preferences``           — list all user preferences
- ``GET /v1/preferences/:user_id``  — per-user channel preferences
- ``POST /v1/preferences/:user_id`` — update preferences
- ``GET /v1/webhooks/partners``     — registered partner webhooks
- ``POST /v1/webhooks/partners``    — register a new webhook
- ``GET /v1/audit-events``          — notification lifecycle audit log

The notification service consumes ``tx.*`` and ``chain.confirmed`` events off
the bus asynchronously and fans them out across email / SMS / push / webhook
channels.
"""

from __future__ import annotations

import streamlit as st

from ..data import client, empty_state, list_to_frame, safe_get, safe_post
from . import action_button, section


def render() -> None:
    st.header("🔔 Notification")
    st.caption("Outbound messages, delivery attempts, partner webhooks, and user preferences.")
    notif = client("notification")

    section(
        "📋 Notifications",
        "Every outbound notification the service has recorded, newest first. "
        "Each row covers the event type, channel, recipient, template, status, "
        "and timestamps. Use the lookup below to drill into a single "
        "notification and its delivery attempts.",
    )
    list_body = safe_get(notif, "/v1/notifications")
    notifications = list_to_frame(
        list_body.get("notifications") if isinstance(list_body, dict) else None
    )
    empty_state("notifications", notifications)
    if not notifications.empty:
        display_cols = [
            c for c in (
                "id", "event_type", "channel", "recipient", "user_id", "template_id",
                "status", "traffic_class", "locale", "created_at", "sent_at",
            ) if c in notifications.columns
        ]
        st.dataframe(notifications[display_cols] if display_cols else notifications, width="stretch", hide_index=True)
        if "status" in notifications.columns:
            st.subheader("📊 Notifications by status")
            st.bar_chart(notifications["status"].value_counts())
        if "channel" in notifications.columns:
            st.subheader("📊 Notifications by channel")
            st.bar_chart(notifications["channel"].value_counts())

    section(
        "🔍 Notification lookup",
        "Fetch a notification by id. Returns the notification record plus every "
        "delivery attempt recorded against it (channel, provider, provider "
        "message id, status, attempt number, error). Use the aggregated status "
        "endpoint below for a per-channel rollup.",
    )
    notif_id = st.text_input("notification id", value="", key="nf_lookup_id")
    if notif_id:
        detail_body = safe_get(notif, f"/v1/notifications/{notif_id}")
        if isinstance(detail_body, dict):
            n = detail_body.get("notification") or {}
            attempts = detail_body.get("attempts") or []
            ncol1, ncol2, ncol3 = st.columns(3)
            ncol1.metric("Status", n.get("status", "-"))
            ncol2.metric("Channel", n.get("channel", "-"))
            ncol3.metric("Recipient", n.get("recipient", "-"))
            tcol1, tcol2 = st.columns(2)
            tcol1.metric("Event type", n.get("event_type", "-"))
            tcol2.metric("Template", n.get("template_id", "-"))
            with st.expander("Notification record"):
                st.json(n)
            st.subheader("Delivery attempts")
            adf = list_to_frame(attempts if isinstance(attempts, list) else None)
            empty_state("delivery attempts", adf)
            if not adf.empty:
                st.dataframe(adf, width="stretch", hide_index=True)

            status_body = safe_get(notif, f"/v1/notifications/{notif_id}/status")
            if isinstance(status_body, dict):
                st.subheader("Aggregated status")
                st.json(status_body)
        else:
            st.info("Notification not found or service unreachable.")
    else:
        st.info("Enter a notification id above to view details.")

    section(
        "📜 Notification lifecycle events",
        "Every notification transition (requested, delivered, failed, "
        "suppressed, bounced) is appended to an in-service audit log and "
        "exposed via ``GET /v1/audit-events``. Useful for spotting delivery "
        "spikes, bounce storms, or stuck channels at a glance.",
    )
    events_body = safe_get(notif, "/v1/audit-events")
    events = list_to_frame(
        events_body.get("events") if isinstance(events_body, dict) else None
    )
    empty_state("notification lifecycle events", events)
    if not events.empty:
        display_cols = [c for c in ("type", "notification_id", "channel", "status", "created_at") if c in events.columns]
        st.dataframe(events[display_cols] if display_cols else events, width="stretch", hide_index=True)
        if "type" in events.columns:
            st.subheader("📊 Events by type")
            st.bar_chart(events["type"].value_counts())
        if "channel" in events.columns:
            st.subheader("📊 Events by channel")
            st.bar_chart(events["channel"].value_counts())

    section(
        "👤 User preferences",
        "Per-user channel opt-ins (email, sms, push, webhook), preferred "
        "locale, and any quiet-hours window. The list below is every "
        "preferences record the service holds. Use the lookup to inspect or "
        "edit a single user's preferences.",
    )
    pref_list_body = safe_get(notif, "/v1/preferences")
    pref_list = list_to_frame(
        pref_list_body.get("preferences") if isinstance(pref_list_body, dict) else None
    )
    empty_state("user preferences", pref_list)
    if not pref_list.empty:
        display_cols = [c for c in ("user_id", "locale", "channels", "quiet_hours") if c in pref_list.columns]
        st.dataframe(pref_list[display_cols] if display_cols else pref_list, width="stretch", hide_index=True)

    pref_user = st.text_input("user id", value="", key="nf_pref_user")
    if pref_user:
        pref_body = safe_get(notif, f"/v1/preferences/{pref_user}")
        if isinstance(pref_body, dict):
            pcol1, pcol2 = st.columns(2)
            pcol1.metric("Locale", pref_body.get("locale", "-"))
            quiet = pref_body.get("quiet_hours")
            if isinstance(quiet, dict):
                pcol2.metric("Quiet hours", f"{quiet.get('start', '--')} → {quiet.get('end', '--')}")
            else:
                pcol2.metric("Quiet hours", "--")
            with st.expander("Preference record"):
                st.json(pref_body)
            action_button("Update preferences", _preferences_dialog, key="nf_open_prefs")
            st.session_state["nf_pref_user_editing"] = pref_user
        else:
            st.info("No preferences set for this user (defaults apply).")
            action_button("Set preferences", _preferences_dialog, key="nf_open_prefs_create")
            st.session_state["nf_pref_user_editing"] = pref_user
    else:
        st.info("Enter a user id above to view or set preferences.")

    section(
        "🔗 Partner webhooks",
        "Registered partner webhook endpoints. Each webhook has a signing "
        "secret, event filters (which event types it wants), a retry policy, "
        "and a batching window. Use the button to register a new webhook.",
    )
    action_button("Register partner webhook", _webhook_dialog, key="nf_open_webhook")
    wh_body = safe_get(notif, "/v1/webhooks/partners")
    webhooks = list_to_frame(
        wh_body.get("webhooks") if isinstance(wh_body, dict) else None
    )
    empty_state("partner webhooks", webhooks)
    if not webhooks.empty:
        display_cols = [c for c in ("id", "url", "status", "batch_window", "created_at") if c in webhooks.columns]
        st.dataframe(webhooks[display_cols] if display_cols else webhooks, width="stretch", hide_index=True)
        if "status" in webhooks.columns:
            st.subheader("📊 Webhooks by status")
            st.bar_chart(webhooks["status"].value_counts())


@st.dialog("Update user preferences")
def _preferences_dialog() -> None:
    """Collect per-user channel preference inputs and submit them."""
    notif = client("notification")
    user_id = st.session_state.get("nf_pref_user_editing") or ""
    if not user_id:
        st.warning("No user selected.")
        return
    st.write(f"Editing preferences for **{user_id}**")
    prow = st.columns(4)
    email = prow[0].checkbox("email", value=True, key="nf_pref_email")
    sms = prow[1].checkbox("sms", value=True, key="nf_pref_sms")
    push = prow[2].checkbox("push", value=True, key="nf_pref_push")
    webhook = prow[3].checkbox("webhook", value=True, key="nf_pref_webhook")
    locale = st.selectbox("locale", ["en", "es", "fr", "de", "pt"], key="nf_pref_locale")
    qrow = st.columns(2)
    quiet_start = qrow[0].text_input("quiet_start (HH:MM)", value="", key="nf_pref_qs")
    quiet_end = qrow[1].text_input("quiet_end (HH:MM)", value="", key="nf_pref_qe")
    if st.button("Save preferences", type="primary"):
        payload: dict = {
            "channels": {
                "email": email,
                "sms": sms,
                "push": push,
                "webhook": webhook,
            },
            "locale": locale,
        }
        if quiet_start and quiet_end:
            payload["quiet_hours"] = {"start": quiet_start, "end": quiet_end}
        result = safe_post(notif, f"/v1/preferences/{user_id}", json=payload)
        if result is not None:
            st.success(f"Preferences saved: {result}")


@st.dialog("Register partner webhook")
def _webhook_dialog() -> None:
    """Collect partner-webhook inputs and register them with the service."""
    notif = client("notification")
    url = st.text_input("url", value="https://partner.example/webhook", key="nf_wh_url")
    secret = st.text_input("secret", value="", key="nf_wh_secret")
    if st.button("Register webhook", type="primary"):
        if not url or not secret:
            st.warning("url and secret are required.")
            return
        payload = {"url": url, "secret": secret}
        result = safe_post(notif, "/v1/webhooks/partners", json=payload)
        if result is not None:
            st.success(f"Webhook registered: {result}")
