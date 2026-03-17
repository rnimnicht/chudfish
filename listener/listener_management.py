import asyncio
import json
import os
import time

from dotenv import load_dotenv
from pymongo import MongoClient
import redis.asyncio as redis

from kalshi_listener import KalshiListener
from shared.models import Matched_Market


r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)

async def sub_manager(queue):
    mongo_client = MongoClient(os.environ.get('MONGODB_URI'))
    subscribe_message = {
        'market_name': 'govshutdownlength',
        'market_ticker': 'KXRECSSNBER-26',
        'msg': {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_ticker": "KXRECSSNBER-26" 
            }
        }
    }
    time.sleep(5)
    print("adding to queue")
    queue.put_nowait(subscribe_message)

async def main():
    kalshi_listener = KalshiListener(r, "govshutdownlength", "KXRECSSNBER-26")
    queue = asyncio.Queue()
    await asyncio.gather(sub_manager(queue), (kalshi_listener.run(queue)))
    

if __name__ == '__main__':
    asyncio.run(main())
    