import json
import os
import requests

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from fastlogging import LogInit

from shared.listener import Listener
from shared.models import Orderbook

logger = LogInit(domain=__name__, console=True, level=10)

class PolymarketListener(Listener):

    def __init__(self, r):
        super().__init__(os.environ.get('POLYMARKET_WS_URI'), r, 'polymarket')
        self.asset_id_map = {}
        self.tid_side_map = {}  # tid -> 'yes' or 'no'

    async def get_headers(self):
                return {}
    
    async def subscribe(self, ws, market_ticker, market_name):

        tids = json.loads(requests.get(f'https://gamma-api.polymarket.com/markets/{market_ticker}').json()['clobTokenIds'])

        self.ticker_map[tids[0]] = market_name
        self.ticker_map[tids[1]] = market_name
        self.tid_side_map[tids[0]] = 'yes'
        self.tid_side_map[tids[1]] = 'no'

        subscribe_message = {
            "assets_ids": [tids[0], tids[1]],
            "type": "market",
            "initial_dump": True,
            "custom_feature_enabled": False
        }
        await ws.send(json.dumps(subscribe_message))

    # TODO: LOTS OF ERROR HANDLING
    async def handle_message(self, message):

        data = json.loads(message)

        # Some Polymarket wss responses are in lists, some aren't
        if isinstance(data, dict):
            data = [data]

        logger.debug(f"Received data: {data}")

        for msg in data:

            # Initial orderbook dump
            if msg['event_type'] == 'book':
                logger.debug("Polymarket orderbook snapshot received")
                asset_id = msg['asset_id']
                key = f"polymarket:{self.ticker_map[asset_id]}"
                side = self.tid_side_map[asset_id]
                snapshot = await self.r.get(key)
                if snapshot:
                    snapshot = Orderbook.from_redis(json.loads(snapshot))
                else:
                    snapshot = Orderbook(yes_asks={}, no_asks={})
                snapshot.apply_polymarket_book(msg, side)
                serialized = snapshot.to_redis()
                await self.r.set(key, serialized)
                await self.r.publish(key, serialized)

            # Orderbook updates
            elif msg['event_type'] == 'price_change':
                # Group changes by market key — yes and no tokens map to the same market
                market_updates = {}
                for change in msg['price_changes']:
                    asset_id = change['asset_id']
                    
                    # We have two assetid streams -
                    # the sell orders are the buy orders of the opposite assetid stream
                    if change['side'] != 'BUY':
                        continue
                    key = f"polymarket:{self.ticker_map[asset_id]}"
                    side = self.tid_side_map[asset_id]
                    market_updates.setdefault(key, []).append((change, side))

                for key, changes in market_updates.items():
                    logger.debug(f"Polymarket orderbook update for {key}")

                    # I think we can do this a bit faster? pre-load the orderbooks we need
                    # cuz if we changes on the same market w 2 asset ids we're doing 2 reads here
                    # but we only need 1
                    raw = await self.r.get(key)
                    if raw:
                        orderbook = Orderbook.from_redis(json.loads(raw))
                        for change, side in changes:
                            orderbook.apply_polymarket_price_change(change, side)
                        serialized = orderbook.to_redis()
                        await self.r.set(key, serialized)
                        await self.r.publish(key, serialized)
