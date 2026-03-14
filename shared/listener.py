from abc import ABC, abstractmethod
import websocket
from shared.models import Orderbook

class Listener(ABC):

    def __init__(self, uri, r, platform_name, market_name):
        self.uri = uri
        self.r = r
        self.market_name = market_name
        self.r_key = f"{platform_name}:{market_name}"
        self.orderbook = Orderbook(yes_asks={}, no_asks={})

    @abstractmethod
    def get_headers(self):
        return {}

    @abstractmethod
    def on_message(self, ws, message):
        pass

    @abstractmethod
    def on_error(self, ws, error):
        pass

    @abstractmethod
    def on_close(self, ws, close_status_code, close_msg):
        pass

    @abstractmethod
    def on_open(self, ws):
        pass

    @abstractmethod
    def on_ping(self, ws, message):
        pass

    def write_orderbook(self):
        self.r.set(self.r_key, self.orderbook.to_redis())

    def run(self):
        websocket.enableTrace(True)
        ws = websocket.WebSocketApp(self.uri,
                                    header=self.get_headers(),
                                    on_message=self.on_message,
                                    on_error=self.on_error,
                                    on_close=self.on_close,
                                    on_open=self.on_open,
                                    on_ping=self.on_ping)
        ws.run_forever()
