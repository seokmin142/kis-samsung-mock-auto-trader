from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone

import requests

from samsung_trader.clock import KST, KSTClock
from samsung_trader.config import Settings
from samsung_trader.persistence import EventRecorder


class AuthenticationError(RuntimeError):
    """Raised when a mock access token cannot be obtained."""


class TokenManager:
    def __init__(
        self,
        settings: Settings,
        session: requests.Session,
        clock: KSTClock,
        logger: logging.Logger,
        recorder: EventRecorder,
    ) -> None:
        self.settings = settings
        self.session = session
        self.clock = clock
        self.logger = logger
        self.recorder = recorder
        settings.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = settings.runtime_dir / "token_cache.json"

    def get_token(self) -> str:
        cached = self._read_valid_cache()
        if cached is not None:
            self.logger.info("reusing the cached mock access token")
            self.recorder.record("token_reused")
            return cached
        return self._issue_token()

    def invalidate(self) -> None:
        try:
            self.cache_path.unlink(missing_ok=True)
        except OSError:
            pass

    def _read_valid_cache(self) -> str | None:
        if not self.cache_path.exists():
            return None
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            token = str(payload["access_token"])
            issued_date = str(payload["issued_date_kst"])
            expires_at = datetime.fromisoformat(str(payload["expires_at_kst"]))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=KST)
            now = self.clock.now()
            if issued_date != now.date().isoformat():
                return None
            if expires_at <= now + timedelta(minutes=5):
                return None
            return token
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _issue_token(self) -> str:
        url = f"{self.settings.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.settings.app_key,
            "appsecret": self.settings.app_secret,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/plain",
            "charset": "UTF-8",
        }

        response: requests.Response | None = None
        for attempt in range(2):
            sent = datetime.now(timezone.utc)
            try:
                response = self.session.post(
                    url,
                    json=body,
                    headers=headers,
                    timeout=self.settings.request_timeout_seconds,
                )
                received = datetime.now(timezone.utc)
                self.clock.observe_date_header(
                    response.headers.get("Date"), sent, received
                )
                if response.status_code < 500:
                    break
            except requests.RequestException as exc:
                if attempt == 1:
                    raise AuthenticationError("mock token request failed") from exc
            time.sleep(2**attempt)

        if response is None:
            raise AuthenticationError("mock token request produced no response")
        if response.status_code != 200:
            raise AuthenticationError(
                f"mock token request failed with HTTP {response.status_code}"
            )
        try:
            payload = response.json()
            token = str(payload["access_token"])
            expiry_text = str(payload["access_token_token_expired"])
            expiry = datetime.strptime(expiry_text, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=KST
            )
        except (KeyError, TypeError, ValueError, requests.JSONDecodeError) as exc:
            raise AuthenticationError("unexpected mock token response") from exc

        cache = {
            "access_token": token,
            "issued_date_kst": self.clock.now().date().isoformat(),
            "expires_at_kst": expiry.isoformat(),
        }
        temporary = self.cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        temporary.replace(self.cache_path)
        self.logger.info("issued and cached a new mock access token")
        self.recorder.record("token_refreshed", expires_at_kst=expiry.isoformat())
        return token
