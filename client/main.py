import os
import redis
from fastapi import FastAPI, HTTPException, Query
from dotenv import load_dotenv
from pymongo import MongoClient
from shared.models import Market, Matched_Market, Orderbook

load_dotenv()

app = FastAPI()
r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)
mongo_client = MongoClient(os.environ.get('MONGODB_URI'))


@app.get("/")
def dashboard():
    return "CHUDFISH 0.0.1"

@app.get("/redis/{object_name}")
def ticker(object_name: str):
    data = r.get(object_name)
    return data if data is not None else "{}"

@app.get("/matched_market")
def get_market(market: str = Query(...)):
    print(market)
    ret = list(mongo_client.markets.matched_markets.find({"name": market}, {"_id": 0}))
    print(ret)
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
    markets = list(mongo_client.markets.matched_markets.find({}, {"_id": 0}))
    return markets

@app.get("/orderbooks")
def list_orderbooks():
    matched_markets = list_markets()
    resp = {}
    for mm in matched_markets:
        print(f"{m['market_name']}:{m['uri']}" for m in mm['markets'])
        resp[mm['name']] = {f"{m['market_name']}:{m['uri']}": r.get(f"{m['market_name']}:{m['uri']}") for m in mm['markets']}
    return resp

@app.get("/orderbooks/{market_name}")
def get_orderbook(market_name: str):
    matched_market = list(mongo_client.markets.matched_markets.find({'name': market_name}, {"_id": 0}))[0]
    ret = {}
    for m in matched_market['markets']:
        print(f"{m['market_name']}:{m['uri']}")
        ret[m['market_name']] = r.get(f"{m['market_name']}:{matched_market['name']}")

    return ret
