from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests

from samsung_trader.auth import TokenManager
from samsung_trader.clock import KSTClock
from samsung_trader.config import Settings
from samsung_trader.persistence import EventRecorder


class KISApiError(RuntimeError):
    """A definite error response from the KIS mock API."""


class AmbiguousOrderError(KISApiError):
    """An order request timed out and must be verified before any retry."""


class KISClient:
    def __init__(
        self,
        settings: Settings,
        session: requests.Session,
        token_manager: TokenManager,
        clock: KSTClock,
        logger: logging.Logger,
        recorder: EventRecorder,
    ) -> None:
        self.settings = settings
        self.session = session
        self.token_manager = token_manager
        self.clock = clock
        self.logger = logger
        self.recorder = recorder
        self._last_request_monotonic = 0.0

    def get(self, path: str, tr_id: str, params: dict[str, str]) -> dict[str, Any]:
        return self._request("GET", path, tr_id, params=params)

    def post(self, path: str, tr_id: str, body: dict[str, str]) -> dict[str, Any]:
        return self._request("POST", path, tr_id, body=body)

    def _request(
        self,
        method: str,
        path: str,
        tr_id: str,
        *,
        params: dict[str, str] | None = None,
        body: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not tr_id.startswith(("V", "FHKST")):
            raise KISApiError(f"unsafe non-mock TR ID rejected: {tr_id}")

        attempts = 3 if method == "GET" else 1
        for attempt in range(attempts):
            self._respect_rate_limit()
            token = self.token_manager.get_token()
            headers = {
                "Content-Type": "application/json",
                "Accept": "text/plain",
                "charset": "UTF-8",
                "authorization": f"Bearer {token}",
                "appkey": self.settings.app_key,
                "appsecret": self.settings.app_secret,
                "tr_id": tr_id,
                "custtype": "P",
                "tr_cont": "",
            }
            sent = datetime.now(timezone.utc)
            try:
                response = self.session.request(
                    method,
                    f"{self.settings.base_url}{path}",
                    headers=headers,
                    params=params,
                    json=body,
                    timeout=self.settings.request_timeout_seconds,
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                self.logger.warning("API %s failed: %s", method, type(exc).__name__)
                self.recorder.record(
                    "api_transport_error", method=method, path=path, attempt=attempt + 1
                )
                if method == "POST":
                    raise AmbiguousOrderError(
                        "order result is unknown; query today's orders before retrying"
                    ) from exc
                if attempt + 1 == attempts:
                    raise KISApiError("GET request failed after retries") from exc
                time.sleep(2 ** (attempt + 1))
                continue

            received = datetime.now(timezone.utc)
            self.clock.observe_date_header(response.headers.get("Date"), sent, received)
            if response.status_code == 401 and attempt == 0 and method == "GET":
                self.token_manager.invalidate()
                continue
            if response.status_code >= 500 and method == "GET" and attempt + 1 < attempts:
                time.sleep(2 ** (attempt + 1))
                continue
            if response.status_code != 200:
                raise KISApiError(f"KIS HTTP {response.status_code} for {path}")

            try:
                payload = response.json()
            except requests.JSONDecodeError as exc:
                raise KISApiError("KIS returned non-JSON data") from exc

            if str(payload.get("rt_cd", "0")) != "0":
                code = str(payload.get("msg_cd", "UNKNOWN"))
                message = str(payload.get("msg1", "KIS API error"))
                self.logger.error("KIS error %s: %s", code, message)
                self.recorder.record(
                    "api_error", path=path, message_code=code, message=message
                )
                if code == "EGW00201" and method == "GET" and attempt + 1 < attempts:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise KISApiError(f"{code}: {message}")
            return payload

        raise KISApiError("request exhausted without a result")

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_monotonic
        wait = self.settings.request_min_interval_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_monotonic = time.monotonic()
