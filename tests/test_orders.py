import pytest

from samsung_trader.orders import OrderService, aligned_price


def test_aligned_price_uses_target_tick() -> None:
    assert aligned_price(70_050, 2_000, 100, "buy") == 68_000
    assert aligned_price(70_050, 2_000, 100, "sell") == 72_100


def test_aligned_price_rejects_invalid_side() -> None:
    with pytest.raises(ValueError):
        aligned_price(70_000, 2_000, 100, "hold")


class FakeOrderClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def post(self, path: str, tr_id: str, body: dict[str, str]) -> dict:
        self.calls.append((path, tr_id, body))
        return {"rt_cd": "0", "output": {"ODNO": "12345", "ORD_TMD": "091501"}}


def test_mock_buy_uses_official_demo_tr_id() -> None:
    client = FakeOrderClient()
    service = OrderService(client, "12345678", "01", "005930")  # type: ignore[arg-type]
    receipt = service.submit_limit("buy", 1, 68_000)
    assert client.calls[0][1] == "VTTC0012U"
    assert client.calls[0][2]["ORD_DVSN"] == "00"
    assert receipt.order_id == "12345"


def test_mock_cancel_uses_official_demo_tr_id_and_all_quantity() -> None:
    client = FakeOrderClient()
    service = OrderService(client, "12345678", "01", "005930")  # type: ignore[arg-type]
    cancel_order_id = service.cancel_all("12345")
    assert client.calls[0][1] == "VTTC0013U"
    assert client.calls[0][2]["ORGN_ODNO"] == "12345"
    assert client.calls[0][2]["RVSE_CNCL_DVSN_CD"] == "02"
    assert client.calls[0][2]["QTY_ALL_ORD_YN"] == "Y"
    assert cancel_order_id == "12345"
