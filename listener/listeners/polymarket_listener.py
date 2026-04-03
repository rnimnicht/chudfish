import json
import os

from fastlogging import LogInit

from listeners.base_listener import BaseListener
from shared.models import Orderbook
from shared.constants import POLYMARKET_WS_URI

logger = LogInit(domain=__name__, console=True, level=10)

class PolymarketListener(BaseListener):

    def __init__(self, r):
        super().__init__(POLYMARKET_WS_URI, r)

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
                if token_id not in self.active_subscriptions:
                    logger.error(f"Failed to apply polymarket orderbook to non-existent subscription: {token_id}")
                    return
                subscription = self.active_subscriptions[token_id]
                snapshot = await self.r.get(subscription.key)
                if snapshot:
                    snapshot = Orderbook.from_redis(json.loads(snapshot))
                else:
                    snapshot = Orderbook(yes_asks={}, no_asks={})
                if subscription.reverse:
                    snapshot.polymarket_no_ticker = subscription.market_ticker
                else:
                    snapshot.polymarket_yes_ticker = subscription.market_ticker
                try:
                    snapshot.apply_polymarket_book(msg, subscription.reverse)
                except Exception:
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
                    if change['side'] != 'SELL':
                        continue
                    token_id = change['asset_id']
                    if token_id not in self.active_subscriptions:
                        logger.warning(f"Failed to apply polymarket price change to non-existent subscription: {token_id}")
                        return
                    subscription = self.active_subscriptions[token_id]
                    raw = await self.r.get(subscription.key)
                    orderbook = Orderbook.from_redis(json.loads(raw))
                    if subscription.reverse:
                        orderbook.polymarket_no_ticker = subscription.market_ticker
                    else:
                        orderbook.polymarket_yes_ticker = subscription.market_ticker
                    try:
                        orderbook.apply_polymarket_price_change(change, subscription.reverse)
                    except Exception:
                        logger.error(f"FAILED TO APPLY POLYMARKET CHANGE: {msg}")
                    
                    serialized = orderbook.to_redis()
                    await self.r.set(subscription.key, serialized)
                    await self.r.publish(subscription.key, serialized)
            elif msg['event_type'] == 'last_trade_price':
                pass
            else:
                logger.info(f"OTHER POLYMARKET MSG: {msg['event_type']}")
