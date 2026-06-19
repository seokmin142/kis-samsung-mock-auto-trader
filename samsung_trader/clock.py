from __future__ import annotations

import logging
import time as time_module
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from threading import Event
from zoneinfo import ZoneInfo

import requests


KST = ZoneInfo("Asia/Seoul")


class ClockSyncError(RuntimeError):
    """Raised when the trusted KIS HTTP clock cannot be read."""


class KSTClock:
    """KST clock corrected using the KIS server's HTTP Date header."""

    def __init__(self) -> None:
        self._offset = timedelta(0)
        self._last_sync_monotonic: float | None = None

    @property
    def offset_seconds(self) -> float:
        return self._offset.total_seconds()

    def now(self) -> datetime:
        corrected_utc = datetime.now(timezone.utc) + self._offset
        return corrected_utc.astimezone(KST)

    def observe_date_header(
        self,
        date_header: str | None,
        sent_at_utc: datetime,
        received_at_utc: datetime,
    ) -> None:
        if not date_header:
            return
        server_utc = parsedate_to_datetime(date_header).astimezone(timezone.utc)
        midpoint = sent_at_utc + (received_at_utc - sent_at_utc) / 2
        self._offset = server_utc - midpoint
        self._last_sync_monotonic = time_module.monotonic()

    def sync(self, session: requests.Session, base_url: str, timeout: float = 15.0) -> float:
        sent = datetime.now(timezone.utc)
        response = session.head(base_url, timeout=timeout)
        received = datetime.now(timezone.utc)
        response.raise_for_status()
        date_header = response.headers.get("Date")
        if not date_header:
            raise ClockSyncError("KIS server did not return an HTTP Date header")
        self.observe_date_header(date_header, sent, received)
        return self.offset_seconds

    def resync_if_due(
        self,
        session: requests.Session,
        base_url: str,
        interval_seconds: int = 3_600,
    ) -> None:
        if (
            self._last_sync_monotonic is None
            or time_module.monotonic() - self._last_sync_monotonic >= interval_seconds
        ):
            self.sync(session, base_url)

    def at(self, day: date, value: time) -> datetime:
        return datetime.combine(day, value, tzinfo=KST)

    def sleep_until(
        self,
        target: datetime,
        stop_event: Event,
        logger: logging.Logger,
    ) -> bool:
        while not stop_event.is_set():
            remaining = (target - self.now()).total_seconds()
            if remaining <= 0:
                return True
            logger.debug("waiting %.1f seconds", remaining)
            stop_event.wait(min(remaining, 30.0))
        return False
