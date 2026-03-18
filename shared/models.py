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

    @classmethod
    def from_polymarket_raw_orderbook(cls, snapshot):
        return cls(
            yes_asks={float(ask['price']): float(ask['size']) for ask in snapshot['bids']},
            no_asks={}
        )


    def to_redis(self):
        return self.model_dump_json()
    
    @classmethod
    def from_redis(cls, doc: dict):
        return cls(**doc)

