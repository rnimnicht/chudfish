from pydantic import BaseModel


class Platform(BaseModel):

    # we should move "reverse" field into here,
    # duplicate market_name field here,
    # andddd also rename to "Subscription"
    platform_name: str
    uri: str
    on: bool = False

    def to_mongo(self):
        return self.model_dump()

    @classmethod
    def from_mongo(cls, doc: dict):
        return cls(**doc)
