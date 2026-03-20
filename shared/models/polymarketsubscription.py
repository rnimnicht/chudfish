import json

class PolymarketSubscription():
    
    def __init__(self, market_name, market_ticker, side):
        self.market_name = market_name
        self.market_ticker = market_ticker
        self.side = side
        self.key = f"polymarket:{market_name}"

    def get_subscribe_message(self, write_seq_id):
        if write_seq_id == 1:
            subscribe_message = {
                "assets_ids": [self.market_ticker],
                "type": "market",
                "initial_dump": True,
                "custom_feature_enabled": False
            }
        else:
            subscribe_message = {
                "operation": "subscribe",
                "assets_ids": [self.market_ticker],
            }
        return json.dumps(subscribe_message)
    
    def get_unsubscribe_message(self):
        unsubscribe_message = {
            "operation": "unsubscribe",
            "asset_ids": [self.market_ticker]
        }
        return json.dumps(unsubscribe_message)