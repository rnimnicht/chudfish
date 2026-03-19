import base64
import json
import os
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from fastlogging import LogInit

from shared.listener import Listener
from shared.models import Orderbook

logger = LogInit(domain=__name__, console=True, level=10)

class KalshiListener(Listener):

    def __init__(self, r):

        super().__init__(os.environ.get('KALSHI_WS_URI'), r, 'kalshi')

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
        logger.debug("Created Kalshi access headers")
        return headers
    
    async def subscribe(self, ws, market_ticker, market_name, reverse=False):
        self.ticker_map[market_ticker] = market_name

        if self.write_seq_id == 1:
            subscribe_message = {                    
                "id": self.write_seq_id,
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta"],
                    "market_ticker": market_ticker}
            }
        else:
            subscribe_message = {
                "id": self.write_seq_id,
                "cmd": "update_subscription",
                "params": {
                    "sid": 1,
                    "market_ticker": market_ticker,
                    "action": "add_markets"
                }
            }
        logger.debug(f"KALSHI SUBSCRIPTION:{subscribe_message} ")
        await ws.send(json.dumps(subscribe_message))
        self.write_seq_id += 1

    # We should maybe put a restart here if we lose our sequence place
    async def check_sequence_id(self, seq_id):
        if seq_id != self.read_seq_id:
            logger.error(f"Sequence ID mismatch: expected {self.read_seq_id}, got {seq_id}")
        else:
            self.read_seq_id += 1

    # TODO: LOTS OF ERROR HANDLING
    async def handle_message(self, message):

        data = json.loads(message)
        msg_type = data.get('type')
        msg = data.get('msg', {})

        if msg_type == "subscribed":
            logger.info(f"Kalshi subscribed: {data}")

        elif msg_type == "orderbook_snapshot":
            logger.debug(f"Kalshi orderbook snapshot received, seq: {self.read_seq_id}")
            await self.check_sequence_id(data.get('seq', int))
            key = f"kalshi:{self.ticker_map[msg['market_ticker']]}"
            orderbook = Orderbook(yes_asks={}, no_asks={})
            orderbook.apply_kalshi_snapshot(msg)
            serialized = orderbook.to_redis()
            await self.r.set(key, serialized)
            await self.r.publish(key, serialized)

        elif msg_type == "orderbook_delta":
            logger.debug(f"Kalshi orderbook update for {msg['market_ticker']}, seq: {self.read_seq_id}")
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
            logger.error(f"Received error msg: {data}")

        else:
            logger.debug(f"Received {msg_type}: {data}")
