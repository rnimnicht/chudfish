import base64
import json
import os
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

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
