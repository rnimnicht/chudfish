import asyncio
import os
import uvloop

from datetime import datetime, timezone
from asyncio import Queue
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastlogging import LogInit

import redis.asyncio as redis

logger = LogInit(domain=__name__, console=True, level=10)

class BalanceManager():

    def __init__(self):
        self.kalshi_balance = 50
        self.polymarket_balance = 50
        self.r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)

    async def polymarket_fill_listener(self):
        pubsub = self.r.pubsub()
        await pubsub.subscribe("polymarket:user")
        async for msg in pubsub.listen():
            if msg and msg['type'] == "message":
                try:
                    logger.info(f"recieved polymarket fill: {msg['data']}")
                except Exception as e:
                    logger.error(e)

    async def kalshi_fill_listener(self):
        pubsub = self.r.pubsub()
        await pubsub.subscribe("kalshi:user")
        async for msg in pubsub.listen():
            if msg and msg['type'] == "message":
                try:
                    logger.info(f"recieved kalshi fill: {msg['data']}")
                except Exception as e:
                    logger.error(e)
    
    async def check_bal(self):
        logger.info("Resetting balance")
        self.kalshi_balance = 50
        self.polymarket_balance = 50

    async def run(self):
        logger.info("Starting balance manager")
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            self.check_bal,
            'cron',
            minute='0,15,30,45',
            second=20
        )
        scheduler.start()

        await asyncio.gather(
            (self.polymarket_fill_listener()),
            (self.kalshi_fill_listener()),
        )
 