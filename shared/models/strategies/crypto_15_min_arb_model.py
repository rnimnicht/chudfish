from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field

from shared.constants import MarketType


class Crypto15MinArbTrader(BaseModel):
    id: Optional[str] = Field(None, alias='_id')

    marketname: str
    type: MarketType

    max_arb_percentage: float
    min_arb_percentage: float
    danger_arb_percentage: float
    max_vol_per_trade: int
    min_required_liquidity: int
    seconds_timeout: int

    on: bool

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}

    def to_mongo(self):
        data = self.model_dump(exclude={"id"}, mode="json")
        return data

    @classmethod
    def from_mongo(cls, doc: dict):
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return cls(**doc)
    
