import os
import json
import requests
from datetime import datetime, timezone

import asyncio
from fastlogging import LogInit

import redis.asyncio as redis
from shared.models.strategies.crypto_15_min_arb_model import Crypto15MinArbTrader
from shared.models.metrics.crypto_15_min_arb_metric import Crypto15MinArbMetric
from shared.models.orderbook import Orderbook
from shared.constants import kalshi_crypto_fee, poly_crypto_fee
from shared.utils import get_kalshi_client, get_polymarket_client, get_kalshi_headers
from py_clob_client.clob_types import OrderArgs, OrderType, PartialCreateOrderOptions
from py_clob_client.order_builder.constants import BUY

logger = LogInit(domain=__name__, console=True, level=10)

class Crypto15MinArbStrategy:


    def __init__(self, options: Crypto15MinArbTrader):
        self.options = options
        self.r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)
        self.polymarket_client = get_polymarket_client()
        self.kalshi_client = get_kalshi_client()
        self.last_timestamps = {'kalshi':datetime.now(), 'polymarket':datetime.now()}
        self.last_timestamp_stale = False

    # TODO: put these in utils somehow
    async def post_kalshi_order(self, kalshi_ticker, side, price: str, volume: int):
        jsonrequest = {"ticker": kalshi_ticker,
                                      "side": side,
                                      "action": "buy",
                                      "count": int(volume),
                                      "time_in_force": "immediate_or_cancel"
                    }
        if side == "yes":
            jsonrequest["yes_price_dollars"] = f"{price:.2f}"
        else:
            jsonrequest["no_price_dollars"] = f"{price:.2f}"

        return await asyncio.to_thread(
            lambda: requests.post(
                'https://api.elections.kalshi.com/trade-api/v2/portfolio/orders',
                json=jsonrequest,
                headers={**get_kalshi_headers("POST", "/trade-api/v2/portfolio/orders"), "Content-Type": "application/json"},
                timeout=5
            ).json()
        )

    async def post_polymarket_order(self, polymarket_ticker, price: str, volume: int):

        logger.info(price)
        logger.info(volume)

        test_order = self.polymarket_client.create_order(
            OrderArgs(
                token_id=polymarket_ticker,
                price=round(float(price), 2),
                size=volume,
                side=BUY,
            ),
            options=PartialCreateOrderOptions(tick_size="0.01")
        )


        try:
            return await asyncio.to_thread(self.polymarket_client.post_order, test_order, OrderType.FAK)
        except Exception as e:
            return e

    async def try_arb(self, kalshi_asks, poly_asks, kalshi_ticker, polymarket_ticker, kalshi_side):

        eff_arb = kalshi_crypto_fee(kalshi_asks[0][0]) + poly_crypto_fee(poly_asks[0][0])

        if eff_arb > self.options.min_arb_percentage:
            logger.info(f"No arb: {eff_arb}")
            return None
        
        if eff_arb < self.options.danger_arb_percentage:
            logger.warning(f"Dangerous arb (markets might be diverging): {eff_arb}")
            return None 

        if kalshi_asks[0][0] * self.options.max_vol_per_trade < 1.0 or poly_asks[0][0] * self.options.max_vol_per_trade < 1.0:
            logger.info(f"Not enough tradeable volume for percentages: {kalshi_asks[0][0]}, {poly_asks[0][0]}")
            return None

        # start at the second entry because the first entry usually gets eaten really fast
        i = 1; j = 1
        k_v = kalshi_asks[0][1] + kalshi_asks[1][1]; p_v = poly_asks[0][1] + poly_asks[1][1]

        # break when we achieve the required liquidity or out of orders
        while (k_v < self.options.min_required_liquidity or p_v < self.options.min_required_liquidity) and (i+1 < len(kalshi_asks) or j+1 < len(poly_asks)):

            # kalshi_asks: [(price1: volume1), ...] (sorted by price:w

            # iterate to the next i/j option if:
            # 1. not greater than the length of the orderbook
            # 2. we're below the needed liquidity
            # 3. doesn't put us above our max arb %
            i_option = []; j_option = [] 
            if i+1 < len(kalshi_asks) and \
                kalshi_crypto_fee(kalshi_asks[i+1][0]) + poly_crypto_fee(poly_asks[j][0]) < self.options.max_arb_percentage and \
                k_v < self.options.min_required_liquidity:

                i_option = kalshi_asks[i+1]

            if j+1 < len(poly_asks) and \
                kalshi_crypto_fee(kalshi_asks[i][0]) + poly_crypto_fee(poly_asks[j+1][0]) < self.options.max_arb_percentage and \
                p_v < self.options.min_required_liquidity:

                j_option = poly_asks[j+1]

            # if neither option available, means we haven't satisfied our requirements 
            # and we can't continue to iterate, so return
            # otherwise, choose available option or max option
            if not i_option and not j_option:
                logger.info("Couldn't find good arb")
                return None
            elif (j_option and i_option and j_option[1] > i_option[1]) or not i_option:
                p_v += j_option[1]
                j += 1
            else:
                k_v += i_option[1]
                i += 1

        kalshi_price = kalshi_asks[i][0]
        polymarket_price = poly_asks[j][0]

        kalshi_cost = kalshi_price * int(self.options.max_vol_per_trade)
        poly_cost = polymarket_price * int(self.options.max_vol_per_trade)

        kalshi_bal_raw = await self.r.get("balance:kalshi")
        poly_bal_raw = await self.r.get("balance:polymarket")
        kalshi_bal = float(kalshi_bal_raw) if kalshi_bal_raw is not None else 0.0
        poly_bal = float(poly_bal_raw) if poly_bal_raw is not None else 0.0

        if kalshi_bal < kalshi_cost:
            logger.warning(f"Insufficient kalshi balance ({kalshi_bal:.2f}) for trade cost ({kalshi_cost:.2f}), skipping")
            return None
        if poly_bal < poly_cost:
            logger.warning(f"Insufficient polymarket balance ({poly_bal:.2f}) for trade cost ({poly_cost:.2f}), skipping")
            return None

        logger.info(f"""GONNA TRY TO BUY!!!!\n
                    ---kalshi price 1 {kalshi_price}, post fees {kalshi_crypto_fee(kalshi_price)}\n
                    ---poly price 1 {polymarket_price}, post fees {poly_crypto_fee(polymarket_price)}\n
                    ---arb min {kalshi_asks[0][0] + poly_asks[0][0]}, arb max {kalshi_asks[i][0] + poly_asks[j][0]}\n
        """)

        async def timed(coro):
            t = datetime.now()
            result = await coro
            return result, (datetime.now() - t).total_seconds()

        kalshi_task = asyncio.create_task(timed(self.post_kalshi_order(kalshi_ticker, kalshi_side, kalshi_asks[i][0], int(self.options.max_vol_per_trade))))
        poly_task = asyncio.create_task(timed(self.post_polymarket_order(polymarket_ticker, poly_asks[j][0], int(self.options.max_vol_per_trade))))

        kalshi_resp, kalshi_rtt = await kalshi_task
        poly_resp, poly_rtt = await poly_task

        try:
            metric = Crypto15MinArbMetric.from_trade(
                kalshi_resp, poly_resp, kalshi_side,
                market=self.options.marketname,
                kalshi_price=kalshi_asks[i][0],
                poly_price=poly_asks[j][0],
                volume=int(self.options.max_vol_per_trade)
            )
            metric.kalshi_request_response_time = kalshi_rtt
            metric.polymarket_request_response_time = poly_rtt
            return metric
        except Exception as e:
            logger.error(f"Failed to build metric: {e}")



    async def run_it_up(self):

        start_time = datetime.now(timezone.utc)

        books = {}
        for platform in ['kalshi', 'polymarket']:
            raw = await self.r.get(f"{platform}:{self.options.marketname}")
            if raw is None:
                logger.warning(f"No orderbook in redis for {platform}:{self.options.marketname}, skipping")
                return
            book = Orderbook.from_redis(json.loads(raw))

            # Check snapshot freshness
            if not book.last_update_time or self.last_timestamps[platform] == book.last_update_time or (start_time - book.last_update_time).total_seconds() > 0.5:
                if not self.last_timestamp_stale:
                    logger.warning(f"{platform} snapshot timestamp stale; skipping")
                    self.last_timestamp_stale = True
                return
            # Check snapshot data exists
            if not book.yes_asks or not book.no_asks:
                logger.warning(f"empty orderbook side for {platform} {self.options.marketname}, skipping")
                return
            
            self.last_timestamps[platform] = book.last_update_time
            books[platform] = book

        self.last_timestamp_stale = False

        kalshi = books['kalshi']
        poly = books['polymarket']

        kalshi_yes_sorted = sorted([(price, volume) for price, volume in kalshi.yes_asks.items()])
        kalshi_no_sorted = sorted([(price, volume) for price, volume in kalshi.no_asks.items()])
        poly_yes_sorted = sorted([(price, volume) for price, volume in poly.yes_asks.items()])
        poly_no_sorted = sorted([(price, volume) for price, volume in poly.no_asks.items()])

        try:
            if arb1metric := await self.try_arb(kalshi_yes_sorted, poly_no_sorted, kalshi.kalshi_ticker, poly.polymarket_no_ticker, 'yes'):
                logger.info("Found arb")
                t = (datetime.now(timezone.utc) - start_time).total_seconds()
                arb1metric.total_execution_time = t
                arb1metric.execution_time = t
                await self.r.publish("mock-trader-v1-results", arb1metric.model_dump_json())
        except Exception as e:
            logger.error(e)

        try:
            if arb2metric := await self.try_arb(kalshi_no_sorted, poly_yes_sorted, kalshi.kalshi_ticker, poly.polymarket_yes_ticker, 'no'):
                logger.info("Found arb")
                t = (datetime.now(timezone.utc) - start_time).total_seconds()
                arb2metric.total_execution_time = t
                arb2metric.execution_time = t
                await self.r.publish("mock-trader-v1-results", arb2metric.model_dump_json())
        except Exception as e:
            logger.error(e)

    async def run(self):

        logger.info(f"Waiting to startup crypto 15 min arb for {self.options.marketname}...")

        await asyncio.sleep(60)

        logger.info(f"Starting crypto 15 min arb for {self.options.marketname}...")

        try:
            while True:
                await self.run_it_up()
                await asyncio.sleep(self.options.seconds_timeout)
        except asyncio.CancelledError:
            logger.info(f"Stopping crypto 15 min arb for {self.options.marketname}")
            raise

    