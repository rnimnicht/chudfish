import asyncio
import os
import json

import uvloop
import requests
from datetime import datetime, timezone

from fastlogging import LogInit
from pymongo import MongoClient
import redis.asyncio as redis

from kalshi_listener import KalshiListener
from polymarket_listener import PolymarketListener
from shared.models.matched_market import Matched_Market
from shared.models.kalshisubscription import KalshiSubscription
from shared.models.polymarketsubscription import PolymarketSubscription

logger = LogInit(domain=__name__, console=True, level=10)

r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)
mongo_client = MongoClient(os.environ.get('MONGODB_URI'))


# the way i wrote this is super gross!!!
# but whatever it works and kinda makes sense i guess
def check_active_kalshi(uri):
    resp = requests.get(f'https://api.elections.kalshi.com/trade-api/v2/markets/{uri}', timeout=5).json()['market']['status'] == 'active'
    if not resp:
        logger.warning(f"Kalshi normal subscription {uri} failed active check")
    return resp


def check_active_polymarket(uri):
    resp = requests.get(f'https://gamma-api.polymarket.com/markets/{uri}', timeout=5).json()
    if not (resp['active'] and not resp['closed']):
        logger.warning(f"Polymarket normal subscription {uri} failed active check")
    return resp['active'] and not resp['closed']


def check_active_recurring_kalshi(uri):
    params = {'series_ticker': uri, 'status': 'open'}
    resp = requests.get(f'https://api.elections.kalshi.com/trade-api/v2/markets', params=params, timeout=5).json()
    now = datetime.now(timezone.utc)

    for market in resp['markets']:
        open_time = datetime.fromisoformat(market['open_time'].replace('Z', '+00:00'))
        close_time = datetime.fromisoformat(market['close_time'].replace('Z', '+00:00'))
        if open_time <= now <= close_time:
            return market['ticker']
    
    return None


def check_active_recurring_polymarket(uri):
    response = requests.get(
        "https://gamma-api.polymarket.com/events",
        params={"series_id": uri, "active": "true", "closed": "false", "start_date_max": datetime.now(timezone.utc).isoformat()}, timeout=5
    )
    events = response.json()
    for event in events:
        for market in event.get("markets", []):
            if market.get("active") and not market.get("closed"):
                return json.loads(market["clobTokenIds"])
    return None


async def sub_manager(polymarket_queue, kalshi_queue):

    while True:

        logger.info('------ refreshing subscriptions :) ------')

        subscribed_polymarket = {}
        subscribed_kalshi = {}

        binary_markets = [Matched_Market.from_mongo(obj) for obj in mongo_client.markets.matched_markets.find()]
        for market in binary_markets:
            for platform in market.markets:
                if not platform.on:
                    continue
                if platform.platform_name == 'kalshi' and check_active_kalshi(platform.uri): 
                    subscribed_kalshi[platform.uri] = KalshiSubscription(market_name=market.name, market_ticker=platform.uri)
                elif platform.platform_name == 'polymarket' and check_active_polymarket(platform.uri):
                    tids = json.loads(requests.get(f'https://gamma-api.polymarket.com/markets/{platform.uri}').json()['clobTokenIds'])
                    subscribed_polymarket[tids[0]] = PolymarketSubscription(market_name=market.name, market_ticker=tids[0], reverse=market.reverse)
                    subscribed_polymarket[tids[1]] = PolymarketSubscription(market_name=market.name, market_ticker=tids[1], reverse=market.reverse)

        recurring_markets = [Matched_Market.from_mongo(obj) for obj in mongo_client.markets.recurring_markets.find()]
        for market in recurring_markets:
            for platform in market.markets:
                if not platform.on:
                    continue
                if platform.platform_name == 'kalshi' and (uri := check_active_recurring_kalshi(platform.uri)): 
                    subscribed_kalshi[uri] = KalshiSubscription(market_name=market.name, market_ticker=uri)
                elif platform.platform_name == 'polymarket' and (tids := check_active_recurring_polymarket(platform.uri)): 
                    subscribed_polymarket[tids[0]] = PolymarketSubscription(market_name=market.name, market_ticker=tids[0], reverse=market.reverse)
                    subscribed_polymarket[tids[1]] = PolymarketSubscription(market_name=market.name, market_ticker=tids[1], reverse=market.reverse)
        
        await polymarket_queue.put(subscribed_polymarket)
        await kalshi_queue.put(subscribed_kalshi)

        await asyncio.sleep(60)

                

async def main():
    polymarket_listener = PolymarketListener(r)
    kalshi_listener = KalshiListener(r)
    polymarket_queue = asyncio.Queue()
    kalshi_queue = asyncio.Queue()
    await asyncio.gather(
        sub_manager(polymarket_queue, kalshi_queue), 
        (polymarket_listener.run(polymarket_queue)), 
        (kalshi_listener.run(kalshi_queue))
    )


if __name__ == '__main__':
    logger.info("Booting up listeners")
    uvloop.run(main())
    