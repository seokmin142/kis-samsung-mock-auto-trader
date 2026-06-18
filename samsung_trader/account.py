from __future__ import annotations

from datetime import date

from samsung_trader.api_client import KISApiError, KISClient
from samsung_trader.models import BalanceSnapshot, OrderStatus


def _number(value: object) -> int:
    try:
        return int(float(str(value or "0").replace(",", "")))
    except ValueError:
        return 0


class AccountService:
    BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
    ORDERS_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"

    def __init__(
        self,
        client: KISClient,
        account_number: str,
        product_code: str,
        symbol: str,
    ) -> None:
        self.client = client
        self.account_number = account_number
        self.product_code = product_code
        self.symbol = symbol

    def balance(self) -> BalanceSnapshot:
        payload = self.client.get(
            self.BALANCE_PATH,
            "VTTC8434R",
            {
                "CANO": self.account_number,
                "ACNT_PRDT_CD": self.product_code,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )
        holdings = payload.get("output1") or []
        summary = payload.get("output2") or []
        if isinstance(summary, list):
            summary = summary[0] if summary else {}
        row = next(
            (item for item in holdings if str(item.get("pdno", "")) == self.symbol),
            {},
        )
        return BalanceSnapshot(
            symbol=self.symbol,
            holding_quantity=_number(row.get("hldg_qty")),
            orderable_quantity=_number(row.get("ord_psbl_qty")),
            available_cash=_number(summary.get("dnca_tot_amt")),
            total_evaluation_amount=_number(summary.get("tot_evlu_amt")),
        )

    def today_orders(self, day: date, order_id: str = "") -> list[OrderStatus]:
        day_text = day.strftime("%Y%m%d")
        payload = self.client.get(
            self.ORDERS_PATH,
            "VTTC0081R",
            {
                "CANO": self.account_number,
                "ACNT_PRDT_CD": self.product_code,
                "INQR_STRT_DT": day_text,
                "INQR_END_DT": day_text,
                "SLL_BUY_DVSN_CD": "00",
                "PDNO": self.symbol,
                "CCLD_DVSN": "00",
                "INQR_DVSN": "00",
                "INQR_DVSN_3": "00",
                "ORD_GNO_BRNO": "",
                "ODNO": order_id,
                "INQR_DVSN_1": "",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
                "EXCG_ID_DVSN_CD": "KRX",
            },
        )
        rows = payload.get("output1") or []
        if not isinstance(rows, list):
            raise KISApiError("daily-order response output1 is not a list")
        result: list[OrderStatus] = []
        for row in rows:
            if str(row.get("pdno", "")) != self.symbol:
                continue
            result.append(
                OrderStatus(
                    order_id=str(row.get("odno", "")),
                    side_name=str(row.get("sll_buy_dvsn_cd_name", "")),
                    ordered_quantity=_number(row.get("ord_qty")),
                    filled_quantity=_number(row.get("tot_ccld_qty")),
                    remaining_quantity=_number(row.get("rmn_qty")),
                    order_price=_number(row.get("ord_unpr")),
                    order_time=str(row.get("ord_tmd", "")),
                )
            )
        return result
