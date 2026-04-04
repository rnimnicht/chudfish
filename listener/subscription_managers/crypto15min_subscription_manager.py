import requests
import json

from datetime import datetime, timezone
from asyncio import Queue
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastlogging import LogInit

from models.subscriptions.kalshi_subscription import KalshiSubscription
from models.subscriptions.polymarket_subscription import PolymarketSubscription
from subscription_managers.base_subscription_manager import BaseSubscriptionManager
from shared.models.matched_market import Matched_Market
from shared.constants import MarketType, PlatformName

logger = LogInit(domain=f"{__name__}:crypto15min", console=True, level=10)

class Crypto15MinSubscriptionManager(BaseSubscriptionManager):

    def get_kalshi_ticker(self, series_id):
        params = {'series_ticker': series_id, 'status': 'open'}
        resp = requests.get(f'https://api.elections.kalshi.com/trade-api/v2/markets', params=params, timeout=5).json()
        now = datetime.now(timezone.utc)

        for market in resp['markets']:
            open_time = datetime.fromisoformat(market['open_time'].replace('Z', '+00:00'))
            close_time = datetime.fromisoformat(market['close_time'].replace('Z', '+00:00'))
            if open_time <= now <= close_time:
                return market['ticker']
    
        return None


    def get_polymarket_ticker(self, series_id):
        response = requests.get(
            "https://gamma-api.polymarket.com/events",
            params={"series_id": series_id, "active": "true", "closed": "false", "start_date_max": datetime.now(timezone.utc).isoformat()}, timeout=5
        )
        now = datetime.now(timezone.utc)
        events = response.json()
        for event in events:
            for market in event.get("markets", []):
                if market.get("active") and \
                    not market.get("closed") and \
                    datetime.fromisoformat(market.get("endDate")) > now and \
                    datetime.fromisoformat(market.get("acceptingOrdersTimestamp")) < now:
                    return json.loads(market["clobTokenIds"])

        return None
    
    async def refresh_subscriptions(self):

        logger.info("Refreshing crypto 15 min subscriptions")

        # check we're after first 30 seconds, within first 1 min of 15 minute window

        # query for our crypto 15 min markets
        kalshi_subscriptions = {}
        polymarket_subscriptions = {}
        markets = [Matched_Market.from_mongo(obj) for obj in self.mongo_client.markets.matched_markets.find({"type": MarketType.CRYPTO_15_MIN.value})]
        for market in markets:

            kalshi_sub = None
            polymarket_t0_sub = None
            polymarket_t1_sub = None

            for platform in market.markets:

                # filter out streams that we've turned off
                if not platform.on:
                    continue
                if platform.platform_name == PlatformName.KALSHI and (uri := self.get_kalshi_ticker(platform.uri)): 
                    kalshi_sub = KalshiSubscription(market_name=market.name, market_ticker=uri, reverse=platform.reverse)
                elif platform.platform_name == PlatformName.POLYMARKET and (tids := self.get_polymarket_ticker(platform.uri)): 
                    polymarket_t0_sub = PolymarketSubscription(market_name=market.name, market_ticker=tids[0], reverse=platform.reverse)
                    polymarket_t1_sub = PolymarketSubscription(market_name=market.name, market_ticker=tids[1], reverse=not platform.reverse)

            # TODO: make sure the pricings are close enough before sending
            # this also means we're only pushing if both streams are on btw
            if kalshi_sub and polymarket_t0_sub and polymarket_t1_sub:
                kalshi_subscriptions[kalshi_sub.market_ticker] = kalshi_sub
                polymarket_subscriptions[polymarket_t0_sub.market_ticker] = polymarket_t0_sub
                polymarket_subscriptions[polymarket_t1_sub.market_ticker] = polymarket_t1_sub

        await self.polymarket_queue.put(polymarket_subscriptions)
        await self.kalshi_queue.put(kalshi_subscriptions)


    async def run(self, kalshi_queue: Queue, polymarket_queue: Queue):

        logger.info("Starting crypto 15 min subscription manager")

        self.kalshi_queue = kalshi_queue
        self.polymarket_queue = polymarket_queue

        await self.refresh_subscriptions()

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            self.refresh_subscriptions,
            'cron',
            minute='1,16,31,46'
        )
        scheduler.start()
            