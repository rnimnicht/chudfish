import os
import asyncio
import time
import json
import requests
from datetime import datetime, timezone

import redis
from fastlogging import LogInit
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, PartialCreateOrderOptions
from py_clob_client.order_builder.constants import BUY

from shared.models.matched_market import Matched_Market
from shared.models.orderbook import Orderbook
from shared.models.metrics.crypto15minarb import Crypto15MinArbMetric
from shared.utils import get_kalshi_client, get_polymarket_client, get_kalshi_headers


# want the logic to be single threaded for safety
time.sleep(60)

r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)
polymarket_client = get_polymarket_client()
kalshi_client = get_kalshi_client()

market_name = "sol15min"
max_arb_percentage = 1.01
min_arb_percentage = 0.99
danger_arb_percentage = 0.60
max_volume_per_trade = 10.0
min_required_liquidity = 250.0
kalshi_fee = lambda x : (x * 0.07 * (1.0-x)) + x
poly_fee = lambda x: (x * 0.25 * ((x * (1.0-x) )**2)) + x
#poly_fee = lambda x: x
total_trades = 0

logger = LogInit(domain=__name__, console=True, level=10)


def emit_metric():
    pass

async def post_kalshi_order(kalshi_ticker, side, price: str, volume: int):
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

    logger.info(jsonrequest)

    return await asyncio.to_thread(
        lambda: requests.post(
            'https://api.elections.kalshi.com/trade-api/v2/portfolio/orders',
            json=jsonrequest,
            headers={**get_kalshi_headers("POST", "/trade-api/v2/portfolio/orders"), "Content-Type": "application/json"},
            timeout=5
        ).json()
    )

async def post_polymarket_order(polymarket_ticker, price: str, volume: int):

    logger.info(price)
    logger.info(volume)

    test_order = polymarket_client.create_order(
        OrderArgs(
            token_id=polymarket_ticker,
            price=round(float(price), 2),
            size=volume,
            side=BUY,
        ),
        options=PartialCreateOrderOptions(tick_size="0.01")
    )


    try:
        return await asyncio.to_thread(polymarket_client.post_order, test_order, OrderType.FAK)
    except Exception as e:
        return e

async def try_arb(kalshi_asks, poly_asks, kalshi_ticker, polymarket_ticker, kalshi_side):

    # logger.info(f"kalshi asks: {kalshi_asks}")
    # logger.info(f"poly asks: {poly_asks}")

    exec_start = time.time()
    eff_arb = kalshi_fee(kalshi_asks[0][0]) + poly_fee(poly_asks[0][0])
    if eff_arb > min_arb_percentage:
        logger.info(f"No arb: {eff_arb}")
        return False
    if eff_arb < danger_arb_percentage:
        logger.warning(f"SCARY ARB: {eff_arb}")
        return False

    if kalshi_asks[0][0] * max_volume_per_trade < 1.0 or poly_asks[0][0] * max_volume_per_trade < 1.0:
        logger.info(f"Not enough tradeable volume for percentages: {kalshi_asks[0][0]}, {poly_asks[0][0]}")
        return

    # start at the second entry because the first entry usually gets eaten really fast
    i = 1; j = 1
    k_v = kalshi_asks[0][1] + kalshi_asks[1][1]; p_v = poly_asks[0][1] + poly_asks[1][1]

    # break when we achieve the required liquidity or out of orders
    while (k_v < min_required_liquidity or p_v < min_required_liquidity) and (i+1 < len(kalshi_asks) or j+1 < len(poly_asks)):

        logger.info(f"chud algoritihm {i} {j}, {kalshi_asks[i]}, {poly_asks[j]}")

        # kalshi_asks: [(price1: volume1), ...] (sorted by price:w

        # get the next available volumes if they're not above arb % and they're not at the end of the orderbook
        i_option = None; j_option = None
        if i+1 < len(kalshi_asks) and kalshi_fee(kalshi_asks[i+1][0]) + poly_fee(poly_asks[j][0]) < max_arb_percentage and k_v < min_required_liquidity:
            logger.info("init more kalshi stuff")
            i_option = kalshi_asks[i+1]
        if j+1 < len(poly_asks) and kalshi_fee(kalshi_asks[i][0]) + poly_fee(poly_asks[j+1][0]) < max_arb_percentage and p_v < min_required_liquidity:
            logger.info("init more polymarket stuff")
            j_option = poly_asks[j+1]

        # break if neither available
        if not i_option and not j_option:
            logger.info("neither option good")
            break

        # if either option not availible, choose the other option, else choose max volume
        # rewrite this dumbass
        elif not i_option and j_option != None:
            p_v += j_option[1]
            j += 1
        elif not j_option and i_option != None:
            k_v += i_option[1]
            i += 1
        elif i_option != None and j_option != None and i_option[1] > j_option[1]:
            k_v += i_option[1]
            i += 1
        else:
            if j_option != None:
                p_v += j_option[1]
                j += 1

    kalshi_price = kalshi_asks[i][0]
    polymarket_price = poly_asks[j][0]

    logger.info(f"{i}, {j}")


    logger.info(kalshi_asks[:i+1])
    logger.info(poly_asks[:j+1])

    # do we want max here?
    # uhhh we dont need to min here
    volume = max_volume_per_trade 
    logger.info(f"Tradeable volume: {volume}")

    # Can't trade < $1
    # if volume * min(kalshi_price, polymarket_price) < 1.0:
    #     logger.info("Not enough volume to trade")
    #     return False

    # Calculate effective prices and arbitrage opportunity
    logger.info(f"""GONNA TRY TO BUY!!!!\n
                ---kalshi price 1 {kalshi_price}, post fees {kalshi_fee(kalshi_price)}\n
                ---poly price 1 {polymarket_price}, post fees {poly_fee(polymarket_price)}\n
                ---arb min {kalshi_asks[0][0] + poly_asks[0][0]}, arb max {kalshi_asks[i][0] + poly_asks[j][0]}\n
    """)

    execution_time = time.time() - exec_start

    async def timed(coro):
        t = time.time()
        result = await coro
        return result, time.time() - t

    kalshi_task = asyncio.create_task(timed(post_kalshi_order(kalshi_ticker, kalshi_side, kalshi_asks[i][0], int(volume))))
    poly_task = asyncio.create_task(timed(post_polymarket_order(polymarket_ticker, poly_asks[j][0], int(volume))))

    kalshi_resp, kalshi_rtt = await kalshi_task
    poly_resp, poly_rtt = await poly_task

    logger.info(kalshi_resp)
    logger.info(poly_resp)

    metric = Crypto15MinArbMetric(
        market=market_name,
        timestamp=str(datetime.now(timezone.utc)),
        execution_time=execution_time,
        expected_return=(1.0 - eff_arb) * volume,
        polymarket_request_response_time=poly_rtt,
        kalshi_request_response_time=kalshi_rtt,
        side='kalshi_yes_poly_no' if kalshi_side == 'yes' else 'kalshi_no_poly_yes',
        eff_combined_price=eff_arb,
        volume=int(volume),
        eff_kalshi_yes_price=kalshi_fee(kalshi_price) if kalshi_side == 'yes' else None,
        eff_poly_no_price=poly_fee(polymarket_price) if kalshi_side == 'yes' else None,
        kalshi_yes_price=kalshi_price if kalshi_side == 'yes' else None,
        poly_no_price=polymarket_price if kalshi_side == 'yes' else None,
        eff_kalshi_no_price=kalshi_fee(kalshi_price) if kalshi_side == 'no' else None,
        eff_poly_yes_price=poly_fee(polymarket_price) if kalshi_side == 'no' else None,
        kalshi_no_price=kalshi_price if kalshi_side == 'no' else None,
        poly_yes_price=polymarket_price if kalshi_side == 'no' else None,
        kalshi_filled=float(kalshi_resp['order']['fill_count_fp']),
        poly_filled=volume if not isinstance(poly_resp, Exception) else 0.0
    )

    global total_trades
    total_trades += 1

    r.publish("mock-trader-v1-results", metric.model_dump_json())


async def run_it_up():

    logger.info(f"--. ݁₊ ⊹ . ݁˖ . ݁--running it up for {market_name}--. ݁₊ ⊹ . ݁˖ . ݁--")

    now = datetime.now(timezone.utc)

    books = {}
    for platform in ['kalshi', 'polymarket']:
        raw = r.get(f"{platform}:{market_name}")
        if raw is None:
            logger.warning(f"no orderbook in redis for {platform}:{market_name}, skipping")
            return
        books[platform] = Orderbook.from_redis(json.loads(raw))

    kalshi = books['kalshi']
    poly = books['polymarket']

    # skip if any side is empty
    if not kalshi.yes_asks or not kalshi.no_asks:
        logger.warning(f"empty orderbook side for kalshi {market_name}, skipping")
        return
    if not poly.yes_asks or not poly.no_asks:
        logger.warning(f"empty orderbook side for polymarket {market_name}, skipping")
        return
    
    # time check
    if not kalshi.last_update_time:
        logger.warning("no kalshi snapshot timestamp; skipping")
        return
    else:
        kalshi_timediff = (now - kalshi.last_update_time).total_seconds()
        logger.info(f"Kalshi snapshot time diff: {kalshi_timediff}")
        if kalshi_timediff > 1.0:
            logger.warning("Kalshi timediff too big, skipping")
            return None

    if not poly.last_update_time:
        logger.warning("no polymarket snapshot timestamp; skipping")
        return
    else:
        polymarket_timediff = (now - poly.last_update_time).total_seconds()
        logger.info(f"Polymarket snapshot time diff: {polymarket_timediff}")
        if polymarket_timediff > 1.0:
            logger.warning("Polymarket timediff too big, skipping")
            return None
        
    kalshi_yes_sorted = sorted([(price, volume) for price, volume in kalshi.yes_asks.items()])
    kalshi_no_sorted = sorted([(price, volume) for price, volume in kalshi.no_asks.items()])
    poly_yes_sorted = sorted([(price, volume) for price, volume in poly.yes_asks.items()])
    poly_no_sorted = sorted([(price, volume) for price, volume in poly.no_asks.items()])

    await try_arb(kalshi_yes_sorted, poly_no_sorted, kalshi.kalshi_ticker, poly.polymarket_no_ticker, 'yes') # kalshi yes sorted is yes asks so we BUY KALSHI YES'S
    await try_arb(kalshi_no_sorted, poly_yes_sorted, kalshi.kalshi_ticker, poly.polymarket_yes_ticker, 'no') # kalshi no sorted is no asks so we BUY KALSHI NO's


if __name__ == "__main__":

    while total_trades < 11:

        #time.sleep(2.5)

        # t1 = datetime.now(timezone.utc)
        # polymarket_client.get_ok()
        # t2 = datetime.now(timezone.utc)
        # logger.info(f"Polymarket health check latency: {(t2 - t1).total_seconds()}")
        # #logger.info(f"Polymarket balance: {polymarket_client.get_balance_allowance()}")

    
        # t1 = datetime.now(timezone.utc)
        # kalshi_client.get_exchange_status()
        # t2 = datetime.now(timezone.utc)
        # logger.info(f"Kalshi health check latency: {(t2 - t1).total_seconds()}")
        # logger.info(f"Kalshi balance: {kalshi_client.get_balance()}")

        asyncio.run(run_it_up())
    
