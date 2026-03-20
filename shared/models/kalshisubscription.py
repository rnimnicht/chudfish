import json

class KalshiSubscription():
    
    def __init__(self, market_name, market_ticker, reverse=False):
        self.market_name = market_name
        self.market_ticker = market_ticker
        self.sid = -1
        self.reverse = reverse
        self.key = f"kalshi:{market_name}"

    def get_subscribe_message(self, write_seq_id):
        if write_seq_id == 1:
            subscribe_message = {                    
                "id": write_seq_id,
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta"],
                    "market_ticker": self.market_ticker
                }
            }
        else:
            subscribe_message = {
                "id": write_seq_id,
                "cmd": "update_subscription",
                "params": {
                    "sid": 1,
                    "market_ticker": self.market_ticker,
                    "action": "add_markets"
                }
            }
        return json.dumps(subscribe_message)
    
    def get_unsubscribe_message(self, write_seq_id):
        unsubscribe_message = {
            "id": write_seq_id,
            "cmd": "update_subscription",
            "params": {
                "sids": [self.sid],
            }
        }
        return json.dumps(unsubscribe_message)
