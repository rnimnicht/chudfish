import asyncio
import traceback
from abc import ABC, abstractmethod

from fastlogging import LogInit
from websockets import connect
from websockets.exceptions import ConnectionClosedError

from shared.models.orderbook import Orderbook

logger = LogInit(domain=__name__, console=True, level=10)

class BaseListener(ABC):

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
        try:
            await ws.send(subscribe_message)
        except Exception as e:
            logger.info(f"FAILED TO SUBSCRIBE: {e}, {e.__class__.__name__}")
            raise
        self.write_seq_id += 1

    async def unsubscribe(self, ws, subscription):
        unsubscribe_message = subscription.get_unsubscribe_message(self.write_seq_id)
        logger.debug(f"UNSUBSCRIBING {subscription.market_ticker}: {unsubscribe_message} ")
        try:
            await ws.send(unsubscribe_message)
        except Exception as e:
            logger.info(f"FAILED TO SUBSCRIBE: {e}, {e.__class__.__name__}")
            logger.warning(f"Connection closed while unsubscribing {subscription.market_ticker}, ignoring")
            return
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
            # Catch ConnectionClosedError's when trying to subscribe
            # We want to re-queue our active sub's and try again
            except Exception as e:
                if isinstance(e, ConnectionClosedError):
                    async with self._subs_lock:
                        logger.error(f"WebSocket connection lost: {e}. ...")
                        if self.active_subscriptions:
                            await sub_queue.put(dict(self.active_subscriptions))
                        self.active_subscriptions = {}
                        self.write_seq_id = 1
                else:
                    traceback.print_exc()
                    logger.error(f"{e}, {e.__class__.__name__}")
