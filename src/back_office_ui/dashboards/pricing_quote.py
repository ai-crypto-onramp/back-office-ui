"""Pricing / Quote dashboard (pricing-quote).

Surfaces the durable records of every quote the service has issued, the
fee-schedule model in effect, and the rate-source registry / failover
order. The pricing-quote service exposes:

- ``GET /v1/quotes``            — list all issued quotes (newest first)
- ``GET /v1/quotes/:id``        — fetch a quote by id
- ``GET /v1/fee-schedules``    — list the in-effect fee schedules
- ``GET /v1/rate-sources``      — list enabled upstream rate sources
- ``GET /v1/audit-events``      — quote lifecycle events
- ``POST /internal/v1/fee-schedules/reload`` — hot-reload fee schedules
"""

from __future__ import annotations

import streamlit as st

from ..data import client, empty_state, list_to_frame, safe_get, safe_post
from . import section


def render() -> None:
    st.header("💹 Pricing / Quote")
    st.caption("Rate quotes, fee schedules, rate sources, and quote lifecycle events.")
    pricing = client("pricing")

    section(
        "📋 Quotes",
        "Every quote the service has issued, newest first. Each row records the "
        "pair, amount, locked rate, spread, fee, total, crypto amount, status, "
        "source venue, and expiry. Use the lookup below to inspect a single "
        "quote in full detail.",
    )
    list_body = safe_get(pricing, "/v1/quotes")
    quotes = list_to_frame(
        list_body.get("quotes") if isinstance(list_body, dict) else None
    )
    empty_state("quotes", quotes)
    if not quotes.empty:
        display_cols = [
            c for c in (
                "quote_id", "from", "to", "side", "amount", "rate", "spread_bps",
                "fee", "total", "crypto_amount", "status", "source_venue",
                "user_tier", "created_at", "expires_at",
            ) if c in quotes.columns
        ]
        st.dataframe(quotes[display_cols] if display_cols else quotes, width="stretch", hide_index=True)
        if "status" in quotes.columns:
            st.subheader("📊 Quotes by status")
            st.bar_chart(quotes["status"].value_counts())

    section(
        "🔍 Quote lookup",
        "Fetch a single quote by its id. Returns the pair, amount, locked rate, "
        "spread, fee, total, crypto amount, status, source venue, and expiry. "
        "Expired quotes are surfaced as expired by the service even if their "
        "status field still reads 'open'.",
    )
    quote_id = st.text_input("quote id", value="", key="pq_lookup_id")
    if quote_id:
        detail_body = safe_get(pricing, f"/v1/quotes/{quote_id}")
        if isinstance(detail_body, dict):
            dcol1, dcol2, dcol3 = st.columns(3)
            dcol1.metric("Status", detail_body.get("status", "-"))
            dcol2.metric("Pair", f"{detail_body.get('from', '?')}/{detail_body.get('to', '?')}")
            dcol3.metric("Side", detail_body.get("side", "-"))
            mcol1, mcol2, mcol3 = st.columns(3)
            mcol1.metric("Rate", detail_body.get("rate", "-"))
            mcol2.metric("Spread (bps)", detail_body.get("spread_bps", "-"))
            mcol3.metric("Fee", f"{detail_body.get('fee', '-')} {detail_body.get('fee_currency', '')}")
            mcol4, mcol5, mcol6 = st.columns(3)
            mcol4.metric("Amount", detail_body.get("amount", "-"))
            mcol5.metric("Total", detail_body.get("total", "-"))
            mcol6.metric("Crypto amount", detail_body.get("crypto_amount", "-"))
            scol1, scol2 = st.columns(2)
            scol1.metric("Source venue", detail_body.get("source_venue", "-") or "-")
            scol2.metric("User tier", detail_body.get("user_tier", "-"))
            st.json(detail_body)
        else:
            st.info("Quote not found or service unreachable.")
    else:
        st.info("Enter a quote id above to view details.")

    section(
        "💸 Fee schedules",
        "The in-effect spread / fee model per user tier, asset, size band, and "
        "side. Loaded into memory at startup and hot-reloaded on a 60-second "
        "tick. Use the reload button below to force an immediate refresh after "
        "a config push.",
    )
    fs_body = safe_get(pricing, "/v1/fee-schedules")
    fs = list_to_frame(
        fs_body.get("fee_schedules") if isinstance(fs_body, dict) else None
    )
    empty_state("fee schedules", fs)
    if not fs.empty:
        display_cols = [
            c for c in (
                "id", "user_tier", "asset", "side", "size_band_min", "size_band_max",
                "spread_bps", "fee_type", "fee_amount", "fee_bps", "enabled", "updated_at",
            ) if c in fs.columns
        ]
        st.dataframe(fs[display_cols] if display_cols else fs, width="stretch", hide_index=True)
        if "user_tier" in fs.columns:
            st.subheader("📊 Schedules by tier")
            st.bar_chart(fs.groupby("user_tier").size())

    if st.button("Reload fee schedules", type="primary", key="pq_reload_btn"):
        result = safe_post(pricing, "/internal/v1/fee-schedules/reload")
        if result is not None:
            st.success(f"Fee schedules reloaded: {result}")

    section(
        "📡 Rate sources",
        "Upstream venues pricing-quote pulls spot rates from. The service picks "
        "the best bid/ask across enabled venues per pair and fails over in "
        "priority order when a venue goes dark. Disabled sources are filtered "
        "out by the store.",
    )
    rs_body = safe_get(pricing, "/v1/rate-sources")
    rs = list_to_frame(
        rs_body.get("rate_sources") if isinstance(rs_body, dict) else None
    )
    empty_state("rate sources", rs)
    if not rs.empty:
        display_cols = [
            c for c in ("name", "priority", "enabled", "weight", "endpoint_ref", "created_at", "updated_at")
            if c in rs.columns
        ]
        st.dataframe(rs[display_cols] if display_cols else rs, width="stretch", hide_index=True)

    section(
        "📜 Quote lifecycle events",
        "Every quote transition (issued, refreshed, expired, claimed, "
        "slippage_rejected) is appended to an in-service audit log and exposed "
        "via ``GET /v1/audit-events``. Useful for correlating claim / expiry "
        "events with the rows in the quotes table above.",
    )
    events_body = safe_get(pricing, "/v1/audit-events")
    events = list_to_frame(
        events_body.get("events") if isinstance(events_body, dict) else None
    )
    empty_state("quote lifecycle events", events)
    if not events.empty:
        display_cols = [c for c in ("type", "quote_id", "user_tier", "source_venue") if c in events.columns]
        st.dataframe(events[display_cols] if display_cols else events, width="stretch", hide_index=True)
        if "type" in events.columns:
            st.subheader("📊 Events by type")
            st.bar_chart(events["type"].value_counts())
