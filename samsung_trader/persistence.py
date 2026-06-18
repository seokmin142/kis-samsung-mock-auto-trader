from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from samsung_trader.clock import KSTClock


SENSITIVE_FRAGMENTS = (
    "account",
    "appkey",
    "app_key",
    "appsecret",
    "app_secret",
    "authorization",
    "token",
)


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "<redacted>"
                if any(fragment in key.lower() for fragment in SENSITIVE_FRAGMENTS)
                else sanitize(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


class EventRecorder:
    def __init__(self, records_dir: Path, clock: KSTClock) -> None:
        self.clock = clock
        records_dir.mkdir(parents=True, exist_ok=True)
        self.records_dir = records_dir

    @property
    def path(self) -> Path:
        return self.records_dir / f"trading_{self.clock.now():%Y%m%d}.jsonl"

    def record(self, event: str, **fields: Any) -> None:
        payload = {
            "timestamp_kst": self.clock.now().isoformat(timespec="seconds"),
            "event": event,
            **sanitize(fields),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


@dataclass
class DailyState:
    date_kst: str
    order_pairs: int = 0
    order_ids: list[str] = field(default_factory=list)
    buy_order_id: str = ""
    sell_order_id: str = ""
    planned_sell_price: int = 0
    holding_before: int = 0


class DailyStateStore:
    def __init__(self, runtime_dir: Path) -> None:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir = runtime_dir

    def _path(self, date_kst: str) -> Path:
        return self.runtime_dir / f"state_{date_kst}.json"

    def load(self, date_kst: str) -> DailyState:
        path = self._path(date_kst)
        if not path.exists():
            return DailyState(date_kst=date_kst)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("date_kst") != date_kst:
                return DailyState(date_kst=date_kst)
            return DailyState(
                date_kst=date_kst,
                order_pairs=int(data.get("order_pairs", 0)),
                order_ids=[str(value) for value in data.get("order_ids", [])],
                buy_order_id=str(data.get("buy_order_id", "")),
                sell_order_id=str(data.get("sell_order_id", "")),
                planned_sell_price=int(data.get("planned_sell_price", 0)),
                holding_before=int(data.get("holding_before", 0)),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return DailyState(date_kst=date_kst)

    def save(self, state: DailyState) -> None:
        path = self._path(state.date_kst)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "date_kst": state.date_kst,
                    "order_pairs": state.order_pairs,
                    "order_ids": state.order_ids,
                    "buy_order_id": state.buy_order_id,
                    "sell_order_id": state.sell_order_id,
                    "planned_sell_price": state.planned_sell_price,
                    "holding_before": state.holding_before,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(path)
