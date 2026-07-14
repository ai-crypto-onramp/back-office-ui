from __future__ import annotations

from back_office_ui.health import classify_readiness, readiness_report


def test_readiness_report_all_ok() -> None:
    results, failed, total = readiness_report()
    assert failed == 0
    assert total > 0
    assert all(v == "ok" for v in results.values())


def test_classify_readiness() -> None:
    assert classify_readiness(0, 8) == (200, "ready")
    assert classify_readiness(3, 8) == (200, "degraded")
    assert classify_readiness(8, 8) == (503, "unavailable")
    assert classify_readiness(0, 0) == (200, "ready")
