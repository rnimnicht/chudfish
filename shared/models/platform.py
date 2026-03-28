from pydantic import BaseModel
from shared.constants import PlatformName
from typing import Optional


class Platform(BaseModel):

    # we should move "reverse" field into here,
    # duplicate market_name field here,
    # andddd also consolidate with "Subscription" model maybe?
    # though maybe not because polymarket has two subscriptions for each id
    platform_name: PlatformName
    uri: str
    on: bool = False
    reverse: Optional[bool] = False

    def to_mongo(self):
        return self.model_dump()

    @classmethod
    def from_mongo(cls, doc: dict):
        return cls(**doc)
