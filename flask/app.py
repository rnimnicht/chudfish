import os
import redis
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
r = redis.Redis(host=os.environ.get('REDIS_HOST', 'redis'), port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)

@app.route("/")
def hello_world():
    data = r.get("btcusdt")
    return data if data is not None else "No data found for key 'btcusdt'"
