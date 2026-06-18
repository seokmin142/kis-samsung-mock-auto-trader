from pathlib import Path

import pytest
import requests

from samsung_trader.api_client import AmbiguousOrderError, KISApiError, KISClient
from samsung_trader.clock import KSTClock
from samsung_trader.config import Settings
from samsung_trader.persistence import EventRecorder


class TokenStub:
    def get_token(self) -> str:
        return "test-token"

    def invalidate(self) -> None:
        pass


class TimeoutSession:
    def request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise requests.Timeout("timeout")


def settings(tmp_path: Path) -> Settings:
    return Settings(
        account_number="12345678",
        account_product_code="01",
        app_key="mock-key",
        app_secret="mock-secret",
        runtime_dir=tmp_path / "runtime",
        records_dir=tmp_path / "records",
        logs_dir=tmp_path / "logs",
        request_min_interval_seconds=0.001,
    )


def test_client_rejects_live_tr_id_before_network(tmp_path: Path) -> None:
    clock = KSTClock()
    client = KISClient(
        settings(tmp_path),
        TimeoutSession(),  # type: ignore[arg-type]
        TokenStub(),  # type: ignore[arg-type]
        clock,
        __import__("logging").getLogger("test"),
        EventRecorder(tmp_path / "records", clock),
    )
    with pytest.raises(KISApiError, match="unsafe non-mock"):
        client.get("/path", "TTTC0012U", {})


def test_order_timeout_is_never_retried(tmp_path: Path) -> None:
    clock = KSTClock()
    session = TimeoutSession()
    client = KISClient(
        settings(tmp_path),
        session,  # type: ignore[arg-type]
        TokenStub(),  # type: ignore[arg-type]
        clock,
        __import__("logging").getLogger("test"),
        EventRecorder(tmp_path / "records", clock),
    )
    with pytest.raises(AmbiguousOrderError):
        client.post("/order", "VTTC0012U", {"ORD_QTY": "1"})
