"""Streamlit entry point for the Back Office UI.

Run locally with:  streamlit run src/back_office_ui/app.py
"""

from __future__ import annotations

import streamlit as st

from back_office_ui.config import get_settings
from back_office_ui.dashboards import (
    fx_hedging,
    ledger,
    liquidity,
    mpc_signing,
    reconciliation,
    settlement,
    treasury,
    wallet,
)
from back_office_ui.data import SERVICE_LABELS, backend_clients, health_check

PAGES = [
    st.Page(treasury.render, title="Treasury", icon="🏛️", url_path="treasury", default=True),
    st.Page(liquidity.render, title="Liquidity", icon="🔄", url_path="liquidity"),
    st.Page(fx_hedging.render, title="FX Hedging", icon="📈", url_path="fx_hedging"),
    st.Page(ledger.render, title="Ledger", icon="📖", url_path="ledger"),
    st.Page(reconciliation.render, title="Reconciliation", icon="🧮", url_path="reconciliation"),
    st.Page(wallet.render, title="Wallets", icon="👛", url_path="wallets"),
    st.Page(settlement.render, title="Settlement", icon="💳", url_path="settlement"),
    st.Page(mpc_signing.render, title="MPC Signing", icon="✍️", url_path="mpc_signing"),
]


def main() -> None:
    st.set_page_config(
        page_title="Back Office UI",
        page_icon="🏛️",
        layout="wide",
    )

    settings = get_settings()
    st.session_state.setdefault("settings", settings)
    backend_clients()

    pg = st.navigation(PAGES)
    with st.sidebar:
        with st.expander("🔌 Services", expanded=False):
            clients = backend_clients()
            for svc_name, label in SERVICE_LABELS:
                ok = health_check(clients[svc_name])
                icon = "🟢" if ok else "🔴"
                st.write(f"{icon} {label}")
    pg.run()


if __name__ == "__main__":
    main()
