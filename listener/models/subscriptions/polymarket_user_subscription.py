import json

from models.subscriptions.base_subscription import BaseSubscription
from shared.utils import get_polymarket_client

class PolymarketUserSubscription(BaseSubscription):

    def __init__(self, **kwargs):
        super().__init__(market_name="", market_ticker="", **kwargs)
        self.key = f"polymarket:user"
    
    def get_subscribe_message(self, write_seq_id):

        pm_client = get_polymarket_client()

        return json.dumps(
            {
                "auth": {
                    "apiKey": pm_client.creds.api_key,
                    "secret": pm_client.creds.api_secret,
                    "passphrase": pm_client.creds.api_passphrase
                },
                "type": "user",
            }
        )
                
    def get_unsubscribe_message(self, write_seq_id):
        return json.dumps({})