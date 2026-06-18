import json
from pathlib import Path

from samsung_trader.clock import KSTClock
from samsung_trader.persistence import DailyState, DailyStateStore, EventRecorder, sanitize


def test_sanitize_redacts_nested_secrets() -> None:
    value = sanitize(
        {"appkey": "secret", "nested": {"authorization": "Bearer x"}, "price": 10}
    )
    assert value == {
        "appkey": "<redacted>",
        "nested": {"authorization": "<redacted>"},
        "price": 10,
    }


def test_event_recorder_does_not_write_sensitive_values(tmp_path: Path) -> None:
    recorder = EventRecorder(tmp_path, KSTClock())
    recorder.record("test", appsecret="never-write", price=70_000)
    payload = json.loads(recorder.path.read_text(encoding="utf-8"))
    assert payload["appsecret"] == "<redacted>"
    assert "never-write" not in recorder.path.read_text(encoding="utf-8")


def test_daily_state_round_trip(tmp_path: Path) -> None:
    store = DailyStateStore(tmp_path)
    state = DailyState(
        date_kst="2026-06-19",
        order_pairs=1,
        order_ids=["123"],
        buy_order_id="123",
        planned_sell_price=72_000,
    )
    store.save(state)
    assert store.load("2026-06-19") == state
