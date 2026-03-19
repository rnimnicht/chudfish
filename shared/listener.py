import asyncio
from abc import ABC, abstractmethod

from fastlogging import LogInit
from websockets import connect
from websockets.exceptions import ConnectionClosed

from shared.models import Orderbook

logger = LogInit(domain=__name__, console=True, level=10)

class Listener(ABC):

    def __init__(self, uri, r, platform_name):
        self.uri = uri
        self.r = r
        self.ticker_map = {}

    @abstractmethod
    async def get_headers(self):
        return {}

    @abstractmethod
    async def handle_message(self, message):
        pass

    @abstractmethod
    async def subscribe(self, ws, market_ticker, market_name):
        pass

    async def consumer_handler(self, ws):
        async for msg in ws:
            await self.handle_message(msg)

    async def producer_handler(self, ws, sub_queue):
        while True:
            subscription = await sub_queue.get()
            if subscription['market_ticker'] and subscription['market_name']:
                await self.subscribe(ws, subscription['market_ticker'], subscription['market_name'])
                logger.info(f"Subscribed: {subscription}")
            else:
                logger.warning(f"Bad subscription: {subscription}")
            sub_queue.task_done()
            logger.debug("Processed subscription request")

    async def run(self, sub_queue):
        logger.info("Listener starting")
        async with connect(self.uri, additional_headers=await self.get_headers()) as ws:
            await asyncio.gather(
                self.consumer_handler(ws),
                self.producer_handler(ws, sub_queue)
            )

