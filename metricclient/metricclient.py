import os
import asyncio

import redis.asyncio as redis
import uvloop
from pymongo import MongoClient
from fastlogging import LogInit

from shared.models.metrics.crypto_15_min_arb_metric import Crypto15MinArbMetric


logger = LogInit(domain=__name__, console=True, level=10)
r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)
mongo_client = MongoClient(os.environ.get('MONGODB_URI'))

def get_collection(marketname: str):
    db_name = marketname.lower().replace('-', '_').replace(' ', '_')
    return mongo_client[db_name]['mock_trader_v1']

async def push_mock_trader_metrics():
    pubsub = r.pubsub()
    await pubsub.subscribe("mock-trader-v1-results")
    async for msg in pubsub.listen():
        if msg and msg['type'] == "message":
            try:
                metric = Crypto15MinArbMetric.model_validate_json(msg['data'])
                metric.populate()
                collection = get_collection(metric.market)
                collection.insert_one(metric.model_dump())
                logger.info(f"Stored trade metric for market {metric.market}")
            except Exception as e:
                logger.error(e)

if __name__ == "__main__":
    logger.info("Starting metric client")
    uvloop.run(push_mock_trader_metrics())

