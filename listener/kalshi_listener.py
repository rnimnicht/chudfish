import os
import json
import time
import base64
import websocket
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from shared.listener import Listener

class KalshiListener(Listener):

    def __init__(self, r, market_name: str, kalshi_ticker: str):

        super().__init__(os.environ.get('KALSHI_WS_URI'), r, 'kalshi', market_name)

        # Kalshi auth setup
        pem = os.environ.get('KALSHI_PRIVATE_KEY', '').replace('\\n', '\n')
        self.private_key = serialization.load_pem_private_key(pem.encode(), password=None)
        self.access_key = os.environ.get('KALSHI_ACCESS_KEY')

        self.kalshi_ticker = kalshi_ticker
        self.read_seq_id = 1
        self.write_seq_id = 1

    def get_headers(self):
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
    
    def check_sequence_id(self, seq_id):
        if  seq_id != self.read_seq_id:
            print('u fuqd up lol')
        else:
            self.read_seq_id += 1

    # TODO: LOTS OF ERROR HANDLING
    def on_message(self, ws, message):
        data = json.loads(message)
        msg_type = data.get('type')
        msg = data.get('msg', {})
        print('msg rec: ', data)

        # TODO: figure out how to restart if this happens

        if msg_type == "subscribed":
            print(f"Subscribed: {data}")

        elif msg_type == "orderbook_snapshot":
            print(f"Orderbook snapshot recieved, seq: {self.read_seq_id}")
            self.check_sequence_id(data.get('seq', int))
            self.orderbook.yes_asks = {float(ask[0]):float(ask[1]) for ask in msg['yes_dollars_fp']}
            self.orderbook.no_asks = {float(ask[0]):float(ask[1]) for ask in msg['no_dollars_fp']}
            self.write_orderbook()
        
        elif msg_type == "orderbook_delta":
            print(f"Orderbook update for {self.kalshi_ticker}, seq: {self.read_seq_id}")
            print(data)
            self.check_sequence_id(data.get('seq', int))
            side = self.orderbook.yes_asks if msg['side'] == 'yes' else self.orderbook.no_asks
            side[float(msg['price_dollars'])] += float(msg['delta_fp'])
            self.write_orderbook()

        elif msg_type == "error":
            print(f"Recieved error msg: {data}")

        else:
            print(f"Received [{msg_type}]: {data}")

    def on_error(self, ws, error):
        print(f"Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print(f"Connection closed: {close_status_code} {close_msg}")

    def on_open(self, ws):
        print(f"Kalshi WebSocket connection opened for {self.market_name}, ticker {self.kalshi_ticker}; attempting to subscribe")
        subscribe_message = {
            "id": self.write_seq_id,
            "cmd": "subscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_ticker": self.kalshi_ticker
            }
        }
        ws.send(json.dumps(subscribe_message))
        self.write_seq_id += 1

    def on_ping(self, ws, message):
        print(f"Received ping: {message}")
        ws.send(message, websocket.ABNF.OPCODE_PONG)

