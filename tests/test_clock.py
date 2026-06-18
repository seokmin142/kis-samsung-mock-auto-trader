from datetime import date, datetime, time, timezone

from samsung_trader.clock import KSTClock


def test_clock_observes_http_date_midpoint() -> None:
    clock = KSTClock()
    sent = datetime(2026, 6, 18, 0, 0, 0, tzinfo=timezone.utc)
    received = datetime(2026, 6, 18, 0, 0, 2, tzinfo=timezone.utc)
    clock.observe_date_header("Thu, 18 Jun 2026 00:00:03 GMT", sent, received)
    assert clock.offset_seconds == 2.0


def test_clock_builds_kst_window() -> None:
    clock = KSTClock()
    value = clock.at(date(2026, 6, 19), time(9, 10))
    assert value.isoformat() == "2026-06-19T09:10:00+09:00"
