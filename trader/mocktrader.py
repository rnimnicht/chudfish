import os
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
from shared.constants import get_kalshi_client, get_polymarket_client, get_kalshi_headers


# want the logic to be single threaded for safety
time.sleep(60)

r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)
polymarket_client = get_polymarket_client()
kalshi_client = get_kalshi_client()

market_name = "btc15min"
# max buffer %
max_arb_percentage = 0.99
max_volume_per_trade = 100
min_required_liquidity = 300
kalshi_fee = lambda x : (x * 0.07 * (1.0-x)) + x
poly_fee = lambda x: (x * 0.25 * ((x * (1.0-x) )**2)) + x

logger = LogInit(domain=__name__, console=True, level=10)

def emit_metric():
    pass

def post_kalshi_order(kalshi_ticker, side, price: str, volume: int):
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
    
    return requests.post(f'https://api.elections.kalshi.com/trade-api/v2/portfolio/orders',
                                json=jsonrequest,
                                headers={**get_kalshi_headers("POST", "/trade-api/v2/portfolio/orders"), "Content-Type": "application/json"},
                                timeout=5
                                ).json()

def post_polymarket_order(polymarket_ticker, price: str, volume: int):

    test_order = polymarket_client.create_order(
        OrderArgs(
            token_id=polymarket_ticker,
            price=round(float(price), 2),
            size=int(volume),
            side=BUY,
        ),
        options=PartialCreateOrderOptions(tick_size="0.01")
    )

    try:
        resp = polymarket_client.post_order(test_order, OrderType.FAK)
        return resp
    except Exception as e:
        return e

def try_arb(kalshi_asks, poly_asks, kalshi_ticker, polymarket_ticker, kalshi_side):

    # logger.info(f"kalshi asks: {kalshi_asks}")
    # logger.info(f"poly asks: {poly_asks}")


    if (eff_arb := kalshi_fee(kalshi_asks[0][0]) + poly_fee(poly_asks[0][0])) > max_arb_percentage:
        logger.info(f"No arb: {eff_arb}")
        return False

    i = 0; j = 0
    total_volume = kalshi_asks[0][1] + poly_asks[0][1]

    # break when we achieve the required liquidity or out of orders
    # FIX:: BOTH SIDES SHOULD HAVE MIN LIQUIDITY
    while total_volume < min_required_liquidity and (i+1 < len(kalshi_asks) or j+1 < len(poly_asks)):

        logger.info(f"chud algoritihm {i} {j}, {kalshi_asks[i]}, {poly_asks[j]}")

        # kalshi_asks: [(price1: volume1), ...] (sorted by price:w

        # get the next available volumes if they're not above arb % and they're not at the end of the orderbook
        i_option = None; j_option = None
        if i+1 < len(kalshi_asks) and kalshi_fee(kalshi_asks[i+1][0]) + poly_fee(poly_asks[j][0]) < max_arb_percentage:
            logger.info("init more kalshi stuff")
            i_option = kalshi_asks[i+1]
        if j+1 < len(poly_asks) and kalshi_fee(kalshi_asks[i][0]) + poly_fee(poly_asks[j+1][0]) < max_arb_percentage:
            logger.info("init more polymarket stuff")
            j_option = poly_asks[j+1]

        # break if neither available
        if not i_option and not j_option:
            logger.info("neither option good")
            break

        # if either option not availible, choose the other option, else choose max volume
        elif not i_option and j_option != None:
            total_volume += j_option[1]
            j += 1
        elif not j_option and i_option != None:
            total_volume += i_option[1]
            i += 1
        elif i_option != None and j_option != None and i_option[1] > j_option[1]:
            total_volume += i_option[1]
            i += 1
        else:
            if j_option != None:
                total_volume += j_option[1]
                j += 1

    kalshi_price = kalshi_asks[i][0]
    polymarket_price = poly_asks[j][0]

    logger.info(f"{i}, {j}")

    logger.info(kalshi_asks[:i+1])
    logger.info(poly_asks[:j+1])

    # do we want max here?
    volume = min(max_volume_per_trade, total_volume)
    logger.info(f"Tradeable volume: {volume}")

    # Can't trade < $1
    if volume * min(kalshi_price, polymarket_price) < 1.0:
        logger.info("Not enough volume to trade")
        return False

    # Calculate effective prices and arbitrage opportunity
    logger.info(f"""GONNA TRY TO BUY!!!!\n
                ---kalshi price 1 {kalshi_price}, post fees {kalshi_fee(kalshi_price)}\n
                ---poly price 1 {polymarket_price}, post fees {poly_fee(polymarket_price)}\n
                ---arb min {kalshi_asks[0][0] + poly_asks[0][0]}, arb max {kalshi_asks[i][0] + poly_asks[j][0]}\n
                ---arb min vol {kalshi_asks[0][1] + poly_asks[0][1]}, arb max vol {total_volume}
    """)

    #kalshi_resp = post_kalshi_order(kalshi_ticker, kalshi_side, kalshi_asks[i][0], volume)
    #poly_resp = post_polymarket_order(polymarket_ticker, poly_asks[j][0], volume)

    #logger.info(kalshi_resp)
    #logger.info(poly_resp)


    data = {
        'market': market_name,
        'combined_price': kalshi_price + polymarket_price,
        'eff_combined_price': eff_arb,
        'min_volume': volume,
        'timestamp': str(datetime.now(timezone.utc)),
        'profit': volume*(1.0-(kalshi_asks[i][0]+poly_asks[j][0])) # should we put in safeguard if combo1 is 0? Should never happen but
    }

    if kalshi_side == 'yes':
        data['type'] = 'kalshi_yes_poly_no' 
        data['eff_kalshi_yes_price'] = kalshi_fee(kalshi_price)
        data['eff_poly_no_price'] = poly_fee(polymarket_price)
        data['kalshi_yes_price'] = kalshi_price 
        data['poly_no_price'] = kalshi_price 
    else:
        data['type'] = 'kalshi_no_poly_yes' 
        data['eff_kalshi_no_price'] = kalshi_fee(kalshi_price)
        data['eff_poly_yes_price'] = poly_fee(polymarket_price)
        data['kalshi_no_price'] = kalshi_price 
        data['poly_yes_price'] = kalshi_price 

    r.publish("mock-trader-v1-results", json.dumps(data))


def run_it_up():

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
        
    kalshi_yes_sorted = sorted([(1.0 - price, volume) for price, volume in kalshi.no_asks.items()]) # YES ASKS, -> 1.0 - NO BIDS
    kalshi_no_sorted = sorted([(1.0 - price, volume) for price, volume in kalshi.yes_asks.items()]) # NO ASKS, -> 1.0 - YES BIDS
    poly_yes_sorted = sorted([(price, volume) for price, volume in poly.yes_asks.items()]) # -> YES ASKS
    poly_no_sorted = sorted([(price, volume) for price, volume in poly.no_asks.items()]) # -> NO ASKS

    # logger.info(kalshi_yes_sorted)
    # logger.info(kalshi_no_sorted)
    # logger.info(poly_yes_sorted)
    # logger.info(poly_no_sorted)
        
    try_arb(kalshi_yes_sorted, poly_no_sorted, kalshi.kalshi_ticker, poly.polymarket_no_ticker, 'yes') # kalshi yes sorted is yes asks so we BUY KALSHI YES'S
    try_arb(kalshi_no_sorted, poly_yes_sorted, kalshi.kalshi_ticker, poly.polymarket_yes_ticker, 'no') # kalshi no sorted is no asks so we BUY KALSHI NO's

    # # arb: buy kalshi yes + buy polymarket no
    # tradeable_volume = min(kalshi_yes_volume, poly_no_volume)
    # eff_kalshi_price = (kalshi_yes_max * 0.07 * (1.0-kalshi_yes_max)) + kalshi_yes_max
    # eff_polymarket_price = (poly_no_max * 0.25 * ((poly_no_max * (1.0-poly_no_max) )**2)) + poly_no_max
    # logger.info(f"---kalshi price 1 {kalshi_yes_max}, post fees {eff_kalshi_price}")
    # logger.info(f"---poly price 1 {poly_no_max}, post fees {eff_polymarket_price}")
    # combo1 = eff_kalshi_price + eff_polymarket_price

    # if combo1 < 1.0:
    #     logger.info(f"ARB kalshi_yes+poly_no={combo1:.4f} for {market_name}, profit {tradeable_volume*(1.0-combo1)}")
    #     return

    # # arb: buy kalshi no + buy polymarket yes
    # tradeable_volume = min(kalshi_no_volume, poly_yes_volume)
    # eff_kalshi_price = (kalshi_no_max * 0.07 * (1.0-kalshi_no_max)) + kalshi_no_max
    # eff_polymarket_price = (poly_yes_max * 0.25 * ((poly_yes_max * (1.0-poly_yes_max))**2)) + poly_yes_max
    # logger.info(f"kalshi price 1 {kalshi_no_max}, post fees {eff_kalshi_price}")
    # logger.info(f"poly price 1 {poly_yes_max}, post fees {eff_polymarket_price}")
    # combo2 = eff_kalshi_price + eff_polymarket_price
    # if combo2 < 1.0:
    #     r.publish('mock-trader-v1-results', json.dumps({
    #         'market': market_name,
    #         'type': 'kalshi_no_poly_yes',
    #         'kalshi_no_price': kalshi_no_max,
    #         'poly_yes_price': poly_yes_max,
    #         'combined_price': kalshi_no_max + poly_yes_max,
    #         'eff_kalshi_no_price': eff_kalshi_price,
    #         'eff_poly_yes_price': eff_polymarket_price,
    #         'eff_combined_price': combo2,
    #         'min_volume': tradeable_volume,
    #         'timestamp': str(now),
    #         'profit': tradeable_volume*(1.0-combo2) # should we put in safeguard if combo1 is 0? Should never happen but
    #     }))
    #     logger.info(f"ARB kalshi_no+poly_yes={combo2:.4f} for {market_name}, profit {tradeable_volume*(1.0-combo2)}")
    # logger.info(f"Side 1: {combo1}, Side 2: {combo2}")

if __name__ == "__main__":

    while True:

        time.sleep(5)

        t1 = datetime.now(timezone.utc)
        polymarket_client.get_ok()
        t2 = datetime.now(timezone.utc)
        logger.info(f"Polymarket health check latency: {(t2 - t1).total_seconds()}")
        #logger.info(f"Polymarket balance: {polymarket_client.get_balance_allowance()}")

    
        t1 = datetime.now(timezone.utc)
        kalshi_client.get_exchange_status()
        t2 = datetime.now(timezone.utc)
        logger.info(f"Kalshi health check latency: {(t2 - t1).total_seconds()}")
        logger.info(f"Kalshi balance: {kalshi_client.get_balance()}")

        run_it_up()
    
