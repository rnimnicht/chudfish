import asyncio
import json
from abc import ABC, abstractmethod

from websockets import connect
from websockets.exceptions import ConnectionClosed

from shared.models import Orderbook

class Listener(ABC):

    def __init__(self, uri, r, platform_name, market_name):
        self.uri = uri
        self.r = r
        self.market_name = market_name
        self.r_key = f"{platform_name}:{market_name}"
        self.orderbook = Orderbook(yes_asks={}, no_asks={})
        self.ticker_map = {}

    @abstractmethod
    async def get_headers(self):
        return {}

    @abstractmethod
    async def handle_message(self, message):
        pass

    async def consumer_handler(self, ws):
        async for msg in ws:
            await self.handle_message(msg)

    async def producer_handler(self, ws, sub_queue):
        while True:
            subscription = await sub_queue.get()
            print(subscription)
            self.ticker_map[subscription['market_ticker']] = subscription['market_name']
            await ws.send(json.dumps(subscription['msg']))
            sub_queue.task_done()
            print("Processed queue item")

    async def run(self, sub_queue):
        print('im running bish')
        async with connect(self.uri, additional_headers=await self.get_headers()) as ws:
            await asyncio.gather(
                self.consumer_handler(ws),
                self.producer_handler(ws, sub_queue)
            )

