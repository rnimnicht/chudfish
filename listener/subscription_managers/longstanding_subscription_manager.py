import requests
import json

from asyncio import Queue
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastlogging import LogInit

from models.subscriptions.kalshi_subscription import KalshiSubscription
from models.subscriptions.polymarket_subscription import PolymarketSubscription
from subscription_managers.base_subscription_manager import BaseSubscriptionManager
from shared.models.matched_market import Matched_Market
from shared.constants import MarketType, PlatformName


logger = LogInit(domain=f"{__name__}:longstanding", console=True, level=10)

class LongstandingSubscriptionManager(BaseSubscriptionManager):

    def check_active_kalshi(self, uri):
        resp = requests.get(f'https://api.elections.kalshi.com/trade-api/v2/markets/{uri}', timeout=5).json()['market']['status'] == 'active'
        if not resp:
            logger.warning(f"Kalshi normal subscription {uri} failed active check")
        return resp


    def check_active_polymarket(self, uri):
        resp = requests.get(f'https://gamma-api.polymarket.com/markets/{uri}', timeout=5).json()
        if not (resp['active'] and not resp['closed']):
            logger.warning(f"Polymarket normal subscription {uri} failed active check")
        return resp['active'] and not resp['closed']
    
    async def refresh_subscriptions(self):
        

        logger.info("Refreshing longstanding subscriptions")

        # TODO: check ur error checking here
        markets = [Matched_Market.from_mongo(obj) for obj in self.mongo_client.markets.matched_markets.find({"type": MarketType.LONGSTANDING.value})]
        kalshi_subscriptions = {}
        polymarket_subscriptions = {}
        for market in markets:
            for platform in market.markets:
                if not platform.on:
                    continue
                if platform.platform_name == PlatformName.KALSHI and self.check_active_kalshi(platform.uri): 
                    kalshi_subscriptions[platform.uri] = KalshiSubscription(market_name=market.name, market_ticker=platform.uri)
                elif platform.platform_name == PlatformName.POLYMARKET and self.check_active_polymarket(platform.uri):
                    tids = json.loads(requests.get(f'https://gamma-api.polymarket.com/markets/{platform.uri}').json()['clobTokenIds'])
                    polymarket_subscriptions[tids[0]] = PolymarketSubscription(market_name=market.name, market_ticker=tids[0], reverse=platform.reverse)
                    polymarket_subscriptions[tids[1]] = PolymarketSubscription(market_name=market.name, market_ticker=tids[1], reverse=not platform.reverse)

        await self.polymarket_queue.put(polymarket_subscriptions)
        await self.kalshi_queue.put(kalshi_subscriptions)


    async def run(self, kalshi_queue: Queue, polymarket_queue: Queue):

        logger.info("Starting longstanding subscription manager")

        self.kalshi_queue = kalshi_queue
        self.polymarket_queue = polymarket_queue

        await self.refresh_subscriptions()

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            self.refresh_subscriptions,
            'cron',
            minute='0,15,30,45',
            second=20
        )
        scheduler.start()
            