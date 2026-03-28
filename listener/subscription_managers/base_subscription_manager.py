from abc import ABC, abstractmethod

class BaseSubscriptionManager(ABC):

    def __init__(self, **kwargs):
        self.mongo_client = kwargs['client']

    @abstractmethod
    async def run(self, *args, **kwargs):
        pass