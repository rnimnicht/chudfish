import os

import asyncio
import uvloop
from fastlogging import LogInit

from shared.models.strategies.crypto_15_min_arb_model import Crypto15MinArbTrader
from strategies.crypto_15_min_arb_strategy import Crypto15MinArbStrategy
from balancemanager import BalanceManager
from pymongo import MongoClient

mongo_client = MongoClient(os.environ.get('MONGODB_URI'))

active_strategy_tasks = {}

logger = LogInit(domain=__name__, console=True, level=10)

# every 30 seconds, query for strategies, then run diff
async def main():
    balance_manager = BalanceManager()
    balance_manager_task = asyncio.create_task(balance_manager.run())

    while True:
        logger.info("Refreshing strategies")
        active_strategies = {s.id : s for s in (Crypto15MinArbTrader.from_mongo(doc) for doc in mongo_client.markets.strategies.find({"on": True}))}

        # Stop non-active strategies
        to_unsub = []
        for s_id, strategy in active_strategy_tasks.items():
            if s_id not in active_strategies:
                logger.info("Stopping a task")
                to_unsub.append(s_id)
        for s_id in to_unsub:
            task = active_strategy_tasks[s_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del active_strategy_tasks[s_id]

        # Start active strategies (if they're not already started)
        for s_id, strategy in active_strategies.items():
            if s_id not in active_strategy_tasks:
                logger.info(f"Starting {strategy.marketname}")
                strat = Crypto15MinArbStrategy(strategy)
                task = asyncio.create_task(strat.run())
                active_strategy_tasks[s_id] = task

        await asyncio.sleep(30)

if __name__ == '__main__':
    logger.info("Starting strategy manager")
    uvloop.run(main())
