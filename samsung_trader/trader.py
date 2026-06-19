from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime
from threading import Event

from samsung_trader.account import AccountService
from samsung_trader.api_client import AmbiguousOrderError, KISApiError
from samsung_trader.clock import KSTClock
from samsung_trader.config import Settings
from samsung_trader.market_data import MarketDataService
from samsung_trader.models import BalanceSnapshot, OrderStatus
from samsung_trader.orders import OrderService, aligned_price
from samsung_trader.persistence import DailyState, DailyStateStore, EventRecorder


class Trader:
    def __init__(
        self,
        settings: Settings,
        clock: KSTClock,
        market: MarketDataService,
        account: AccountService,
        orders: OrderService,
        state_store: DailyStateStore,
        recorder: EventRecorder,
        logger: logging.Logger,
        stop_event: Event,
    ) -> None:
        self.settings = settings
        self.clock = clock
        self.market = market
        self.account = account
        self.orders = orders
        self.state_store = state_store
        self.recorder = recorder
        self.logger = logger
        self.stop_event = stop_event
        self._last_status: dict[str, tuple[int, int]] = {}

    def preflight(self, target_date: date, confirmed_open_day: bool = False) -> None:
        open_day = self._open_day_or_override(target_date, confirmed_open_day)
        price = self.market.current_price()
        balance = self.account.balance()
        self.logger.info(
            "preflight OK | target=%s open_day=%s price=%s holdings=%s cash=%s",
            target_date,
            open_day,
            price,
            balance.holding_quantity,
            balance.available_cash,
        )
        self.recorder.record(
            "preflight",
            target_date=target_date.isoformat(),
            open_day=open_day,
            current_price=price,
            balance=asdict(balance),
        )

    def run(
        self,
        target_date: date,
        wait_for_open: bool,
        execute: bool,
        confirmed_open_day: bool = False,
    ) -> None:
        open_at = self.clock.at(target_date, self.settings.market_open)
        close_at = self.clock.at(target_date, self.settings.market_close)
        now = self.clock.now()

        if now > close_at:
            self.logger.info("target trading window has already ended")
            self.recorder.record("window_already_closed", target_date=target_date.isoformat())
            return
        if now < open_at:
            if not wait_for_open:
                self.logger.info("outside trading window; use --wait-for-open to wait")
                self.recorder.record("outside_window", target_date=target_date.isoformat())
                return
            self.logger.info("waiting for KST market window at %s", open_at.isoformat())
            self.recorder.record("waiting_for_open", open_at_kst=open_at.isoformat())
            if not self.clock.sleep_until(open_at, self.stop_event, self.logger):
                return

        if not self._open_day_or_override(target_date, confirmed_open_day):
            self.logger.warning("KIS holiday API reports a closed market day")
            self.recorder.record("market_closed_day", target_date=target_date.isoformat())
            return

        mode = "execute-mock-orders" if execute else "dry-run"
        self.logger.info("trading window started | mode=%s", mode)
        self.recorder.record("trading_window_started", mode=mode)
        state = self.state_store.load(target_date.isoformat())

        try:
            while not self.stop_event.is_set() and self.clock.now() < close_at:
                self._resync_clock()
                if not execute:
                    self._plan_once(state)
                    return

                if state.buy_order_id:
                    completed = self._monitor_current_pair(state, target_date)
                    interval = (
                        self.settings.polling_seconds
                        if completed
                        else self.settings.monitor_seconds
                    )
                elif (
                    self.settings.max_order_pairs_per_day > 0
                    and state.order_pairs >= self.settings.max_order_pairs_per_day
                ):
                    self.logger.info("daily order-pair limit reached; monitoring only")
                    self._monitor_known_orders(state, target_date)
                    interval = self.settings.monitor_seconds
                else:
                    placed = self._place_pair(state, target_date)
                    interval = (
                        self.settings.monitor_seconds
                        if placed
                        else self.settings.polling_seconds
                    )
                self._wait(interval, close_at)
        finally:
            self._final_snapshot(state, target_date)
            self.logger.info("trading window ended; no more orders will be placed")
            self.recorder.record("trading_window_ended")

    def _plan_once(self, state: DailyState) -> None:
        price = self.market.current_price()
        balance = self.account.balance()
        buy_price = aligned_price(
            price,
            self.settings.price_offset_krw,
            self.settings.price_tick_krw,
            "buy",
        )
        sell_price = aligned_price(
            price,
            self.settings.price_offset_krw,
            self.settings.price_tick_krw,
            "sell",
        )
        self.logger.info(
            "dry-run plan | current=%s buy=%s sell=%s qty=%s holdings=%s",
            price,
            buy_price,
            sell_price,
            self.settings.order_quantity,
            balance.holding_quantity,
        )
        self.recorder.record(
            "dry_run_plan",
            symbol=self.settings.symbol,
            current_price=price,
            buy_price=buy_price,
            sell_price=sell_price,
            quantity=self.settings.order_quantity,
            conditional_sell=balance.orderable_quantity < self.settings.order_quantity,
        )

    def _open_day_or_override(
        self, target_date: date, confirmed_open_day: bool
    ) -> bool:
        try:
            return self.market.is_open_day(target_date)
        except KISApiError as exc:
            today = self.clock.now().date()
            if (
                not confirmed_open_day
                or target_date != today
                or target_date.weekday() >= 5
            ):
                raise
            self.logger.warning(
                "KIS holiday API unavailable; using independently confirmed "
                "open-day override for %s",
                target_date,
            )
            self.recorder.record(
                "open_day_operator_override",
                target_date=target_date.isoformat(),
                holiday_api_error=type(exc).__name__,
            )
            return True

    def _place_pair(self, state: DailyState, target_date: date) -> bool:
        existing = self.account.today_orders(target_date)
        outstanding = [order for order in existing if order.remaining_quantity > 0]
        if outstanding:
            self.logger.warning("existing open Samsung order detected; skipping new orders")
            self.recorder.record(
                "order_skipped_existing_open_order",
                order_ids=[order.order_id for order in outstanding],
            )
            return False

        current_price = self.market.current_price()
        before = self.account.balance()
        buy_price = aligned_price(
            current_price,
            self.settings.price_offset_krw,
            self.settings.price_tick_krw,
            "buy",
        )
        sell_price = aligned_price(
            current_price,
            self.settings.price_offset_krw,
            self.settings.price_tick_krw,
            "sell",
        )
        required_cash = buy_price * self.settings.order_quantity
        self.logger.info(
            "market=%s | before holdings=%s orderable=%s cash=%s",
            current_price,
            before.holding_quantity,
            before.orderable_quantity,
            before.available_cash,
        )
        self.recorder.record(
            "holdings_before_order",
            symbol=self.settings.symbol,
            current_price=current_price,
            balance=asdict(before),
        )
        if before.available_cash < required_cash:
            self.logger.warning("insufficient mock cash for the planned buy")
            self.recorder.record(
                "buy_skipped_insufficient_cash",
                required_cash=required_cash,
                available_cash=before.available_cash,
            )
            return False

        self.recorder.record(
            "buy_order_request",
            symbol=self.settings.symbol,
            quantity=self.settings.order_quantity,
            price=buy_price,
        )
        try:
            buy = self.orders.submit_limit(
                "buy", self.settings.order_quantity, buy_price
            )
        except AmbiguousOrderError:
            self.recorder.record("buy_order_ambiguous", symbol=self.settings.symbol)
            self.logger.error("buy response is ambiguous; no automatic retry will occur")
            return False

        state.order_pairs += 1
        state.buy_order_id = buy.order_id
        state.sell_order_id = ""
        state.planned_sell_price = sell_price
        state.holding_before = before.holding_quantity
        state.order_ids.append(buy.order_id)
        self.state_store.save(state)
        self.logger.info("mock buy accepted | order_id=%s price=%s", buy.order_id, buy.price)
        self.recorder.record("buy_order_accepted", **asdict(buy))

        if before.orderable_quantity >= self.settings.order_quantity:
            self._submit_sell(state)

        self._wait_seconds(self.settings.verification_delay_seconds)
        self._monitor_current_pair(state, target_date)
        return True

    def _submit_sell(self, state: DailyState) -> None:
        self.recorder.record(
            "sell_order_request",
            symbol=self.settings.symbol,
            quantity=self.settings.order_quantity,
            price=state.planned_sell_price,
        )
        try:
            sell = self.orders.submit_limit(
                "sell", self.settings.order_quantity, state.planned_sell_price
            )
        except AmbiguousOrderError:
            self.recorder.record("sell_order_ambiguous", symbol=self.settings.symbol)
            self.logger.error("sell response is ambiguous; no automatic retry will occur")
            return
        state.sell_order_id = sell.order_id
        state.order_ids.append(sell.order_id)
        self.state_store.save(state)
        self.logger.info("mock sell accepted | order_id=%s price=%s", sell.order_id, sell.price)
        self.recorder.record("sell_order_accepted", **asdict(sell))

    def _monitor_current_pair(self, state: DailyState, target_date: date) -> bool:
        statuses = self.account.today_orders(target_date)
        by_id = {status.order_id: status for status in statuses}
        needs_balance = self._record_status_changes(statuses)
        buy_status = by_id.get(state.buy_order_id)
        sell_status = by_id.get(state.sell_order_id) if state.sell_order_id else None
        if buy_status and buy_status.is_filled and not state.sell_order_id:
            balance = self.account.balance()
            needs_balance = False
            self._record_balance("holdings_after_buy", balance)
            if balance.orderable_quantity >= self.settings.order_quantity:
                self._submit_sell(state)
                self._wait_seconds(self.settings.verification_delay_seconds)
                statuses = self.account.today_orders(target_date)
                self._record_status_changes(statuses)
                by_id = {status.order_id: status for status in statuses}
                buy_status = by_id.get(state.buy_order_id)
                sell_status = by_id.get(state.sell_order_id)
                balance = self.account.balance()
                self._record_balance("holdings_after_sell_order", balance)

        if needs_balance:
            self._record_balance("holdings_after_order", self.account.balance())

        buy_finished = buy_status is not None and buy_status.remaining_quantity == 0
        sell_finished = sell_status is not None and sell_status.remaining_quantity == 0
        if buy_finished and (sell_finished or not buy_status.is_filled):
            state.buy_order_id = ""
            state.sell_order_id = ""
            state.planned_sell_price = 0
            state.holding_before = 0
            self.state_store.save(state)
            return True
        return False

    def _monitor_known_orders(self, state: DailyState, target_date: date) -> None:
        statuses = self.account.today_orders(target_date)
        relevant = [status for status in statuses if status.order_id in state.order_ids]
        changed = self._record_status_changes(relevant)
        if changed:
            self._record_balance("holdings_after_status_change", self.account.balance())

    def _record_status_changes(self, statuses: list[OrderStatus]) -> bool:
        changed = False
        for status in statuses:
            value = (status.filled_quantity, status.remaining_quantity)
            if self._last_status.get(status.order_id) == value:
                continue
            self._last_status[status.order_id] = value
            changed = True
            self.logger.info(
                "order status | id=%s filled=%s remaining=%s",
                status.order_id,
                status.filled_quantity,
                status.remaining_quantity,
            )
            self.recorder.record("order_status", **asdict(status))
        return changed

    def _record_balance(self, event: str, balance: BalanceSnapshot) -> None:
        self.logger.info(
            "%s | holdings=%s orderable=%s cash=%s",
            event,
            balance.holding_quantity,
            balance.orderable_quantity,
            balance.available_cash,
        )
        self.recorder.record(event, symbol=self.settings.symbol, balance=asdict(balance))

    def _final_snapshot(self, state: DailyState, target_date: date) -> None:
        if not state.order_ids:
            return
        try:
            self._monitor_known_orders(state, target_date)
        except KISApiError as exc:
            self.logger.warning("final status check failed: %s", exc)

    def _resync_clock(self) -> None:
        try:
            self.clock.resync_if_due(
                self.market.client.session, self.settings.base_url
            )
        except Exception as exc:  # Trading still uses the last verified offset.
            self.logger.warning("clock resync failed; keeping last offset: %s", exc)
            self.recorder.record("clock_resync_failed", error=type(exc).__name__)

    def _wait(self, seconds: int, close_at: datetime) -> None:
        remaining = max(0.0, (close_at - self.clock.now()).total_seconds())
        self.stop_event.wait(min(float(seconds), remaining))

    def _wait_seconds(self, seconds: int) -> None:
        self.stop_event.wait(float(seconds))
