"""Stage 6 — Reconciliation Dashboard (reconciliation)."""

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
    st.header("Reconciliation Dashboard")
    st.caption("Break detection, aging, and resolution against ledger vs external sources.")
    recon = client("reconciliation")

    st.subheader("Break queue")
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
        st.dataframe(bdf, use_container_width=True, hide_index=True)

    st.subheader("Aging buckets")
    if not bdf.empty and "aging_bucket" in bdf.columns:
        counts = bdf["aging_bucket"].value_counts().reindex(
            ["0-1h", "1-4h", "4-24h", "24h+", "unknown"], fill_value=0
        )
        st.bar_chart(counts)
    else:
        st.info("No aging data — no breaks to bucket.")

    st.subheader("Break detail & resolution")
    selected_break: str | None = None
    if not bdf.empty and "id" in bdf.columns:
        selected_break = st.selectbox(
            "Select break", options=bdf["id"].tolist(), key="recon_break_sel"
        )
    if selected_break:
        detail = safe_get(recon, f"/v1/breaks/{selected_break}")
        if isinstance(detail, dict):
            st.json(detail)
        with st.container(border=True):
            r1, r2 = st.columns(2)
            resolution = r1.selectbox("resolution", ["timing", "real"], key="recon_res")
            actor = r2.text_input("actor", value="bo-ui-operator", key="recon_actor")
            note = st.text_input("note", value="", key="recon_note")
            if st.button("Resolve break", type="primary"):
                payload = {"actor": actor, "note": note, "resolution": resolution}
                result = safe_post(recon, f"/v1/breaks/{selected_break}/resolve", json=payload)
                if result is not None:
                    st.success(f"Break resolved: {result}")
            if st.button("Escalate break"):
                payload = {"actor": actor}
                result = safe_post(recon, f"/v1/breaks/{selected_break}/escalate", json=payload)
                if result is not None:
                    st.success(f"Break escalated: {result}")

    st.divider()

    st.subheader("Recon runs")
    runs_body = safe_get(recon, "/v1/recon-runs")
    runs: list[dict] = []
    if isinstance(runs_body, dict):
        runs = runs_body.get("recon_runs", []) or runs_body.get("runs", []) or []
    elif isinstance(runs_body, list):
        runs = runs_body
    rdf = list_to_frame(runs)
    empty_state("recon runs", rdf)
    if not rdf.empty:
        st.dataframe(rdf, use_container_width=True, hide_index=True)

    with st.expander("Trigger an EOD recon run", expanded=False):
        with st.container(border=True):
            run_source = st.selectbox("source", ["ledger", "bank", "exchange", "onchain", "custody"], key="recon_run_src")
            run_scope = st.selectbox("scope", ["daily", "intraday"], key="recon_run_scope")
            run_mode = st.selectbox("mode", ["eod", "continuous"], key="recon_run_mode")
            if st.button("Run recon", type="primary"):
                payload = {"source": run_source, "scope": run_scope, "mode": run_mode}
                result = safe_post(recon, "/v1/recon-runs", json=payload)
                if result is not None:
                    st.success(f"Recon run created: {result}")

    st.subheader("Resolution stats")
    if not bdf.empty and "status" in bdf.columns:
        st.bar_chart(bdf["status"].value_counts())
    else:
        st.info("No break status data.")

    st.subheader("Export")
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
