import os
import redis
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from pymongo import MongoClient
from shared.models import Market, Matched_Market

load_dotenv()

app = Flask(__name__)
r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)
mongo_client = MongoClient(os.environ.get('MONGODB_URI'))


@app.route("/")
def dashboard():
    return "CHUDFISH 0.0.1"

@app.route("/ticker")
def ticker():
    data = r.get("btcusdt")
    return data if data is not None else "{}"

@app.route("/matched_market", methods=["GET"])
def get_market():
    market_name = request.args.get("market")
    print(market_name)
    ret = list(mongo_client.markets.matched_markets.find({"name": market_name}, {"_id": 0}))
    print(ret)
    return jsonify(ret)

@app.route("/matched_market", methods=["POST"])
def add_market():
    market = Matched_Market(**request.json)
    mongo_client.markets.matched_markets.insert_one(market.to_mongo())
    return jsonify({"message": "Market added"}), 201

@app.route("/matched_market", methods=["PUT"])
def update_market():
    market_name = request.args.get("market")
    updates = request.json
    result = mongo_client.markets.matched_markets.update_one({"name": market_name}, {"$set": updates})
    if result.matched_count == 0:
        return jsonify({"error": "Market not found"}), 404
    return jsonify({"message": "Market updated"})

@app.route("/matched_market", methods=["DELETE"])
def delete_market():
    market_name = request.args.get("market")
    result = mongo_client.markets.matched_markets.delete_one({"name": market_name})
    if result.deleted_count == 0:
        return jsonify({"error": "Market not found"}), 404
    return jsonify({"message": "Market deleted"})

@app.route("/list_matched_markets", methods=["GET"])
def list_markets():
    markets = list(mongo_client.markets.matched_markets.find({}, {"_id": 0}))
    return jsonify(markets)
