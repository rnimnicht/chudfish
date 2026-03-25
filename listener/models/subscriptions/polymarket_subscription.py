import json

from models.subscriptions.base_subscription import BaseSubscription

class PolymarketSubscription(BaseSubscription):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.key = f"polymarket:{self.market_name}"
    
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
    
    def get_unsubscribe_message(self, write_seq_id):
        unsubscribe_message = {
            "operation": "unsubscribe",
            "assets_ids": [self.market_ticker]
        }
        return json.dumps(unsubscribe_message)