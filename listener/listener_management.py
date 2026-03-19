import asyncio
import os

import uvloop

from fastlogging import LogInit
from pymongo import MongoClient
import redis.asyncio as redis

from kalshi_listener import KalshiListener
from polymarket_listener import PolymarketListener
from shared.models import Matched_Market

logger = LogInit(console=True, level=10)

r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)
mongo_client = MongoClient(os.environ.get('MONGODB_URI'))

async def sub_manager(polymarket_queue, kalshi_queue):

    global mongo_client

    subscribed_polymarket = set()
    subscribed_kalshi = set()

    while True:
        markets = [Matched_Market.from_mongo(obj) for obj in mongo_client.markets.matched_markets.find()]
        for market in markets:
            for platform in market.markets:
                if platform.platform_name == 'polymarket' and platform.uri not in subscribed_polymarket:
                    subscribe_message = {'market_name': market.name, 'market_ticker': platform.uri}
                    polymarket_queue.put_nowait(subscribe_message)
                    subscribed_polymarket.add(platform.uri)
                if platform.platform_name == 'kalshi' and platform.uri not in subscribed_kalshi:
                    subscribe_message = {'market_name': market.name, 'market_ticker': platform.uri}
                    kalshi_queue.put_nowait(subscribe_message)
                    subscribed_kalshi.add(platform.uri)

        await asyncio.sleep(180)
                

async def main():
    polymarket_listener = PolymarketListener(r)
    kalshi_listener = KalshiListener(r)
    polymarket_queue = asyncio.Queue()
    kalshi_queue = asyncio.Queue()
    await asyncio.gather(
        sub_manager(polymarket_queue, kalshi_queue), 
        (polymarket_listener.run(polymarket_queue)), 
        (kalshi_listener.run(kalshi_queue))
    )
    

if __name__ == '__main__':
    logger.info("Booting up listeners")
    uvloop.run(main())
    