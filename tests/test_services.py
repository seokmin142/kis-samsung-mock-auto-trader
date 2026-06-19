from datetime import date

from samsung_trader.account import AccountService
from samsung_trader.market_data import MarketDataService


class FakeClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def get(self, path: str, tr_id: str, params: dict[str, str]) -> dict:
        self.calls.append((path, tr_id, params))
        return self.responses.pop(0)


def test_market_price_and_holiday_parsing() -> None:
    client = FakeClient(
        [
            {"output": {"stck_prpr": "70000"}},
            {"output": [{"bass_dt": "20260619", "opnd_yn": "Y"}]},
        ]
    )
    service = MarketDataService(client, "005930")  # type: ignore[arg-type]
    assert service.current_price() == 70_000
    assert service.is_open_day(date(2026, 6, 19)) is True
    assert client.calls[1][1] == "CTCA0903R"


def test_balance_and_order_status_parsing() -> None:
    client = FakeClient(
        [
            {
                "output1": [
                    {"pdno": "005930", "hldg_qty": "2", "ord_psbl_qty": "1"}
                ],
                "output2": [{"dnca_tot_amt": "1000000", "tot_evlu_amt": "1200000"}],
            },
            {
                "output1": [
                    {
                        "pdno": "005930",
                        "odno": "99",
                        "sll_buy_dvsn_cd_name": "매수",
                        "ord_qty": "1",
                        "tot_ccld_qty": "1",
                        "rmn_qty": "0",
                        "ord_unpr": "68000",
                        "ord_tmd": "091500",
                    }
                ]
            },
        ]
    )
    service = AccountService(client, "12345678", "01", "005930")  # type: ignore[arg-type]
    balance = service.balance()
    statuses = service.today_orders(date(2026, 6, 19))
    assert balance.holding_quantity == 2
    assert balance.available_cash == 1_000_000
    assert statuses[0].is_filled is True
    assert client.calls[0][1] == "VTTC8434R"
    assert client.calls[1][1] == "VTTC0081R"
