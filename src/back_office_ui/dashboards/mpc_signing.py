"""Stage 9 — MPC Signing Monitor (mpc-signing-service)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..data import client, safe_get
from . import section


def render() -> None:
    st.header("✍️ MPC Signing Monitor")
    st.caption("Signing sessions, key ceremonies, and threshold node health.")
    mpc = client("mpc")

    section(
        "ℹ️ About this monitor",
        "MPC (Multi-Party Computation) signing spreads the private key across several "
        "nodes so no single node ever holds the full key. The signing API is gRPC on "
        "the internal network, so this monitor reports service health and webhook "
        "status. Signing session and ceremony visibility will be wired via the gRPC "
        "reflection surface in a follow-up.",
    )
    st.info(
        "The MPC signing API is gRPC on the internal network "
        "(mpc-signing-service:9090). The HTTP surface exposes /healthz and "
        "the custody webhook, so this monitor reports service health and "
        "webhook status. Signing session / ceremony visibility will be wired "
        "via the gRPC reflection surface in a follow-up."
    )

    section(
        "💚 Service health",
        "A simple health check against the MPC signing service. A green status means "
        "the service is up and reachable.",
    )
    health_body = safe_get(mpc, "/healthz")
    if isinstance(health_body, dict):
        st.metric("Status", health_body.get("status", "-"))
        st.json(health_body)
    else:
        st.warning("MPC signing service is unreachable.")

    section(
        "🔗 Custody webhook",
        "The custody webhook receives signed-payload notifications from our custody "
        "provider. It returns 501 until CUSTODY_WEBHOOK_SECRET is configured for a "
        "provider. Use the button below to probe the webhook endpoint.",
    )
    st.caption(
        "POST /v1/custody/webhook returns 501 until CUSTODY_WEBHOOK_SECRET is "
        "configured for a provider."
    )
    if st.button("Probe custody webhook"):
        try:
            resp = mpc.post("/v1/custody/webhook", json={})
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Webhook probe failed: {exc}")
            resp = None
        if resp is not None:
            st.write(f"Status: {resp.status_code}")
            try:
                st.json(resp.json())
            except Exception:  # noqa: BLE001
                st.write(resp.text[:500])

    section(
        "⏱️ Signing latency metrics",
        "Signing latency (p50/p99) shows how long signing operations take. This "
        "requires a metrics endpoint that the service doesn't expose yet.",
    )
    st.caption("Latency p50/p99 require a metrics endpoint; not yet exposed by the service.")

    section(
        "🖥️ Threshold node health",
        "Threshold node health reports whether each node in the MPC quorum is online "
        "and heartbeating. Node health is reported over the internal gRPC control "
        "plane, so only a placeholder is shown here for now.",
    )
    st.caption("Node health is reported over the internal gRPC control plane.")
    st.dataframe(
        pd.DataFrame(
            [{"node_id": "node-0", "status": "unknown", "last_heartbeat": "-", "version": "-"}]
        ),
        width="stretch",
        hide_index=True,
    )
