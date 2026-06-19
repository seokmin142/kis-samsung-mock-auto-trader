from __future__ import annotations

from samsung_trader.api_client import KISApiError, KISClient
from samsung_trader.models import OrderReceipt


def aligned_price(reference_price: int, offset: int, tick: int, side: str) -> int:
    raw = reference_price - offset if side == "buy" else reference_price + offset
    if raw <= 0:
        raise ValueError("calculated order price must be positive")
    if side == "buy":
        return (raw // tick) * tick
    if side == "sell":
        return ((raw + tick - 1) // tick) * tick
    raise ValueError("side must be buy or sell")


class OrderService:
    ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
    CANCEL_PATH = "/uapi/domestic-stock/v1/trading/order-rvsecncl"

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

    def submit_limit(self, side: str, quantity: int, price: int) -> OrderReceipt:
        if side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        tr_id = "VTTC0012U" if side == "buy" else "VTTC0011U"
        payload = self.client.post(
            self.ORDER_PATH,
            tr_id,
            {
                "CANO": self.account_number,
                "ACNT_PRDT_CD": self.product_code,
                "PDNO": self.symbol,
                "ORD_DVSN": "00",
                "ORD_QTY": str(quantity),
                "ORD_UNPR": str(price),
                "EXCG_ID_DVSN_CD": "KRX",
                "SLL_TYPE": "01" if side == "sell" else "",
                "CNDT_PRIC": "",
            },
        )
        output = payload.get("output") or {}
        order_id = str(output.get("ODNO") or output.get("odno") or "")
        order_time = str(output.get("ORD_TMD") or output.get("ord_tmd") or "")
        if not order_id:
            raise KISApiError("order response did not contain an order number")
        return OrderReceipt(
            side=side,
            symbol=self.symbol,
            quantity=quantity,
            price=price,
            order_id=order_id,
            order_time=order_time,
        )

    def cancel_all(self, original_order_id: str) -> str:
        if not original_order_id.isdigit():
            raise ValueError("original_order_id must contain digits only")
        payload = self.client.post(
            self.CANCEL_PATH,
            "VTTC0013U",
            {
                "CANO": self.account_number,
                "ACNT_PRDT_CD": self.product_code,
                "KRX_FWDG_ORD_ORGNO": "",
                "ORGN_ODNO": original_order_id,
                "ORD_DVSN": "00",
                "RVSE_CNCL_DVSN_CD": "02",
                "ORD_QTY": "0",
                "ORD_UNPR": "0",
                "QTY_ALL_ORD_YN": "Y",
                "EXCG_ID_DVSN_CD": "KRX",
                "CNDT_PRIC": "",
            },
        )
        output = payload.get("output") or {}
        cancel_order_id = str(output.get("ODNO") or output.get("odno") or "")
        if not cancel_order_id:
            raise KISApiError("cancel response did not contain an order number")
        return cancel_order_id
