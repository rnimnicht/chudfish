import asyncio
from abc import ABC, abstractmethod

from fastlogging import LogInit
from websockets import connect
from websockets.exceptions import ConnectionClosed

from shared.models.orderbook import Orderbook

logger = LogInit(domain=__name__, console=True, level=10)

class AbstractListener(ABC):

    def __init__(self, uri, r):
        self.uri = uri
        self.r = r
        self.ticker_map = {}
        self.active_subscriptions = {}
        self.write_seq_id = 1

    @abstractmethod
    async def get_headers(self):
        return {}

    @abstractmethod
    async def handle_message(self, message):
        pass

    async def subscribe(self, ws, subscription):
        subscribe_message = subscription.get_subscribe_message(self.write_seq_id)
        logger.debug(f"SUBSCRIBING: {subscribe_message} ")
        await ws.send(subscribe_message)
        self.write_seq_id += 1

    async def unsubscribe(self, ws, subscription):
        unsubscribe_message = subscription.get_unsubscribe_message(self.write_seq_id)
        logger.debug(f"UNSUBSCRIBING: {unsubscribe_message} ")
        await ws.send(unsubscribe_message)
        self.write_seq_id += 1

    async def consumer_handler(self, ws):
        async for msg in ws:
            await self.handle_message(msg)

    async def producer_handler(self, ws, sub_queue):

        while True:

            # {market_ticker: Subscription ...}
            subscriptions = await sub_queue.get()

            # add new subscriptions
            for mn, s in subscriptions.items():
                if mn not in self.active_subscriptions:
                    self.active_subscriptions[mn] = s
                    await self.subscribe(ws, s)
                    await asyncio.sleep(0.01)

            # then delete old subscriptions
            for mn, s in self.active_subscriptions.items():
                if mn not in subscriptions:
                    await self.unsubscribe(ws, s)
            self.active_subscriptions = {k : v for k, v in self.active_subscriptions.items() if k in subscriptions}
                
            sub_queue.task_done()
            logger.debug("Processed subscription refresh")

    async def run(self, sub_queue):
        logger.info("Listener starting")
        async with connect(self.uri, additional_headers=await self.get_headers()) as ws:
            await asyncio.gather(
                self.consumer_handler(ws),
                self.producer_handler(ws, sub_queue)
            )

