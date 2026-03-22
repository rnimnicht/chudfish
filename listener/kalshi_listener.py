import base64
import json
import os
import time


from fastlogging import LogInit

from shared.listener import AbstractListener
from shared.models.orderbook import Orderbook
from shared.models.kalshisubscription import KalshiSubscription
from shared.constants import get_kalshi_headers

logger = LogInit(domain=__name__, console=True, level=10)

class KalshiListener(AbstractListener):

    def __init__(self, r):

        super().__init__(os.environ.get('KALSHI_WS_URI'), r)

        self.read_seq_id = 1
        self.last_subscription = None
        self.headers = get_kalshi_headers("GET", "/trade-api/ws/v2")

    async def subscribe(self, ws, subscription: KalshiSubscription):
        await super().subscribe(ws, subscription=subscription)
        self.last_subscription = subscription.market_ticker

    # We should maybe put a restart here if we lose our sequence place
    async def check_read_sequence_id(self, seq_id):
        if seq_id != self.read_seq_id:
            logger.error(f"Sequence ID mismatch: expected {self.read_seq_id}, got {seq_id}")
        else:
            self.read_seq_id += 1

    # TODO: Also subscribe to Market Lifecycle?
    async def handle_message(self, message):

        data = json.loads(message)
        msg_type = data.get('type')
        msg = data.get('msg', {})

        if msg_type == "subscribed":
            logger.info(f"Kalshi subscribed: {data}, {self.last_subscription}")
            if self.last_subscription:
                self.active_subscriptions[self.last_subscription].sid = msg['sid']

        elif msg_type == "orderbook_snapshot":
            if 'yes_dollars_fp' not in msg:
                logger.warning(f"KALSHI TICKER {msg['market_ticker']} GOT NO DATA")
                await self.check_read_sequence_id(data.get('seq'))
                return
            subscription = self.active_subscriptions[msg['market_ticker']]
            orderbook = Orderbook(yes_asks={}, no_asks={}, market_ticker=msg['market_ticker'])
            try:
                orderbook.apply_kalshi_snapshot(msg)
            except Exception:
                logger.error(f"FAILED TO SERIALIZE KALSHI ORDERBOOK SNAPSHOT: {msg}")
            serialized = orderbook.to_redis()
            await self.r.set(subscription.key, serialized)
            await self.r.publish(subscription.key, serialized)

        elif msg_type == "orderbook_delta":
            subscription = self.active_subscriptions[msg['market_ticker']]
            #logger.info(f"KALSHI UPDATE {subscription.key}")
            raw = await self.r.get(subscription.key)
            if raw:
                orderbook = Orderbook.from_redis(json.loads(raw))
                orderbook.market_ticker = msg['market_ticker']
                try:
                    orderbook.apply_kalshi_delta(msg)
                except Exception:
                    logger.error(f"FAILED TO APPLY KALSHI DELTA: {msg}")
                serialized = orderbook.to_redis()
                await self.r.set(subscription.key, serialized)
                await self.r.publish(subscription.key, serialized)

        elif msg_type == "ok":
            if 'market_tickers' in msg:
                for mt in msg['market_tickers']:
                    self.active_subscriptions[mt].sid = data['sid']
            else:
                logger.debug(f"Received Kalshi ok: {data}")

        elif msg_type == "error":
            logger.error(f"Received Kalshi error msg: {data}")

        else:
            logger.debug(f"Received Kalshi {msg_type}: {data}")
        await self.check_read_sequence_id(data.get('seq'))
