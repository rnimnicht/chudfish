import os

import asyncio
from fastlogging import LogInit

from shared.models.strategies.crypto_15_min_arb_model import Crypto15MinArbTrader

logger = LogInit(domain=__name__, console=True, level=10)


class Crypto15MinArbStrategy:

    def __init__(self, options: Crypto15MinArbTrader):
        self.options = options

    async def run(self):
        while True:
            logger.info(f"Running {self.options.marketname}")
            await asyncio.sleep(20)

    