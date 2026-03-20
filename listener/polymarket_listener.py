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

    # Polymarket websocket API doesn't require headers
    async def get_headers(self):
        return {}
    
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
                try:
                    snapshot.apply_polymarket_book(msg, subscription.reverse)
                except:
                    logger.error(f"FAILED TO APPLY POLYMARKET SNAPSHOT: {msg}")
                serialized = snapshot.to_redis()
                await self.r.set(subscription.key, serialized)
                await self.r.publish(subscription.key, serialized)

            # Orderbook updates
            elif msg['event_type'] == 'price_change':
                # Group changes by market key — yes and no tokens map to the same market
                # (so could save a redis read)
                # 2 layz to think rn tho
                for change in msg['price_changes']:
                    if change['side'] != 'BUY':
                        continue
                    token_id = change['asset_id']
                    subscription = self.active_subscriptions[token_id]
                    raw = await self.r.get(subscription.key)
                    orderbook = Orderbook.from_redis(json.loads(raw))
                    try:
                        orderbook.apply_polymarket_price_change(change, subscription.reverse)
                    except:
                        logger.error(f"FAILED TO APPLY POLYMARKET CHANGE: {msg}")
                    
                    serialized = orderbook.to_redis()
                    await self.r.set(subscription.key, serialized)
                    await self.r.publish(subscription.key, serialized)
            else:
                logger.info(f"OTHER POLYMARKET MSG: {msg['event_type']}")
