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
        print(data)
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
                if self.asset_id_map[msg['asset_id']]:
                    snapshot.set_yes_from_polymarket_raw(msg)
                else:
                    snapshot.set_no_from_polymarket_raw(msg)
                serialized = snapshot.to_redis()
                await self.r.set(key, serialized)
                await self.r.publish(key, serialized)

            # TODO: make this work
            elif msg['event_type'] == 'price_change':
                key = f"polymarket:{self.ticker_map[msg['price_changes'][0]['asset_id']]}"
                print(f"Polymarket orderbook update for {key}")
