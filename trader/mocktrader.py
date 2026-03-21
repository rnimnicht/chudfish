import os
import time
import json
from datetime import datetime, timezone

import redis
from pymongo import MongoClient

from shared.models.matched_market import Matched_Market
from shared.models.orderbook import Orderbook

# want the logic to be single threaded for safety
r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)

# maybe do metric publishes on a separate thread? should rlly figure that out
mongo_client = MongoClient(os.environ.get('MONGODB_URI'))
arb_collection = mongo_client['chudfish']['trades']['mock_trader_v1']

market_names = []

def run_it_up(market):
    print(f"running it up for {market}")

    now = datetime.now(timezone.utc)

    books = {}
    for platform in ['kalshi', 'polymarket']:
        raw = r.get(f"{platform}:{market}")
        if raw is None:
            print(f"no orderbook in redis for {platform}:{market}, skipping")
            return
        books[platform] = Orderbook.from_redis(json.loads(raw))

    kalshi = books['kalshi']
    poly = books['polymarket']

    # skip if any side is empty
    if not kalshi.yes_asks or not kalshi.no_asks:
        print(f"empty orderbook side for kalshi {market}, skipping")
        return
    if not poly.yes_asks or not poly.no_asks:
        print(f"empty orderbook side for {market}, skipping")
        return
    
    # time check
    if not kalshi.last_update_time:
        print("no kalshi snapshot timestamp; skipping")
        return
    else:
        kalshi_timediff = (now - kalshi.last_update_time).total_seconds()
        print(f"Kalshi snapshot time diff: {kalshi_timediff}")
        if kalshi_timediff > 1.0:
            print("Kalshi timediff too big, skipping")
            return None

    if not poly.last_update_time:
        print("no polymarket snapshot timestamp; skipping")
        return
    else:
        polymarket_timediff = (now - poly.last_update_time).total_seconds()
        print(f"Polymarket snapshot time diff: {polymarket_timediff}")
        if polymarket_timediff > 1.0:
            print("Polymarket timediff too big, skipping")
            return None

    kalshi_yes_max = max(kalshi.yes_asks)
    kalshi_no_max = max(kalshi.no_asks)
    poly_yes_max = max(poly.yes_asks)
    poly_no_max = max(poly.no_asks)


    # arb: buy kalshi yes + buy polymarket no
    combo1 = kalshi_yes_max + poly_no_max
    if combo1 < 1.0:
        min_volume = min(poly.no_asks[poly_no_max] * poly_no_max, kalshi.yes_asks[kalshi_yes_max] * kalshi_yes_max)
        max_return = ((min_volume * (1.0 / combo1)) - min_volume) * 2.0
        arb_collection.insert_one({
            'market': market,
            'type': 'kalshi_yes_poly_no',
            'kalshi_yes_price': kalshi_yes_max,
            'poly_no_price': poly_no_max,
            'combined_price': combo1,
            'min_volume': min_volume,
            'timestamp': now,
            'max_return': max_return
        })
        print(f"ARB kalshi_yes+poly_no={combo1:.4f} for {market}, max return {max_return}")

    # arb: buy kalshi no + buy polymarket yes
    combo2 = kalshi_no_max + poly_yes_max
    if combo2 < 1.0:
        min_volume = min(poly.yes_asks[poly_yes_max] * poly_yes_max, kalshi.no_asks[kalshi_no_max] * kalshi_no_max)
        max_return = ((min_volume * (1.0 / combo2)) - min_volume) * 2.0
        arb_collection.insert_one({
            'market': market,
            'type': 'kalshi_no_poly_yes',
            'kalshi_no_price': kalshi_no_max,
            'poly_yes_price': poly_yes_max,
            'min_volume': min_volume,
            'combined_price': combo2,
            'timestamp': now,
            'max_return': max_return
        })
        print(f"ARB kalshi_no+poly_yes={combo2:.4f} for {market}, max return {max_return}")


def main():
    for m in market_names:
        run_it_up(m)


if __name__ == "__main__":
    market_names = [Matched_Market.from_mongo(obj).name for obj in mongo_client.markets.matched_markets.find()] + [Matched_Market.from_mongo(obj).name for obj in mongo_client.markets.recurring_markets.find()]
    # account for startup time - we should have a better way to do this though
    time.sleep(20)
    while True:
        main()
        time.sleep(15)
