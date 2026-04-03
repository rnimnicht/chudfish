import json

from models.subscriptions.base_subscription import BaseSubscription

class KalshiFillSubscription(BaseSubscription):

    def __init__(self, **kwargs):
        super().__init__(market_name="", market_ticker="", **kwargs)
        self.key = "kalshi:user"
 
    def get_subscribe_message(self, write_seq_id):

        return json.dumps({
            "id": write_seq_id,
            "cmd": "subscribe",
            "params": {
                "channels": ["fill"]
            }
        })
   
    def get_unsubscribe_message(self, write_seq_id):
        return json.dumps({})
            