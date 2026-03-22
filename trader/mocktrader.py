import os
import time
import json
from datetime import datetime, timezone
import requests

import redis
from fastlogging import LogInit
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

from shared.models.matched_market import Matched_Market
from shared.models.orderbook import Orderbook
from shared.constants import get_kalshi_headers


# want the logic to be single threaded for safety
r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)

time.sleep(50)

# temp_client = ClobClient(
#     host="https://clob.polymarket.com",
#     chain_id=137,
#     key=os.environ.get("POLYMARKET_PRIVATE_KEY"))
# api_creds = temp_client.create_or_derive_api_creds()

# polymarket_client = ClobClient(
#     host="https://clob.polymarket.com",
#     chain_id=137,
#     key=os.environ.get("POLYMARKET_PRIVATE_KEY"),
#     creds=api_creds,
#     signature_type=1,
#     funder=os.environ.get("FUNDER_ADDRESS")
# )

market_name = "btc15min"

logger = LogInit(domain=__name__, console=True, level=10)

def run_it_up():
    logger.info(f"--. ݁₊ ⊹ . ݁˖ . ݁--running it up for {market_name}--. ݁₊ ⊹ . ݁˖ . ݁--")
    

    now = datetime.now(timezone.utc)

    #  ok sooooo
    # 1. read data and handle read edge cases
    # if OK, first send to lower volume
    # send order, wait for rec, send second order, wait for rec, cancel both orders
    # push to metric agent? i dunno this might take too long to implement so maybe don't idk

    # yes/no books for both platforms

    
    books = {}
    for platform in ['kalshi', 'polymarket']:
        raw = r.get(f"{platform}:{market_name}")
        if raw is None:
            logger.warning(f"no orderbook in redis for {platform}:{market_name}, skipping")
            return
        books[platform] = Orderbook.from_redis(json.loads(raw))

    kalshi = books['kalshi']
    poly = books['polymarket']
    # raw = r.get(f"kalshi:{market_name}")
    # if raw is None:
    #     logger.warning(f"no orderbook in redis for kalshi:{market_name}, skipping")
    # kalshi = Orderbook.from_redis(json.loads(raw))
 
    
    

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

    kalshi_yes_max = 1.0 - max(kalshi.no_asks)
    kalshi_yes_volume = kalshi.no_asks[max(kalshi.no_asks)]
    kalshi_no_max = 1.0 - max(kalshi.yes_asks)
    kalshi_no_volume = kalshi.yes_asks[max(kalshi.yes_asks)]
    poly_yes_max = 1.0 - max(poly.no_asks)
    poly_yes_volume = poly.no_asks[max(poly.no_asks)]
    poly_no_max = 1.0 - max(poly.yes_asks)
    poly_no_volume = poly.yes_asks[max(poly.yes_asks)]

    # logger.info(kalshi)

    # logger.info(jsonrequest := {"ticker": kalshi.kalshi_ticker,
    #                                   "side": "yes",
    #                                   "action": "buy",
    #                                   "yes_price_dollars": f"{kalshi_yes_max:.4f}",
    #                                   "count": 1,
    #                                   "time_in_force": "immediate_or_cancel"
    #                                   })

    # kalshi_resp = requests.post(f'https://api.elections.kalshi.com/trade-api/v2/portfolio/orders',
    #                             json=jsonrequest,
    #                             headers={**get_kalshi_headers("POST", "/trade-api/v2/portfolio/orders"), "Content-Type": "application/json"},
    #                             timeout=5
    #                             ).json()

    # logger.info(f"KALSHI HTTP ResPONSE: {kalshi_resp}")

    # test_order = polymarket_client.create_order(
    #     OrderArgs(
    #         token_id=poly.polymarket_no_ticker,
    #         price=float(f"{poly_no_max:.2f}"),
    #         size=1,
    #         side=BUY,
    #     ),
    #     options={}
    # )

    # logger.info(f"POLYMARKET CREDS {polymarket_client.creds}")

    # response = polymarket_client.post_order(test_order, OrderType.FAK)

    # logger.info("Poly Order ID:", response["orderID"])
    # logger.info("Poly Status:", response["status"])

    # logger.info(jsonrequest := {""})

    # poly_resp = requests.post(f'https://clob.polymarket.com/order',
    #                           json=jsonrequest,
    #                           headers={**get_polymarket_headers(""), 'Content-Type': 'application/json'},
    #                           timeout=5
    #                           ).json()

    # logger.info(f"POLY HTTP ResPONSE: {kalshi_resp}")





    # arb: buy kalshi yes + buy polymarket no
    tradeable_volume = min(kalshi_yes_volume, poly_no_volume)
    eff_kalshi_price = (kalshi_yes_max * 0.07 * (1.0-kalshi_yes_max)) + kalshi_yes_max
    eff_polymarket_price = (poly_no_max * 0.25 * ((poly_no_max * (1.0-poly_no_max) )**2)) + poly_no_max
    logger.info(f"---kalshi price 1 {kalshi_yes_max}, post fees {eff_kalshi_price}")
    logger.info(f"---poly price 1 {poly_no_max}, post fees {eff_polymarket_price}")
    combo1 = eff_kalshi_price + eff_polymarket_price

    if combo1 < 1.0:
        r.publish("mock-trader-v1-results", json.dumps({
            'market': market_name,
            'type': 'kalshi_yes_poly_no',
            'kalshi_yes_price': kalshi_yes_max,
            'poly_no_price': poly_no_max,
            'combined_price': kalshi_yes_max + poly_no_max,
            'eff_kalshi_yes_price': kalshi_yes_max,
            'eff_poly_no_price': poly_no_max,
            'eff_combined_price': combo1,
            'min_volume': tradeable_volume,
            'timestamp': str(now),
            'profit': tradeable_volume*(1.0-combo1) # should we put in safeguard if combo1 is 0? Should never happen but
        }))
        logger.info(f"ARB kalshi_yes+poly_no={combo1:.4f} for {market_name}, profit {tradeable_volume*(1.0-combo1)}")



        
        return

    # arb: buy kalshi no + buy polymarket yes
    tradeable_volume = min(kalshi_no_volume, poly_yes_volume)
    eff_kalshi_price = (kalshi_no_max * 0.07 * (1.0-kalshi_no_max)) + kalshi_no_max
    eff_polymarket_price = (poly_yes_max * 0.25 * ((poly_yes_max * (1.0-poly_yes_max))**2)) + poly_yes_max
    logger.info(f"kalshi price 1 {kalshi_no_max}, post fees {eff_kalshi_price}")
    logger.info(f"poly price 1 {poly_yes_max}, post fees {eff_polymarket_price}")
    combo2 = eff_kalshi_price + eff_polymarket_price
    if combo2 < 1.0:
        r.publish('mock-trader-v1-results', json.dumps({
            'market': market_name,
            'type': 'kalshi_no_poly_yes',
            'kalshi_no_price': kalshi_no_max,
            'poly_yes_price': poly_yes_max,
            'combined_price': kalshi_no_max + poly_yes_max,
            'eff_kalshi_no_price': eff_kalshi_price,
            'eff_poly_yes_price': eff_polymarket_price,
            'eff_combined_price': combo2,
            'min_volume': tradeable_volume,
            'timestamp': str(now),
            'profit': tradeable_volume*(1.0-combo2) # should we put in safeguard if combo1 is 0? Should never happen but
        }))
        logger.info(f"ARB kalshi_no+poly_yes={combo2:.4f} for {market_name}, profit {tradeable_volume*(1.0-combo2)}")
    logger.info(f"Side 1: {combo1}, Side 2: {combo2}")

        



if __name__ == "__main__":

    run_it_up()
    
