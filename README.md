# Back Office UI

![CI](https://github.com/ai-crypto-onramp/back-office-ui/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/ai-crypto-onramp/back-office-ui/branch/main/graph/badge.svg)](https://codecov.io/gh/ai-crypto-onramp/back-office-ui)

Treasury and finance console for the crypto on-ramp. Built in Python
with Streamlit, consuming backend services via REST and reusing the
existing Python analytics stack (pandas, polars). Covers treasury
dashboard, liquidity routing, FX hedging, ledger viewer,
reconciliation, wallet inventory, settlement, and MPC signing monitor.

## Overview / Responsibilities

- Single internal console for treasury, finance, and recon operations staff.
- Aggregates data from treasury-orchestration, liquidity-routing, fx-hedging,
  ledger-accounting, reconciliation, wallet-management, payment-orchestration,
  and mpc-signing-service via REST.
- Read-only dashboards by default; mutating actions (batch creation,
  rebalancing, break resolution) gated by role.
- Python/Streamlit front-end reusing the platform's existing analytics stack.

## Language & Tech Stack

- **Language:** Python 3.11
- **UI framework:** Streamlit
- **Data:** pandas, polars
- **HTTP client:** httpx
- **Linting/typecheck:** ruff, mypy
- **Testing:** pytest + pytest-cov
- **Container:** multi-stage Docker image running `streamlit run`

## Project Structure

```
back-office-ui/
├── src/back_office_ui/
│   ├── app.py            # Streamlit entry point
│   ├── config.py         # Settings (env-driven)
│   ├── clients.py        # httpx backend client helpers
│   ├── health.py         # Readiness checks
│   └── health_server.py # FastAPI /healthz, /readyz sidecar
├── tests/                # pytest suite
├── Dockerfile            # Multi-stage, streamlit serve
├── Makefile              # build / test / lint / docker targets
├── pyproject.toml        # ruff + mypy + pytest + coverage config
├── requirements.txt
└── .env.example
```

## Getting Started

```bash
make build          # pip install -e .
make run            # streamlit run on :8501
make test           # pytest with coverage
make lint           # ruff
make typecheck      # mypy
make docker-build   # build image
make docker-run     # run on :8501
```

## Configuration

Copy `.env.example` to `.env` and adjust backend URLs. All settings are
read from environment variables (see `config.py`).

## Health

The container exposes Streamlit's built-in health endpoint at
`/_stcore/health` on port 8501. A FastAPI sidecar
(`back_office_ui.health_server:app`) provides `/healthz` and `/readyz`
on port 8080 for gatus/docker-compose probes.

## CI / Coverage

CI runs on every push and pull request via `.github/workflows/ci.yml`:
lint (ruff), typecheck (mypy), tests (pytest with coverage), Docker
build. Coverage is uploaded to Codecov.