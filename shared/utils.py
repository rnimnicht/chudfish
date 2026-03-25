import base64
import json
import os
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from py_clob_client.client import ClobClient
from kalshi_python_sync import Configuration, KalshiClient

def get_kalshi_headers(http_method, path):
    pem = os.environ.get('KALSHI_PRIVATE_KEY', '').replace('\\n', '\n')
    private_key = serialization.load_pem_private_key(pem.encode(), password=None)
    access_key = os.environ.get('KALSHI_ACCESS_KEY')
    timestamp = str(int(time.time() * 1000))
            
    msg = (timestamp + http_method + path).encode('utf-8')
    signature = private_key.sign(msg,
                                        padding.PSS(
                                        mgf=padding.MGF1(hashes.SHA256()),
                                        salt_length=padding.PSS.DIGEST_LENGTH
    ), hashes.SHA256())
    headers = {
        "KALSHI-ACCESS-KEY": access_key,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode('utf-8'),
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
    }
    return headers

def get_polymarket_client():
    temp_client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        key=os.environ.get("POLYMARKET_PRIVATE_KEY"))
    api_creds = temp_client.create_or_derive_api_creds()

    return ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        key=os.environ.get("POLYMARKET_PRIVATE_KEY"),
        creds=api_creds,
        signature_type=1,
        funder=os.environ.get("FUNDER_ADDRESS")
    )

def get_kalshi_client():
    config = Configuration(
        host="https://api.elections.kalshi.com/trade-api/v2",
    )
    config.api_key_id = os.environ.get("KALSHI_ACCESS_KEY")
    config.private_key_pem = os.environ.get("KALSHI_PRIVATE_KEY", '').replace('\\n', '\n')

    return KalshiClient(config)
