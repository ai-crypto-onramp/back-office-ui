# Project Plan — Back Office UI

Treasury and finance console for the crypto on-ramp. Built in Python
with Streamlit, consuming backend services via REST and reusing the
existing Python analytics stack (pandas, polars). Covers treasury
dashboard, liquidity routing, FX hedging, ledger viewer,
reconciliation, wallet inventory, settlement, and MPC signing monitor.

## Stage 1 — Project Scaffolding & CI

**Goal:** Stand up the Streamlit app with CI and testing.

**Tasks:**
- [x] Initialize Python project (pyproject.toml, requirements.txt).
- [x] Add Streamlit app entry point with navigation sidebar.
- [x] Add ruff + mypy configuration.
- [x] Configure CI: lint, typecheck, test (pytest).
- [x] Add Dockerfile (multi-stage, streamlit serve).
- [x] Codecov badge and reporting wired.
- [x] Set up environment variable management (.env.example).
- [x] Add HTTP client helpers for backend service calls (httpx).

**Acceptance criteria:**
- `streamlit run app.py` starts the app on port 8501.
- `ruff check` and `mypy` pass with zero errors.
- Docker image builds and serves the app.

## Stage 2 — Treasury Dashboard

**Goal:** Aggregate view of treasury operations
(treasury-orchestration).

**Tasks:**
- [x] Aggregate buy orders table (batch ID, total amount, asset, status, created_at).
- [x] T+0 vs T+2/3 float exposure chart (bar chart by settlement date).
- [x] Hot/warm wallet funding status (chain, balance, target, deficit/surplus).
- [x] Rebalancing queue (pending transfers, amount, from → to wallet).
- [x] Batch creation form (select user orders to aggregate).
- [x] Float utilization gauge (committed vs available).

**Acceptance criteria:**
- Treasury ops can see current float exposure and wallet funding gaps at a glance.
- Rebalancing queue is visible and actionable.

## Stage 3 — Liquidity Routing Console

**Goal:** Venue health and execution monitoring
(liquidity-routing, exchange-connectors).

**Tasks:**
- [x] Venue health table (exchange name, status, latency, last_heartbeat).
- [x] Active child orders table (parent ID, venue, side, amount, filled, status).
- [x] TWAP execution progress (slices executed vs total, time remaining).
- [x] Slippage analysis chart (expected vs actual fill price per order).
- [x] Order routing diagram (parent → child orders across venues).

**Acceptance criteria:**
- Operators can monitor venue health and execution progress in real-time.
- Slippage is visible per order for post-trade analysis.

## Stage 4 — FX Hedging Monitor

**Goal:** Currency exposure and hedge tracking (fx-hedging).

**Tasks:**
- [x] Currency exposure by pair (fiat/crypto, net exposure, hedge ratio).
- [x] Active hedge positions table (pair, notional, entry rate, current rate, PnL).
- [x] Slippage vs benchmark chart (historical, per pair).
- [x] Hedge execution log (timestamp, pair, amount, rate, venue).

**Acceptance criteria:**
- Finance team can see net currency exposure and hedge coverage at a glance.
- PnL on hedges is calculated and displayed in real-time.

## Stage 5 — Ledger Viewer

**Goal:** Double-entry ledger exploration (ledger-accounting).

**Tasks:**
- [x] Account list with balances (asset, liability, equity categories).
- [x] Journal entry search (by tx_id, account, date range).
- [x] Entry detail view (debit/credit lines, reference tx_id, timestamp).
- [x] Trial balance report (all accounts, debit/credit totals).
- [x] Balance history chart per account (time series).
- [x] Export to CSV for accounting system import.

**Acceptance criteria:**
- Finance can search and verify any ledger entry.
- Trial balance is always in balance (debits = credits).

## Stage 6 — Reconciliation Dashboard

**Goal:** Break detection and resolution (reconciliation).

**Tasks:**
- [x] Break queue with filters (source, type, status, age, severity).
- [x] Break detail: expected vs actual amount, source (bank/exchange/on-chain/custody).
- [x] Aging buckets chart (0-1h, 1-4h, 4-24h, 24h+).
- [x] Auto-resolved vs manual resolution stats.
- [x] Per-source match status (ledger vs each external source).
- [x] EOD recon run history (run ID, timestamp, breaks found, breaks resolved).
- [x] Break resolution form (mark as timing/real, add notes, close).

**Acceptance criteria:**
- Recon team can triage and resolve breaks from the dashboard.
- Aging visibility ensures stale breaks are escalated.

## Stage 7 — Wallet Inventory

**Goal:** Wallet state and key management (wallet-management).

**Tasks:**
- [x] Wallet inventory table (chain, type [hot/warm/cold], address, balance, status).
- [x] Key rotation status (current key index, last rotation date, next scheduled).
- [x] UTXO set viewer (BTC — txout, amount, confirmations, spendable).
- [x] Address derivation audit log (index, address, derived_at, used_in_tx).
- [x] Balance chart per wallet (time series, confirmed vs unconfirmed).

**Acceptance criteria:**
- Treasury can see all wallet balances and key health at a glance.
- Key rotation schedule is visible and actionable.

## Stage 8 — Settlement & Rail Status

**Goal:** Payment settlement and chargeback monitoring
(payment-orchestration, rail-connectors).

**Tasks:**
- [x] Settlement status table (payment ID, rail, amount, status, settled_at).
- [x] Chargeback list (payment ID, reason, amount, status, disputed_at).
- [x] 3DS auth records (payment ID, auth result, ACS URL, liability shift).
- [x] Rail health indicators (per-rail latency, success rate, last error).
- [x] Pending settlement aging (unsettled payments by age).

**Acceptance criteria:**
- Finance can track settlement status and identify stale/unsettled payments.
- Chargebacks are visible with dispute status.

## Stage 9 — MPC Signing Monitor

**Goal:** Signing session and key ceremony visibility
(mpc-signing-service).

**Tasks:**
- [x] Active signing sessions (session ID, tx_id, threshold t/n, status, participants).
- [x] Key rotation / DKG event log (ceremony ID, participants, status, completed_at).
- [x] Threshold node health table (node ID, status, last heartbeat, version).
- [x] Signing latency metrics (p50, p99 over time).

**Acceptance criteria:**
- Security ops can monitor signing ceremonies and node health.
- Key ceremonies are auditable after the fact.

## Stage 10 — E2E Tests & Deployment

**Goal:** Tests and deployment pipeline.

**Tasks:**
- [x] pytest integration tests for critical data flows (treasury → ledger → recon).
- [x] Add to `.github/docker-compose.yml` for the integration stack.
- [x] Deployment config (containerized, internal network only).

**Acceptance criteria:**
- Tests cover the treasury-to-reconciliation data flow.
- App runs in docker-compose alongside the backend services.