from datetime import time

import pytest

from samsung_trader.config import ConfigurationError, Settings, split_account


def test_split_account_accepts_common_formats() -> None:
    assert split_account("12345678-01") == ("12345678", "01")
    assert split_account("1234567801") == ("12345678", "01")


def test_split_account_rejects_wrong_length() -> None:
    with pytest.raises(ConfigurationError):
        split_account("1234")


def test_settings_loads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_ACCOUNT", "12345678-01")
    monkeypatch.setenv("GH_APPKEY", "mock-key")
    monkeypatch.setenv("GH_APPSECRET", "mock-secret")
    settings = Settings.from_env(None)
    assert settings.account_number == "12345678"
    assert settings.account_product_code == "01"
    assert settings.market_open == time(9, 10)
    assert settings.market_close == time(15, 30)
    assert settings.price_offset_krw == 2_000


def test_settings_rejects_missing_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GH_ACCOUNT", "GH_APPKEY", "GH_APPSECRET"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigurationError):
        Settings.from_env(None)
