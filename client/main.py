import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
import redis
import redis.asyncio as aioredis

from shared.models import Matched_Market, Orderbook, Platform

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)
ar = aioredis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)
mongo_client = MongoClient(os.environ.get('MONGODB_URI'))


@app.get("/")
def dashboard():
    return FileResponse("static/index.html")

@app.get("/redis/{object_name}")
def ticker(object_name: str):
    data = r.get(object_name)
    return data if data is not None else "{}"


@app.get("/matched_market")
def get_market(market: str = Query(...)):
    print(market)
    ret = Matched_Market.from_mongo(mongo_client.markets.matched_markets.find_one({"name": market}))
    return ret

@app.post("/matched_market", status_code=201)
def add_market(market: Matched_Market):
    mongo_client.markets.matched_markets.insert_one(market.to_mongo())
    return {"message": "Market added"}


@app.put("/matched_market")
def update_market(market: str = Query(...), updates: dict = {}):
    result = mongo_client.markets.matched_markets.update_one({"name": market}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Market not found")
    return {"message": "Market updated"}


@app.delete("/matched_market")
def delete_market(market: str = Query(...)):
    result = mongo_client.markets.matched_markets.delete_one({"name": market})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Market not found")
    return {"message": "Market deleted"}


@app.get("/list_matched_markets")
def list_markets():
    markets = [Matched_Market.from_mongo(obj) for obj in mongo_client.markets.matched_markets.find()]
    return markets


@app.get("/orderbooks")
def list_orderbooks():
    matched_markets = list_markets()
    resp = {}
    for mm in matched_markets:
        resp[mm['name']] = {f"{m['market_name']}:{m['uri']}": r.get(f"{m['market_name']}:{m['uri']}") for m in mm['markets']}
    return resp


@app.get("/orderbooks/{market_name}")
def get_orderbook(market_name: str):
    mm = Matched_Market.from_mongo(mongo_client.markets.matched_markets.find_one({'name': market_name}))
    resp = {}
    for m in mm.markets:
        resp[m.platform_name] = r.get(f"{m.platform_name}:{mm.name}")

    return resp


@app.websocket("/ws/orderbooks/{market_name}")
async def orderbook_ws(websocket: WebSocket, market_name: str):
    await websocket.accept()
    channels = [f"kalshi:{market_name}", f"polymarket:{market_name}"]
    pubsub = ar.pubsub()
    await pubsub.subscribe(*channels)
    try:
        # Send current snapshot immediately on connect
        snapshot = {ch: r.get(ch) for ch in channels if r.get(ch)}
        if snapshot:
            await websocket.send_json({"type": "snapshot", "data": snapshot})

        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_json({
                    "type": "update",
                    "channel": message["channel"],
                    "data": message["data"],
                })
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
