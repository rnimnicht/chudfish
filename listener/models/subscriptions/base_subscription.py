import json
from typing import Optional

from abc import ABC, abstractmethod
from pydantic import BaseModel


class BaseSubscription(BaseModel, ABC):
    market_name: str
    market_ticker: str
    reverse: Optional[bool] = False
    key: Optional[str] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @abstractmethod
    def get_subscribe_message(self, write_seq_id):
        return json.dumps({})

    @abstractmethod
    def get_unsubscribe_message(self, write_seq_id):
        return json.dumps({})
    
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (
            self.market_name == other.market_name
            and self.market_ticker == other.market_ticker
            and self.reverse == other.reverse
        )

    def __hash__(self):
        return hash((self.market_name, self.market_ticker, self.reverse))
