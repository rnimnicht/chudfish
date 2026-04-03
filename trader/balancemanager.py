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
        while True:
            msg = await pubsub.get_message()
            if msg and msg['type'] == "message":
                try:
                    logger.info(f"recieved polymarket fill: {msg['data']}")
                except Exception as e:
                    logger.error(e)

    async def kalshi_fill_listener(self):
        pubsub = self.r.pubsub()
        await pubsub.subscribe("kalshi:user")
        while True:
            msg = await pubsub.get_message()
            if msg and msg['type'] == "message":
                try:
                    logger.info(f"recieved kalshi fill: {msg['data']}")
                except Exception as e:
                    logger.error(e)
    
    async def check_bal(self):
        self.kalshi_balance = 50
        self.polymarket_balance = 50

    async def run(self):
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            self.check_bal,
            'cron',
            minute='0,15,30,45',
            second=20
        )

        await asyncio.gather(
            scheduler.start(),
            (self.polymarket_fill_listener()),
            (self.kalshi_fill_listener()),
        )

        scheduler.start()
 