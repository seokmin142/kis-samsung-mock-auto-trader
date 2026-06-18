from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path

from dotenv import load_dotenv


MOCK_BASE_URL = "https://openapivts.koreainvestment.com:29443"
SYMBOL = "005930"
STOCK_NAME = "삼성전자"


class ConfigurationError(ValueError):
    """Raised when required settings are absent or unsafe."""


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return value


def split_account(raw: str) -> tuple[str, str]:
    digits = "".join(character for character in raw if character.isdigit())
    if len(digits) != 10:
        raise ConfigurationError(
            "GH_ACCOUNT must contain 10 digits, for example 12345678-01"
        )
    return digits[:8], digits[8:]


@dataclass(frozen=True)
class Settings:
    account_number: str
    account_product_code: str
    app_key: str
    app_secret: str
    base_url: str = MOCK_BASE_URL
    symbol: str = SYMBOL
    stock_name: str = STOCK_NAME
    market_open: time = time(9, 10)
    market_close: time = time(15, 30)
    polling_seconds: int = 180
    monitor_seconds: int = 600
    verification_delay_seconds: int = 30
    price_offset_krw: int = 2_000
    price_tick_krw: int = 100
    order_quantity: int = 1
    max_order_pairs_per_day: int = 1
    request_min_interval_seconds: float = 0.6
    request_timeout_seconds: float = 10.0
    runtime_dir: Path = Path(".runtime")
    records_dir: Path = Path("records")
    logs_dir: Path = Path("logs")

    @classmethod
    def from_env(cls, env_file: Path | None = Path(".env")) -> "Settings":
        if env_file is not None:
            load_dotenv(env_file, override=False)

        account = os.getenv("GH_ACCOUNT", "").strip()
        app_key = os.getenv("GH_APPKEY", "").strip()
        app_secret = os.getenv("GH_APPSECRET", "").strip()
        missing = [
            name
            for name, value in (
                ("GH_ACCOUNT", account),
                ("GH_APPKEY", app_key),
                ("GH_APPSECRET", app_secret),
            )
            if not value
        ]
        if missing:
            raise ConfigurationError(
                "Missing environment variables: " + ", ".join(missing)
            )

        account_number, product_code = split_account(account)
        settings = cls(
            account_number=account_number,
            account_product_code=product_code,
            app_key=app_key,
            app_secret=app_secret,
            polling_seconds=_positive_int("POLL_INTERVAL_SECONDS", 180),
            monitor_seconds=_positive_int("MONITOR_INTERVAL_SECONDS", 600),
            verification_delay_seconds=_positive_int(
                "VERIFICATION_DELAY_SECONDS", 30
            ),
            price_offset_krw=_positive_int("PRICE_OFFSET_KRW", 2_000),
            price_tick_krw=_positive_int("PRICE_TICK_KRW", 100),
            order_quantity=_positive_int("ORDER_QUANTITY", 1),
            max_order_pairs_per_day=_positive_int(
                "MAX_ORDER_PAIRS_PER_DAY", 1
            ),
            request_min_interval_seconds=_positive_float(
                "REQUEST_MIN_INTERVAL_SECONDS", 0.6
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.base_url != MOCK_BASE_URL:
            raise ConfigurationError("Only the KIS mock-trading server is allowed")
        if self.symbol != SYMBOL:
            raise ConfigurationError("This project is locked to Samsung Electronics 005930")
        if not self.app_key or not self.app_secret:
            raise ConfigurationError("Mock app credentials are required")
        if self.market_open >= self.market_close:
            raise ConfigurationError("market_open must be before market_close")
        if self.price_offset_krw % self.price_tick_krw != 0:
            raise ConfigurationError("PRICE_OFFSET_KRW must align to PRICE_TICK_KRW")
