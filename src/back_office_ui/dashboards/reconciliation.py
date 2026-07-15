"""Stage 6 — Reconciliation Dashboard (reconciliation)."""

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
    st.header("🧮 Reconciliation Dashboard")
    st.caption("Break detection, aging, and resolution against ledger vs external sources.")
    recon = client("reconciliation")

    section(
        "🚨 Break queue",
        "A break is a mismatch between two sources of truth (e.g. our ledger vs the "
        "bank). This queue lists every open break so operators can triage and resolve "
        "them. Use the filters to narrow down by source, type, or status.",
    )
    with st.container(border=True):
        f1, f2, f3 = st.columns(3)
        src_filter = f1.text_input("source filter", value="", key="recon_src")
        type_filter = f2.text_input("type filter", value="", key="recon_type")
        status_filter = f3.selectbox(
            "status", ["", "open", "timing", "real", "resolved", "escalated"], key="recon_status"
        )

    params: dict[str, str] = {}
    if src_filter:
        params["source"] = src_filter
    if type_filter:
        params["type"] = type_filter
    if status_filter:
        params["status"] = status_filter

    breaks_body = safe_get(recon, "/v1/breaks", params=params or None)
    breaks: list[dict] = []
    if isinstance(breaks_body, dict):
        breaks = breaks_body.get("breaks", []) or []
    bdf = list_to_frame(breaks)
    if not bdf.empty:
        age_col = next(
            (c for c in ("created_at", "detected_at", "timestamp") if c in bdf.columns),
            None,
        )
        if age_col:
            bdf = bdf.copy()
            bdf["aging_bucket"] = bdf[age_col].map(_aging_bucket)
    empty_state("breaks", bdf)
    if not bdf.empty:
        st.dataframe(bdf, width="stretch", hide_index=True)

    section(
        "⏳ Aging buckets",
        "Aging buckets group breaks by how long they've been open (0-1h, 1-4h, 4-24h, "
        "24h+). Older breaks are higher risk and should be resolved first.",
    )
    if not bdf.empty and "aging_bucket" in bdf.columns:
        counts = bdf["aging_bucket"].value_counts().reindex(
            ["0-1h", "1-4h", "4-24h", "24h+", "unknown"], fill_value=0
        )
        st.bar_chart(counts)
    else:
        st.info("No aging data — no breaks to bucket.")

    section(
        "🔍 Break detail & resolution",
        "Select a break to inspect its full detail, then resolve it (mark it as a "
        "timing difference or a real discrepancy) or escalate it to another team. "
        "Opening the action button shows the resolution form.",
    )
    selected_break: str | None = None
    if not bdf.empty and "id" in bdf.columns:
        selected_break = st.selectbox(
            "Select break", options=bdf["id"].tolist(), key="recon_break_sel"
        )
    if selected_break:
        detail = safe_get(recon, f"/v1/breaks/{selected_break}")
        if isinstance(detail, dict):
            st.json(detail)
        st.session_state["recon_selected_break"] = selected_break
        rcol1, rcol2 = st.columns(2)
        with rcol1:
            action_button(
                "Resolve break", _resolve_dialog, key="recon_open_resolve"
            )
        with rcol2:
            action_button(
                "Escalate break", _escalate_dialog, key="recon_open_escalate"
            )

    st.divider()

    section(
        "🔍 Recon run lookup",
        "The reconciliation API exposes recon runs by ID, not as a list. "
        "Enter a run ID to inspect its status and report.",
    )
    run_id = st.text_input("recon run ID", value="", key="recon_run_id")
    if run_id:
        run_detail = safe_get(recon, f"/v1/recon-runs/{run_id}")
        if isinstance(run_detail, dict):
            st.json(run_detail)
            rcol1, rcol2 = st.columns(2)
            with rcol1:
                if st.button("View JSON report"):
                    report = safe_get(recon, f"/v1/recon-runs/{run_id}/report", params={"fmt": "json"})
                    if isinstance(report, str):
                        st.code(report, language="json")
                    elif isinstance(report, dict):
                        st.json(report)
                    elif report is not None:
                        st.write(report)
            with rcol2:
                if st.button("View CSV report"):
                    resp = recon.get(f"/v1/recon-runs/{run_id}/report", params={"fmt": "csv"})
                    if resp.status_code < 400:
                        st.download_button(
                            "Download report.csv",
                            resp.content,
                            file_name=f"recon_run_{run_id}.csv",
                            mime="text/csv",
                        )
                    else:
                        st.warning(f"Report fetch failed: {resp.status_code}")
        else:
            st.info("Recon run not found.")
    else:
        st.info("Enter a recon run ID above to view details.")

    section(
        "▶️ Trigger an EOD recon run",
        "Kick off an end-of-day reconciliation run against a chosen source (ledger, "
        "bank, exchange, onchain, or custody). Pick the scope and mode, then submit.",
    )
    action_button("Trigger an EOD recon run", _recon_run_dialog, key="recon_open_run")

    section(
        "📊 Resolution stats",
        "A breakdown of how breaks are currently distributed across statuses (open, "
        "resolved, escalated, etc.) so you can see overall health at a glance.",
    )
    if not bdf.empty and "status" in bdf.columns:
        st.bar_chart(bdf["status"].value_counts())
    else:
        st.info("No break status data.")

    section(
        "📤 Export",
        "Download the current break queue as a CSV or JSON file for offline analysis "
        "or sharing.",
    )
    ec1, ec2 = st.columns(2)
    with ec1:
        if st.button("Export breaks (CSV)"):
            resp = recon.get("/v1/breaks-export", params={"fmt": "csv"})
            if resp.status_code < 400:
                st.download_button(
                    "Download breaks.csv",
                    resp.content,
                    file_name="breaks.csv",
                    mime="text/csv",
                )
            else:
                st.warning(f"Export failed: {resp.status_code}")
    with ec2:
        if st.button("Export breaks (JSON)"):
            resp = recon.get("/v1/breaks-export", params={"fmt": "json"})
            if resp.status_code < 400:
                st.download_button(
                    "Download breaks.json",
                    resp.content,
                    file_name="breaks.json",
                    mime="application/json",
                )
            else:
                st.warning(f"Export failed: {resp.status_code}")


@st.dialog("Resolve break")
def _resolve_dialog() -> None:
    """Collect resolution inputs and resolve the selected break."""
    recon = client("reconciliation")
    selected_break = st.session_state.get("recon_selected_break")
    if not selected_break:
        st.warning("No break selected.")
        return
    r1, r2 = st.columns(2)
    resolution = r1.selectbox("resolution", ["timing", "real"], key="recon_res")
    actor = r2.text_input("actor", value="bo-ui-operator", key="recon_actor")
    note = st.text_input("note", value="", key="recon_note")
    if st.button("Resolve break", type="primary"):
        payload = {"actor": actor, "note": note, "resolution": resolution}
        result = safe_post(recon, f"/v1/breaks/{selected_break}/resolve", json=payload)
        if result is not None:
            st.success(f"Break resolved: {result}")


@st.dialog("Escalate break")
def _escalate_dialog() -> None:
    """Collect actor and escalate the selected break."""
    recon = client("reconciliation")
    selected_break = st.session_state.get("recon_selected_break")
    if not selected_break:
        st.warning("No break selected.")
        return
    actor = st.text_input("actor", value="bo-ui-operator", key="recon_esc_actor")
    if st.button("Escalate break", type="primary"):
        payload = {"actor": actor}
        result = safe_post(recon, f"/v1/breaks/{selected_break}/escalate", json=payload)
        if result is not None:
            st.success(f"Break escalated: {result}")


@st.dialog("Trigger an EOD recon run")
def _recon_run_dialog() -> None:
    """Collect recon-run inputs and submit them to the reconciliation service."""
    recon = client("reconciliation")
    run_source = st.selectbox("source", ["ledger", "bank", "exchange", "onchain", "custody"], key="recon_run_src")
    run_scope = st.selectbox("scope", ["daily", "intraday"], key="recon_run_scope")
    run_mode = st.selectbox("mode", ["eod", "continuous"], key="recon_run_mode")
    if st.button("Run recon", type="primary"):
        payload = {"source": run_source, "scope": run_scope, "mode": run_mode}
        result = safe_post(recon, "/v1/recon-runs", json=payload)
        if result is not None:
            st.success(f"Recon run created: {result}")
