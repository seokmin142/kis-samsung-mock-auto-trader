from __future__ import annotations

import logging
from pathlib import Path

from samsung_trader.clock import KSTClock


class ClockFilter(logging.Filter):
    def __init__(self, clock: KSTClock) -> None:
        super().__init__()
        self.clock = clock

    def filter(self, record: logging.LogRecord) -> bool:
        record.kst_time = self.clock.now().isoformat(timespec="seconds")
        return True


def setup_logging(log_dir: Path, clock: KSTClock) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("samsung_trader")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        "%(kst_time)s | %(levelname)s | %(name)s | %(message)s"
    )
    clock_filter = ClockFilter(clock)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(clock_filter)
    logger.addHandler(console)

    filename = log_dir / f"trader_{clock.now():%Y%m%d}.log"
    file_handler = logging.FileHandler(filename, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(clock_filter)
    logger.addHandler(file_handler)
    return logger
