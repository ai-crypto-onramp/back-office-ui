from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


@dataclass(frozen=True)
class Settings:
    port: int = field(default_factory=lambda: int(_env("STREAMLIT_SERVER_PORT", "8501") or "8501"))
    treasury_url: str = field(default_factory=lambda: _env("TREASURY_URL", "http://treasury-orchestration:8080") or "http://treasury-orchestration:8080")
    liquidity_url: str = field(default_factory=lambda: _env("LIQUIDITY_URL", "http://liquidity-routing:8080") or "http://liquidity-routing:8080")
    fx_hedging_url: str = field(default_factory=lambda: _env("FX_HEDGING_URL", "http://fx-hedging:8080") or "http://fx-hedging:8080")
    ledger_url: str = field(default_factory=lambda: _env("LEDGER_URL", "http://ledger-accounting:8080") or "http://ledger-accounting:8080")
    reconciliation_url: str = field(default_factory=lambda: _env("RECONCILIATION_URL", "http://reconciliation:8080") or "http://reconciliation:8080")
    wallet_url: str = field(default_factory=lambda: _env("WALLET_URL", "http://wallet-management:8080") or "http://wallet-management:8080")
    payment_url: str = field(default_factory=lambda: _env("PAYMENT_URL", "http://payment-orchestration:8080") or "http://payment-orchestration:8080")
    mpc_url: str = field(default_factory=lambda: _env("MPC_URL", "http://mpc-signing-service:8080") or "http://mpc-signing-service:8080")


def get_settings() -> Settings:
    return Settings()
