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
        self._subs_lock = asyncio.Lock()
        self.headers = {}

    @abstractmethod
    async def handle_message(self, message):
        pass

    async def subscribe(self, ws, subscription):
        subscribe_message = subscription.get_subscribe_message(self.write_seq_id)
        logger.debug(f"SUBSCRIBING {subscription.market_ticker}: {subscribe_message} ")
        await ws.send(subscribe_message)
        self.write_seq_id += 1

    async def unsubscribe(self, ws, subscription):
        unsubscribe_message = subscription.get_unsubscribe_message(self.write_seq_id)
        logger.debug(f"UNSUBSCRIBING {subscription.market_ticker}: {unsubscribe_message} ")
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
            to_add = {}
            to_remove = {}
            async with self._subs_lock:
                to_add = {mn: s for mn, s in subscriptions.items()
                          if mn not in self.active_subscriptions or self.active_subscriptions[mn] != s}
                to_remove = {mn: s for mn, s in self.active_subscriptions.items()
                             if mn not in subscriptions or subscriptions.get(mn) != s}
            # we want to set these fast
            for mn, s in to_remove.items():
                await self.r.set(s.key, Orderbook(yes_asks={}, no_asks={}).to_redis())
                await self.r.publish(s.key, Orderbook(yes_asks={}, no_asks={}).to_redis())
            for mn, s in to_remove.items():
                await self.unsubscribe(ws, s)
                async with self._subs_lock:
                    self.active_subscriptions.pop(mn, None)

            for mn, s in to_add.items():
                await self.subscribe(ws, s)
                await asyncio.sleep(0.01)
                async with self._subs_lock:
                    self.active_subscriptions[mn] = s
                
            sub_queue.task_done()
            logger.debug("Processed subscription refresh")

    async def run(self, sub_queue):
        logger.info("Listener starting")
        while True:
            try:
                # Connect generic
                async with connect(self.uri, additional_headers=self.headers) as ws:
                    await asyncio.gather(
                        self.consumer_handler(ws),
                        self.producer_handler(ws, sub_queue)
                    )
            except Exception as e:
                # Catches when a socket is unsubscribed
                # soooo we want to requeue it if it should still be active
                async with self._subs_lock:
                    if e in self.active_subscriptions:
                        # First make sure we're not sending to redis
                        await self.r.set(self.active_subscriptions[e].key, Orderbook(yes_asks={}, no_asks={}).to_redis())
                        await self.r.publish(self.active_subscriptions[e].key, Orderbook(yes_asks={}, no_asks={}).to_redis())
                        # We don't want to have to wait for the subscription refresh, so queue our active subs
                        sub_queue.put(self.active_subscriptions)
                        self.active_subscriptions = {}
                        self.write_seq_id = 1
                        logger.warning(f"Active WebSocket connection unexpectedly lost: {e}. Reconnecting...")
                    else:
                        print(e)
                        logger.error(f"WebSocket connection lost: {e}. ...")

