import base64
import json
import os
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from shared.listener import Listener
from shared.models import Orderbook

class KalshiListener(Listener):

    def __init__(self, r):

        super().__init__(os.environ.get('KALSHI_WS_URI'), r, 'kalshi')

        # Kalshi auth setup
        pem = os.environ.get('KALSHI_PRIVATE_KEY', '').replace('\\n', '\n')
        self.private_key = serialization.load_pem_private_key(pem.encode(), password=None)
        self.access_key = os.environ.get('KALSHI_ACCESS_KEY')

        self.read_seq_id = 1
        self.write_seq_id = 1

    async def get_headers(self):
        timestamp = str(int(time.time() * 1000))
        ws_path = os.environ.get("KALSHI_WS_PATH") or ""
        if ws_path == "":
            raise Exception("Couldn't find kalshi ws path environment variable")
            
        msg = (timestamp + "GET" + ws_path).encode('utf-8')
        signature = self.private_key.sign(msg,
                                          padding.PSS(
                                              mgf=padding.MGF1(hashes.SHA256()),
                                              salt_length=padding.PSS.DIGEST_LENGTH
                                          ), hashes.SHA256())
        headers = {
            "KALSHI-ACCESS-KEY": self.access_key,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode('utf-8'),
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }
        print("Created Kalshi access headers")
        return headers
    
    async def subscribe(self, ws, market_ticker, market_name):
        self.ticker_map[market_ticker] = market_name
        subscribe_message = {                    
            "id": self.write_seq_id,
            "cmd": "subscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_ticker": market_ticker}
        }
        await ws.send(json.dumps(subscribe_message))
        self.write_seq_id += 1

    
    async def check_sequence_id(self, seq_id):
        if seq_id != self.read_seq_id:
            print('u fuqd up lol')
        else:
            self.read_seq_id += 1

    # TODO: LOTS OF ERROR HANDLING
    async def handle_message(self, message):

        data = json.loads(message)
        msg_type = data.get('type')
        msg = data.get('msg', {})

        if msg_type == "subscribed":
            print(f"Subscribed: {data}")

        elif msg_type == "orderbook_snapshot":
            print(f"Kalshi orderbook snapshot recieved, seq: {self.read_seq_id}")
            await self.check_sequence_id(data.get('seq', int))
            key = f"kalshi:{self.ticker_map[msg['market_ticker']]}"
            orderbook = Orderbook(yes_asks={}, no_asks={})
            orderbook.apply_kalshi_snapshot(msg)
            serialized = orderbook.to_redis()
            await self.r.set(key, serialized)
            await self.r.publish(key, serialized)

        elif msg_type == "orderbook_delta":
            print(f"Kalshi orderbook update for {msg['market_ticker']}, seq: {self.read_seq_id}")
            await self.check_sequence_id(data.get('seq', int))
            key = f"kalshi:{self.ticker_map[msg['market_ticker']]}"
            raw = await self.r.get(key)
            if raw:
                orderbook = Orderbook.from_redis(json.loads(raw))
                orderbook.apply_kalshi_delta(msg)
                serialized = orderbook.to_redis()
                await self.r.set(key, serialized)
                await self.r.publish(key, serialized)

        elif msg_type == "error":
            print(f"Recieved error msg: {data}")

        else:
            print(f"Received [{msg_type}]: {data}")
