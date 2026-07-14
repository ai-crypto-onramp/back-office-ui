"""Streamlit entry point for the Back Office UI.

Run locally with:  streamlit run src/back_office_ui/app.py
"""

from __future__ import annotations

import streamlit as st

from back_office_ui.config import get_settings


def main() -> None:
    settings = get_settings()
    st.set_page_config(
        page_title="Back Office UI",
        page_icon="🏛️",
        layout="wide",
    )
    st.title("Back Office UI")
    st.caption("Treasury and finance console for the crypto on-ramp.")

    with st.sidebar:
        st.header("Navigation")
        st.markdown(
            """
            - Treasury Dashboard
            - Liquidity Routing
            - FX Hedging
            - Ledger Viewer
            - Reconciliation
            - Wallet Inventory
            - Settlement
            - MPC Signing
            """
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

    st.info(
        "Skeleton app. Pages will be added in subsequent stages "
        "(see PROJECT_PLAN.md)."
    )


if __name__ == "__main__":
    main()
