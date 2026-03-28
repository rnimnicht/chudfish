import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
import redis
import redis.asyncio as aioredis

from shared.models.matched_market import Matched_Market
from shared.models.strategies.crypto_15_min_arb_model import Crypto15MinArbTrader

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


# ── Matched Market CRUD ──

@app.get("/matched_market")
def get_market(market: str = Query(...)):
    doc = mongo_client.markets.matched_markets.find_one({"name": market})
    if not doc:
        raise HTTPException(status_code=404, detail="Market not found")
    return Matched_Market.from_mongo(doc)


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


# ── Crypto15MinArbTrader CRUD ──

@app.get("/arb_trader")
def get_arb_trader(marketname: str = Query(...)):
    doc = mongo_client.markets.strategies.find_one({"marketname": marketname})
    if not doc:
        raise HTTPException(status_code=404, detail="Arb trader not found")
    return Crypto15MinArbTrader.from_mongo(doc)


@app.post("/arb_trader", status_code=201)
def add_arb_trader(trader: Crypto15MinArbTrader):
    mongo_client.markets.strategies.insert_one(trader.to_mongo())
    return {"message": "Arb trader added"}


@app.put("/arb_trader")
def update_arb_trader(marketname: str = Query(...), updates: dict = {}):
    result = mongo_client.markets.strategies.update_one({"marketname": marketname}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Arb trader not found")
    return {"message": "Arb trader updated"}


@app.delete("/arb_trader")
def delete_arb_trader(marketname: str = Query(...)):
    result = mongo_client.markets.strategies.delete_one({"marketname": marketname})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Arb trader not found")
    return {"message": "Arb trader deleted"}


@app.get("/list_arb_traders")
def list_arb_traders():
    traders = [Crypto15MinArbTrader.from_mongo(doc) for doc in mongo_client.markets.strategies.find()]
    return traders


# ── WebSocket ──

@app.websocket("/ws/orderbooks/{market_name}")
async def orderbook_ws(websocket: WebSocket, market_name: str):
    await websocket.accept()
    channels = [f"kalshi:{market_name}", f"polymarket:{market_name}"]
    pubsub = ar.pubsub()
    await pubsub.subscribe(*channels)
    try:
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
