from typing import Optional, List, Dict
from bson import ObjectId
from pydantic import BaseModel, Field


class Platform(BaseModel):
    platform_name: str
    uri: str

    def to_mongo(self):
        return self.model_dump()

    @classmethod
    def from_mongo(cls, doc: dict):
        return cls(**doc)


class Matched_Market(BaseModel):
    id: Optional[str] = Field(None, alias='_id')
    name: str
    markets: List[Platform]

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}

    def to_mongo(self):
        data = self.model_dump(exclude={"id"})
        return data

    @classmethod
    def from_mongo(cls, doc: dict):
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return cls(**doc)


class Orderbook(BaseModel):
    yes_asks: Dict[float, float]
    no_asks: Dict[float, float]

    @classmethod
    def from_kalshi_raw_orderbook(cls, snapshot):
        return cls(
            yes_asks={float(ask[0]): float(ask[1]) for ask in snapshot['yes_dollars_fp']},
            no_asks={float(ask[0]): float(ask[1]) for ask in snapshot['no_dollars_fp']},
        )

    def apply_kalshi_snapshot(self, msg):
        self.yes_asks = {float(ask[0]): float(ask[1]) for ask in msg['yes_dollars_fp']}
        self.no_asks = {float(ask[0]): float(ask[1]) for ask in msg['no_dollars_fp']}

    def apply_kalshi_delta(self, msg):
        side = self.yes_asks if msg['side'] == 'yes' else self.no_asks
        price = float(msg['price_dollars'])
        side[price] = side.get(price, 0.0) + float(msg['delta_fp'])
        if side[price] <= 0:
            del side[price]

    @classmethod
    def from_polymarket_raw_orderbook(cls, snapshot):
        return cls(
            yes_asks={float(ask['price']): float(ask['size']) for ask in snapshot['bids']},
            no_asks={}
        )

    def apply_polymarket_book(self, msg, side: str):
        bids = {float(ask['price']): float(ask['size']) for ask in msg['bids']}
        if side == 'yes':
            self.yes_asks = bids
        else:
            self.no_asks = bids

    def apply_polymarket_price_change(self, price_change: dict, side: str):
        target = self.yes_asks if side == 'yes' else self.no_asks
        price = float(price_change['price'])
        size = float(price_change['size'])
        # TODO: double check this isn't a delta thing
        if size <= 0:
            target.pop(price, None)
        else:
            target[price] = size

    def to_redis(self):
        return self.model_dump_json()
    
    @classmethod
    def from_redis(cls, doc: dict):
        return cls(**doc)

