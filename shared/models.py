from typing import Optional, List
from bson import ObjectId
from pydantic import BaseModel, Field


class Market(BaseModel):
    market_name: str
    uri: str

    def to_mongo(self):
        return self.model_dump()

    @classmethod
    def from_mongo(cls, doc: dict):
        return cls(**doc)


class Matched_Market(BaseModel):
    id: Optional[str] = Field(None, alias='_id')
    name: str
    markets: List[Market]

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
