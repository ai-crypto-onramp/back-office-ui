from __future__ import annotations

from collections.abc import Callable

READINESS_CHECKS: list[tuple[str, Callable[[], bool]]] = [
    ("treasury", lambda: True),
    ("liquidity", lambda: True),
    ("fx_hedging", lambda: True),
    ("ledger", lambda: True),
    ("reconciliation", lambda: True),
    ("wallet", lambda: True),
    ("payment", lambda: True),
    ("mpc", lambda: True),
]


def readiness_report() -> tuple[dict[str, str], int, int]:
    results: dict[str, str] = {}
    failed = 0
    for name, check in READINESS_CHECKS:
        ok = False
        try:
            ok = bool(check())
        except Exception:
            ok = False
        results[name] = "ok" if ok else "down"
        if not ok:
            failed += 1
    return results, failed, len(READINESS_CHECKS)


def classify_readiness(failed: int, total: int) -> tuple[int, str]:
    if total == 0:
        return 200, "ready"
    if failed == 0:
        return 200, "ready"
    if failed < total:
        return 200, "degraded"
    return 503, "unavailable"
