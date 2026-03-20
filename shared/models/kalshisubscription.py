import json
from typing import Optional

from pydantic import BaseModel

class KalshiSubscription(BaseModel):

    market_name: str
    market_ticker: str
    reverse: Optional[bool] = False
    key: Optional[str] = None
    sid: int = -1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.key = f"polymarket:{self.market_name}"
 
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
