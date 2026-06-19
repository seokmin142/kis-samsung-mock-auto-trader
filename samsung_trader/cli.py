from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path
from threading import Event

import requests

from samsung_trader.account import AccountService
from samsung_trader.api_client import KISApiError, KISClient
from samsung_trader.auth import AuthenticationError, TokenManager
from samsung_trader.clock import KSTClock
from samsung_trader.config import ConfigurationError, Settings
from samsung_trader.logging_setup import setup_logging
from samsung_trader.market_data import MarketDataService
from samsung_trader.orders import OrderService
from samsung_trader.persistence import DailyStateStore, EventRecorder
from samsung_trader.trader import Trader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Samsung Electronics auto-trader for KIS mock trading only."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="submit orders to the KIS mock account; otherwise only print a plan",
    )
    parser.add_argument(
        "--run-date",
        type=date.fromisoformat,
        help="KST trading date in YYYY-MM-DD format (default: current KST date)",
    )
    parser.add_argument(
        "--wait-for-open",
        action="store_true",
        help="wait until 09:10 KST instead of exiting before the window",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="test clock, authentication, holiday, price, and balance without ordering",
    )
    parser.add_argument(
        "--confirmed-open-day",
        action="store_true",
        help=(
            "allow today's weekday only when the KIS holiday API is unavailable "
            "and an operator independently confirmed the exchange calendar"
        ),
    )
    parser.add_argument(
        "--cancel-order",
        metavar="ORDER_ID",
        help="cancel all remaining quantity for one KIS mock order, then exit",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="local environment file; ignored by Git",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    clock = KSTClock()
    session = requests.Session()

    try:
        settings = Settings.from_env(args.env_file)
        skew = clock.sync(session, settings.base_url)
    except (ConfigurationError, requests.RequestException, RuntimeError) as exc:
        print(f"Pre-start check failed: {exc}")
        return 2

    logger = setup_logging(settings.logs_dir, clock)
    recorder = EventRecorder(settings.records_dir, clock)
    logger.info("KIS server clock synchronized | local correction=%+.3fs", skew)
    recorder.record("clock_synchronized", correction_seconds=round(skew, 3))

    token_manager = TokenManager(settings, session, clock, logger, recorder)
    client = KISClient(
        settings, session, token_manager, clock, logger, recorder
    )
    market = MarketDataService(client, settings.symbol)
    account = AccountService(
        client,
        settings.account_number,
        settings.account_product_code,
        settings.symbol,
    )
    orders = OrderService(
        client,
        settings.account_number,
        settings.account_product_code,
        settings.symbol,
    )
    trader = Trader(
        settings=settings,
        clock=clock,
        market=market,
        account=account,
        orders=orders,
        state_store=DailyStateStore(settings.runtime_dir),
        recorder=recorder,
        logger=logger,
        stop_event=Event(),
    )
    target_date = args.run_date or clock.now().date()

    try:
        if args.cancel_order:
            recorder.record("cancel_order_request", order_id=args.cancel_order)
            cancel_order_id = orders.cancel_all(args.cancel_order)
            logger.info(
                "mock order cancellation accepted | original=%s cancel_order=%s",
                args.cancel_order,
                cancel_order_id,
            )
            recorder.record(
                "cancel_order_accepted",
                original_order_id=args.cancel_order,
                cancel_order_id=cancel_order_id,
            )
        elif args.preflight:
            trader.preflight(target_date, args.confirmed_open_day)
        else:
            trader.run(
                target_date,
                args.wait_for_open,
                args.execute,
                args.confirmed_open_day,
            )
        return 0
    except KeyboardInterrupt:
        logger.info("stopped by user")
        recorder.record("stopped_by_user")
        return 130
    except (AuthenticationError, KISApiError) as exc:
        logger.error("safe stop after API error: %s", exc)
        recorder.record("safe_stop", error=type(exc).__name__, message=str(exc))
        return 1
    finally:
        session.close()
