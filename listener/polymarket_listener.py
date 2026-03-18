import base64
import json
import os
import time
import requests

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from shared.listener import Listener
from shared.models import Orderbook

class PolymarketListener(Listener):

    def __init__(self, r):
        super().__init__(os.environ.get('POLYMARKET_WS_URI'), r, 'polymarket')
        self.asset_id_map = {}

    async def get_headers(self):
                return {}
    
    async def check_sequence_id(self, seq_id):
        if seq_id != self.read_seq_id:
            print('u fuqd up lol')
        else:
            self.read_seq_id += 1

    async def subscribe(self, ws, market_ticker, market_name):

        tids = json.loads(requests.get(f'https://gamma-api.polymarket.com/markets/{market_ticker}').json()['clobTokenIds'])

        for t in tids:
             self.ticker_map[t] = market_name
        self.asset_id_map[tids[0]] = False
        self.asset_id_map[tids[1]] = True

        subscribe_message = {
            "assets_ids": tids,
            "type": "market",
            "initial_dump": True,
            "custom_feature_enabled": False
        }
        await ws.send(json.dumps(subscribe_message))

    # TODO: LOTS OF ERROR HANDLING
    async def handle_message(self, message):

        data = json.loads(message)
        if isinstance(data, dict):
            data = [data]

        for msg in data:
            if msg['event_type'] == 'book':
                print(f"Polymarket orderbook snapshot recieved")
                key = f"polymarket:{self.ticker_map[msg['asset_id']]}"
                snapshot = await self.r.get(key)
                if snapshot:
                    snapshot = Orderbook.from_redis(json.loads(snapshot))
                else:
                    snapshot = Orderbook(yes_asks={}, no_asks={})
                snapshot.apply_polymarket_book(msg, is_yes=self.asset_id_map[msg['asset_id']])
                serialized = snapshot.to_redis()
                await self.r.set(key, serialized)
                await self.r.publish(key, serialized)

            elif msg['event_type'] == 'price_change':
                # Group changes by market key — yes and no tokens map to the same market
                market_updates = {}
                for change in msg['price_changes']:
                    asset_id = change['asset_id']
                    key = f"polymarket:{self.ticker_map[asset_id]}"
                    market_updates.setdefault(key, []).append((change, self.asset_id_map[asset_id]))

                for key, changes in market_updates.items():
                    print(f"Polymarket orderbook update for {key}")
                    raw = await self.r.get(key)
                    if raw:
                        orderbook = Orderbook.from_redis(json.loads(raw))
                        for change, is_yes in changes:
                            orderbook.apply_polymarket_price_change(change, is_yes)
                        serialized = orderbook.to_redis()
                        await self.r.set(key, serialized)
                        await self.r.publish(key, serialized)
