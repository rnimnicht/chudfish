import redis
from dotenv import load_dotenv
from kalshi_listener import KalshiListener
import os


r = redis.Redis(host='redis', port=int(os.environ.get('REDIS_PORT', 6379)), decode_responses=True)
load_dotenv()

if __name__ == '__main__':
    
    # read data from mongo db
    # start a listener for each entry w/ each market
    # um swag out?

    kalshi_listener = KalshiListener(r, 'govshutdownlength', 'KXRECSSNBER-26')
    kalshi_listener.run()
