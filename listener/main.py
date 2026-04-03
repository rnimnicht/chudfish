import asyncio
import os
import uvloop

from fastlogging import LogInit
from pymongo import MongoClient
import redis.asyncio as redis

from listeners.kalshi_listener import KalshiListener
from listeners.polymarket_listener import PolymarketListener
from listeners.kalshi_user_listener import KalshiUserListener
from subscription_managers.crypto15min_subscription_manager import Crypto15MinSubscriptionManager
from subscription_managers.longstanding_subscription_manager import LongstandingSubscriptionManager

from models.subscriptions.kalshi_fill_subscription import KalshiFillSubscription

logger = LogInit(domain=__name__, console=True, level=10)
r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)
mongo_client = MongoClient(os.environ.get('MONGODB_URI'))

# here we want to query mongodb and spin up listener managers as-needed

async def main():

    # We will have different websockets for each market type. not optimal but it's what's supported by what i wrote /shrug

    # Kalshi user channels
    kalshi_user_queue = asyncio.Queue()
    kalshi_user_listener = KalshiUserListener(r)
    await kalshi_user_queue.put({"fill": KalshiFillSubscription()})

    # Crypto 15 minute market setup
    crypto15min_polymarket_listener = PolymarketListener(r)
    crypto15min_kalshi_listener = KalshiListener(r)
    crypto15min_polymarket_queue = asyncio.Queue()
    crypto15min_kalshi_queue = asyncio.Queue()
    crypto15min_manager = Crypto15MinSubscriptionManager(client=mongo_client)

    # Longstanding binary market setup
    longstanding_polymarket_listener = PolymarketListener(r)
    longstanding_kalshi_listener = KalshiListener(r)
    longstanding_polymarket_queue = asyncio.Queue()
    longstanding_kalshi_queue = asyncio.Queue()
    longstanding_manager = LongstandingSubscriptionManager(client=mongo_client)


    await asyncio.gather(

        crypto15min_manager.run(crypto15min_kalshi_queue, crypto15min_polymarket_queue),
        (crypto15min_polymarket_listener.run(crypto15min_polymarket_queue)), 
        (crypto15min_kalshi_listener.run(crypto15min_kalshi_queue)),

        longstanding_manager.run(longstanding_kalshi_queue, longstanding_polymarket_queue),
        (longstanding_polymarket_listener.run(longstanding_polymarket_queue)),
        (longstanding_kalshi_listener.run(longstanding_kalshi_queue)),

        (kalshi_user_listener.run(kalshi_user_queue)),

    )

if __name__ == '__main__':
    logger.info("Booting up listeners")
    uvloop.run(main())
    