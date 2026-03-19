import os
import time

import redis
from pymongo import MongoClient

from shared.models import Matched_Market
from shared.mockplatformclient import MockPlatformClient

# want the logic to be single threaded for safety
r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)

platform_client1 = MockPlatformClient
platform_client2 = MockPlatformClient

# maybe do metric publishes on a separate thread? should rlly figure that out
mongo_client = MongoClient(os.environ.get('MONGODB_URI'))
market_names = []

def run_it_up(market):

    print(f"running it up for {market}")

    # check our redis markets
    books = {}
    for platform in ['kalshi', 'polymarket']:
        books[platform] = r.get(f"{platform}:{market}")

    # first check
    #if sort(books['kalshi'].yes_asks.keys) + sort(books['polymarket'].no_asks.keys):
    # should use some kinda data structure to speed up max/min's
    # kalshi_yes_max = max(books['kalshi'].yes_asks.keys)
    # kalshi_no_max = 
    # polymarket_yes_max = 
    # polymarket_no_max = 
    



def main():
    for m in market_names:
        run_it_up(m)


if __name__ == "__main__":


    # first pull the markets we wanna trade
    markets_names = [Matched_Market.from_mongo(obj).name for obj in mongo_client.markets.matched_markets.find()]
    while True:
        main()
        time.sleep(60)
