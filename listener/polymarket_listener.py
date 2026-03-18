import base64
import json
import os
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from shared.listener import Listener
from shared.models import Orderbook

class PolymarketListener(Listener):

    def __init__(self, r):

        super().__init__(os.environ.get('POLYMARKET_WS_URI'), r, 'polymarket')

        # Polymarket auth setup
        #pem = os.environ.get('KALSHI_PRIVATE_KEY', '').replace('\\n', '\n')
        #self.private_key = serialization.load_pem_private_key(pem.encode(), password=None)
        #self.access_key = os.environ.get('KALSHI_ACCESS_KEY')

        self.read_seq_id = 1
        self.write_seq_id = 1

    async def get_headers(self):
                return {}
    
    async def check_sequence_id(self, seq_id):
        if seq_id != self.read_seq_id:
            print('u fuqd up lol')
        else:
            self.read_seq_id += 1

    async def subscribe(self, ws, market_ticker):
        subscribe_message = {
            "assets_ids": [market_ticker],
            "type": "market",
            "initial_dump": True,
            "custom_feature_enabled": False
        }
        print(subscribe_message)
        await ws.send(json.dumps(subscribe_message))
        self.write_seq_id += 1


    # TODO: LOTS OF ERROR HANDLING
    async def handle_message(self, message):

        data = json.loads(message)
        print(data)
        if isinstance(data, list):
            data = data[0]

        if data['event_type'] == 'book':
             print(f"Polymarket orderbook snapshot recieved")
             snapshot = Orderbook.from_polymarket_raw_orderbook(data)
             if snapshot:
                  key = f"polymarket:{self.ticker_map[data['asset_id']]}"
                  serialized = snapshot.to_redis()
                  await self.r.set(key, serialized)
                  await self.r.publish(key, serialized)
            
        elif data['event_type'] == 'price_change':
             key = f"polymarket:{self.ticker_map[data['price_changes'][0]['asset_id']]}"
             print(f"Polymarket orderbook update for {key}")
            #  raw = await self.r.get(key)
            #  if raw:
            #       orderbook = Orderbook.from_redis(json.loads(raw))




        # data = json.loads(message)
        # msg_type = data.get('type')
        # msg = data.get('msg', {})
        # print('poly msg rec: ', data)

        # if msg_type == "subscribed":
        #     print(f"Subscribed: {data}")

        # elif msg_type == "orderbook_snapshot":
        #     print(f"Orderbook snapshot recieved, seq: {self.read_seq_id}")
        #     await self.check_sequence_id(data.get('seq', int))
        #     snapshot = Orderbook.from_kalshi_raw_orderbook(msg)
        #     if snapshot:
        #         await self.r.set(f"kalshi:{self.ticker_map[msg['market_ticker']]}", snapshot.to_redis())
        
        # elif msg_type == "orderbook_delta":
        #     print(f"Orderbook update for {msg['market_ticker']}, seq: {self.read_seq_id}")
        #     await self.check_sequence_id(data.get('seq', int))
        #     key = f"kalshi:{self.ticker_map[msg['market_ticker']]}"
        #     raw = await self.r.get(key)
        #     if raw:
        #         orderbook = Orderbook.from_redis(json.loads(raw))
        #         side = orderbook.yes_asks if msg['side'] == 'yes' else orderbook.no_asks
        #         price = float(msg['price_dollars'])
        #         side[price] = side.get(price, 0.0) + float(msg['delta_fp'])
        #         if side[price] <= 0:
        #             del side[price]
        #         await self.r.set(key, orderbook.to_redis())

        # elif msg_type == "error":
        #     print(f"Recieved error msg: {data}")

        # else:
        #     print(f"Received [{msg_type}]: {data}")
