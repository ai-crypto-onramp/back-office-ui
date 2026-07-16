"""Shared helpers for fetching and shaping backend data."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from .clients import BackendClient


def safe_get(client: BackendClient, path: str, **kwargs: Any) -> dict[str, Any] | list[Any] | None:
    """GET ``path`` from ``client``, returning parsed JSON or ``None`` on error.

    Errors are surfaced via ``st.warning`` so dashboards can degrade gracefully.
    """
    try:
        resp = client.get(path, **kwargs)
    except Exception as exc:  # noqa: BLE001 - network errors are varied
        st.warning(f"Could not reach `{client._base}{path}`: {exc}")
        return None
    if resp.status_code >= 400:
        st.warning(f"`{path}` returned {resp.status_code}: {resp.text[:200]}")
        return None
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        st.warning(f"`{path}` returned non-JSON body.")
        return None


def safe_post(
    client: BackendClient, path: str, **kwargs: Any
) -> dict[str, Any] | list[Any] | None:
    """POST to ``path`` from ``client``, returning parsed JSON or ``None``."""
    try:
        resp = client.post(path, **kwargs)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Could not reach `{client._base}{path}`: {exc}")
        return None
    if resp.status_code >= 400:
        st.warning(f"`{path}` returned {resp.status_code}: {resp.text[:200]}")
        return None
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return None


def list_to_frame(items: list[dict[str, Any]] | None) -> pd.DataFrame:
    """Convert a list of dicts to a DataFrame, empty if missing.

    List-valued columns where every element of every row is a string are kept
    as Python lists so Streamlit renders them as pills/badges in
    ``st.dataframe``. Other object-dtype columns with mixed types are
    stringified so Arrow serialization doesn't fail.
    """
    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    for col in df.columns:
        if df[col].dtype != "object":
            continue
        vals = df[col].dropna()
        if not vals.empty and vals.map(lambda v: isinstance(v, list)).all():
            if vals.map(lambda lst: all(isinstance(x, str) for x in lst)).all():
                continue
        try:
            pd.Series(df[col].tolist(), dtype="string")
        except (TypeError, ValueError):
            df[col] = df[col].astype(str)
    return df


def empty_state(label: str, frame: pd.DataFrame) -> None:
    """Show an info callout when a DataFrame is empty."""
    if frame.empty:
        st.info(f"No {label} available.")


def backend_clients() -> dict[str, BackendClient]:
    """Build a BackendClient per backend service from cached settings."""
    settings = st.session_state.get("settings")
    if settings is None:
        from .config import get_settings

        settings = get_settings()
        st.session_state["settings"] = settings
    return {
        "treasury": BackendClient(settings.treasury_url),
        "liquidity": BackendClient(settings.liquidity_url),
        "fx_hedging": BackendClient(settings.fx_hedging_url),
        "ledger": BackendClient(settings.ledger_url),
        "reconciliation": BackendClient(settings.reconciliation_url),
        "wallet": BackendClient(settings.wallet_url),
        "payment": BackendClient(settings.payment_url),
        "mpc": BackendClient(settings.mpc_url),
        "pricing": BackendClient(settings.pricing_url),
        "notification": BackendClient(settings.notification_url),
    }


def client(name: str) -> BackendClient:
    """Return a backend client by name from :func:`backend_clients`."""
    return backend_clients()[name]


def health_check(c: BackendClient, timeout: float = 2.0) -> bool:
    """Return ``True`` if the service responds on ``/healthz``."""
    try:
        resp = c.get("/healthz", timeout=timeout)
        return resp.status_code < 400
    except Exception:  # noqa: BLE001
        return False


SERVICE_LABELS: list[tuple[str, str]] = [
    ("treasury", "Treasury"),
    ("liquidity", "Liquidity"),
    ("fx_hedging", "FX Hedging"),
    ("ledger", "Ledger"),
    ("reconciliation", "Reconciliation"),
    ("wallet", "Wallet"),
    ("payment", "Payment"),
    ("mpc", "MPC Signing"),
    ("pricing", "Pricing"),
    ("notification", "Notification"),
]
