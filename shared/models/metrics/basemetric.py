import time

from abc import ABC, abstractmethod
from pydantic import BaseModel

class BaseMetric(BaseModel):

    execution_time: float
    expected_return: float
    market: str
    timestamp: str