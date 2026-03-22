import os
import asyncio
import json

import redis.asyncio as redis
import uvloop
from pymongo import MongoClient
from fastlogging import LogInit


logger = LogInit(domain=__name__, console=True, level=10)
r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)
mongo_client = MongoClient(os.environ.get('MONGODB_URI'))
arb_collection = mongo_client['chudfish']['trades']['mock_trader_v1']

async def push_mock_trader_metrics():
    pubsub = r.pubsub()
    await pubsub.subscribe("mock-trader-v1-results")
    while True:
        await asyncio.sleep(5)
        msg = await pubsub.get_message()
        if msg and msg['type'] == "message":
            try:
                logger.info("published trade info")
                arb_collection.insert_one(json.loads(msg['data']))
            except Exception as e:
                logger.error(e)

if __name__ == "__main__":
    logger.info("Starting metric client")
    uvloop.run(push_mock_trader_metrics())

