import asyncio
import json
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
        self.kalshi_balance = 50.0
        self.polymarket_balance = 50.0
        self.r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)

    async def _persist_balances(self):
        await self.r.set("balance:kalshi", self.kalshi_balance)
        await self.r.set("balance:polymarket", self.polymarket_balance)

    async def polymarket_fill_listener(self):
        pubsub = self.r.pubsub()
        await pubsub.subscribe("polymarket:user")
        async for msg in pubsub.listen():
            if msg and msg['type'] == "message":
                try:
                    data = json.loads(msg['data'])
                    self.polymarket_balance -= float(data[0]['size']) * float(data[0]['price'])
                    logger.info(f"new polymarket bal: {self.polymarket_balance}")
                    await self._persist_balances()
                except Exception as e:
                    logger.error(e)

    async def kalshi_fill_listener(self):
        pubsub = self.r.pubsub()
        await pubsub.subscribe("kalshi:user")
        async for msg in pubsub.listen():
            if msg and msg['type'] == "message":
                try:
                    data = json.loads(msg['data'])
                    if data['side'] == 'yes':
                        self.kalshi_balance -= float(data['count_fp']) * float(data['yes_price_dollars'])
                    elif data['side'] == 'no':
                        self.kalshi_balance -= float(data['count_fp']) * float(data['no_price_dollars'])
                    logger.info(f"new kalshi bal: {self.kalshi_balance}")
                    await self._persist_balances()
                except Exception as e:
                    logger.error(e)

    async def check_bal(self):
        logger.info("Resetting balance")
        self.kalshi_balance = 50.0
        self.polymarket_balance = 50.0
        await self._persist_balances()

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
 