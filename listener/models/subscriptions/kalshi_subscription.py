import json
from typing import Optional, Annotated

from pydantic import BaseModel
from pydantic.functional_validators import SkipValidation

class KalshiSubscription(BaseModel):

    market_name: str
    market_ticker: str
    reverse: Optional[bool] = False
    key: Optional[str] = None
    sid: Annotated[int, SkipValidation] = -1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.key = f"kalshi:{self.market_name}"
 
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
                    "action": "add_markets",
                    "send_initial_snapshot": True
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
    
    def __eq__(self, other):
        if not isinstance(other, KalshiSubscription):
            return False
        return (
            self.market_name == other.market_name
            and self.market_ticker == other.market_ticker
            and self.reverse == other.reverse
        )

    def __hash__(self):
        return hash((self.market_name, self.market_ticker, self.reverse))
