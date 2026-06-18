from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BalanceSnapshot:
    symbol: str
    holding_quantity: int
    orderable_quantity: int
    available_cash: int
    total_evaluation_amount: int


@dataclass(frozen=True)
class OrderReceipt:
    side: str
    symbol: str
    quantity: int
    price: int
    order_id: str
    order_time: str


@dataclass(frozen=True)
class OrderStatus:
    order_id: str
    side_name: str
    ordered_quantity: int
    filled_quantity: int
    remaining_quantity: int
    order_price: int
    order_time: str

    @property
    def is_filled(self) -> bool:
        return (
            self.ordered_quantity > 0
            and self.filled_quantity >= self.ordered_quantity
            and self.remaining_quantity == 0
        )
