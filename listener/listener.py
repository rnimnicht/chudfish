import os
import websocket
import json
import redis
from dotenv import load_dotenv

load_dotenv()

r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)

def on_message(ws, message):
    data = json.loads(message)
    print(f"Received message: {data}")
    # you can pipeline this data to your function, analysis or backtesting
    f_data = f"Symbol: {data['s']}, Price: {data['c']}, Time: {data['E']}"
    r.set('btcusdt', f_data)

def on_error(ws, error):
    print(f"error: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"closed")

def on_open(ws):
    print("WebSocket connection opened")
    subscribe_message = {
        "method": "SUBSCRIBE",
        "params": ["btcusdt@ticker"],
        "id": 1
    }
    ws.send(json.dumps(subscribe_message))

def on_ping(ws, message):
    print(f"Received ping: {message}")
    ws.send(message, websocket.ABNF.OPCODE_PONG)
    print(f"Sent pong: {message}")


async def main():
    url = os.environ.get('BINANCE_WS_URL', 'wss://stream.binance.us:9443/ws') + '/btcusdt@trade'
    
    async with websocket.connect(url) as ws:
        while True:
            data = json.loads(await ws.recv())
            print(f"Price: {data['p']} Quantity: {data['q']}")

if __name__ == "__main__":
    websocket.enableTrace(True)
    socket = os.environ.get('BINANCE_WS_URL', 'wss://stream.binance.us:9443/ws')
    ws = websocket.WebSocketApp(socket,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close,
                                on_open=on_open,
                                on_ping=on_ping)
    ws.run_forever()

