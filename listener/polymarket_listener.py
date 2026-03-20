import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from fastlogging import LogInit

from shared.listener import AbstractListener
from shared.models import Orderbook
from shared.models.polymarketsubscription import PolymarketSubscription

logger = LogInit(domain=__name__, console=True, level=10)

class PolymarketListener(AbstractListener):

    def __init__(self, r):
        super().__init__(os.environ.get('POLYMARKET_WS_URI'), r)
        self.asset_id_map = {}
        self.tid_side_map = {}  # tid -> 'yes' or 'no'
        self.tid_reverse_set = set()
        self.write_seq_id = 1

    # Polymarket websocket API doesn't require headers
    async def get_headers(self):
        return {}
    
    async def subscribe(self, ws, subscription: PolymarketSubscription):
        subscribe_message = subscription.get_subscribe_message(self.write_seq_id)
        logger.debug(f"POLYMARKET SUBSCRIPTION:{subscribe_message} ")
        await ws.send(subscribe_message)
        self.write_seq_id += 1

    async def unsubscribe(self, ws, subscription: PolymarketSubscription):
        unsubscribe_message = subscription.get_unsubscribe_message()
        logger.debug(f"POLYMARKET UNSUBSCRIBE:{unsubscribe_message} ")
        await ws.send(unsubscribe_message)

    # TODO: LOTS OF ERROR HANDLING
    async def handle_message(self, message):

        data = json.loads(message)

        # Some Polymarket wss responses are in lists, some aren't
        if isinstance(data, dict):
            data = [data]

        for msg in data:

            # Initial orderbook dump
            if msg['event_type'] == 'book':
                token_id = msg['asset_id']
                subscription = self.active_subscriptions[token_id]
                snapshot = await self.r.get(subscription.key)
                if snapshot:
                    snapshot = Orderbook.from_redis(json.loads(snapshot))
                else:
                    snapshot = Orderbook(yes_asks={}, no_asks={})
                snapshot.apply_polymarket_book(msg, subscription.side)
                serialized = snapshot.to_redis()
                await self.r.set(subscription.key, serialized)
                await self.r.publish(subscription.key, serialized)

            # Orderbook updates
            elif msg['event_type'] == 'price_change':
                # Group changes by market key — yes and no tokens map to the same market
                market_updates = {}
                #TODO: make sure we need two loops here... was vibecoded, seems odd
                # 2 layz to think rn tho
                for change in msg['price_changes']:
                    token_id = change['asset_id']
                    subscription = self.active_subscriptions[token_id]
                    
                    # We have two assetid streams -
                    # the sell orders are the buy orders
                    if change['side'] != 'BUY':
                        continue
                    market_updates.setdefault(subscription.key, []).append((change, subscription.side))

                for key, changes in market_updates.items():
                    raw = await self.r.get(key)
                    if raw:
                        orderbook = Orderbook.from_redis(json.loads(raw))
                        for change, side in changes:
                            orderbook.apply_polymarket_price_change(change, side)
                        serialized = orderbook.to_redis()
                        await self.r.set(key, serialized)
                        await self.r.publish(key, serialized)
