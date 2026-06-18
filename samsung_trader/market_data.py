from __future__ import annotations

from datetime import date

from samsung_trader.api_client import KISApiError, KISClient


class MarketDataService:
    PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
    HOLIDAY_PATH = "/uapi/domestic-stock/v1/quotations/chk-holiday"

    def __init__(self, client: KISClient, symbol: str) -> None:
        self.client = client
        self.symbol = symbol

    def current_price(self) -> int:
        payload = self.client.get(
            self.PRICE_PATH,
            "FHKST01010100",
            {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": self.symbol,
            },
        )
        output = payload.get("output") or {}
        try:
            price = int(str(output["stck_prpr"]).replace(",", ""))
        except (KeyError, TypeError, ValueError) as exc:
            raise KISApiError("current-price response lacks stck_prpr") from exc
        if price <= 0:
            raise KISApiError("current price must be positive")
        return price

    def is_open_day(self, day: date) -> bool:
        payload = self.client.get(
            self.HOLIDAY_PATH,
            "VTCA0903R",
            {"BASS_DT": day.strftime("%Y%m%d"), "CTX_AREA_FK": "", "CTX_AREA_NK": ""},
        )
        rows = payload.get("output") or []
        if isinstance(rows, dict):
            rows = [rows]
        target = day.strftime("%Y%m%d")
        for row in rows:
            if str(row.get("bass_dt", "")) == target:
                return str(row.get("opnd_yn", "N")).upper() == "Y"
        raise KISApiError("holiday response did not include the target date")
