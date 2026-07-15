"""Streamlit entry point for the Back Office UI.

Run locally with:  streamlit run src/back_office_ui/app.py
"""

from __future__ import annotations

import streamlit as st

from back_office_ui.config import get_settings
from back_office_ui.data import backend_clients
from back_office_ui.pages import (
    fx_hedging,
    ledger,
    liquidity,
    mpc_signing,
    reconciliation,
    settlement,
    treasury,
    wallet,
)

PAGES = [
    ("Treasury Dashboard", treasury),
    ("Liquidity Routing", liquidity),
    ("FX Hedging", fx_hedging),
    ("Ledger Viewer", ledger),
    ("Reconciliation", reconciliation),
    ("Wallet Inventory", wallet),
    ("Settlement & Rail", settlement),
    ("MPC Signing", mpc_signing),
]


def main() -> None:
    settings = get_settings()
    st.session_state.setdefault("settings", settings)
    backend_clients()

    st.set_page_config(
        page_title="Back Office UI",
        page_icon="🏛️",
        layout="wide",
    )
    st.title("Back Office UI")
    st.caption("Treasury and finance console for the crypto on-ramp.")

    with st.sidebar:
        st.header("Navigation")
        choice = st.radio(
            "Page",
            options=[name for name, _ in PAGES],
            label_visibility="collapsed",
        )
        st.divider()
        st.subheader("Backend Services")
        st.write(f"Treasury: `{settings.treasury_url}`")
        st.write(f"Liquidity: `{settings.liquidity_url}`")
        st.write(f"FX Hedging: `{settings.fx_hedging_url}`")
        st.write(f"Ledger: `{settings.ledger_url}`")
        st.write(f"Reconciliation: `{settings.reconciliation_url}`")
        st.write(f"Wallet: `{settings.wallet_url}`")
        st.write(f"Payment: `{settings.payment_url}`")
        st.write(f"MPC Signing: `{settings.mpc_url}`")

    page_module = next(mod for name, mod in PAGES if name == choice)
    page_module.render()


if __name__ == "__main__":
    main()
