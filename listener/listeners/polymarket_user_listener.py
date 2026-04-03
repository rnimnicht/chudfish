import json

from fastlogging import LogInit

from listeners.base_listener import BaseListener
from shared.models import Orderbook
from shared.constants import POLYMARKET_USER_WS_URI
from shared.utils import get_polymarket_client

logger = LogInit(domain=__name__, console=True, level=10)

class PolymarketUserListener(BaseListener):

    def __init__(self, r):
        super().__init__(POLYMARKET_USER_WS_URI, r)
        
    # TODO: LOTS OF ERROR HANDLING
    async def handle_message(self, message):

        data = json.loads(message)

        # Some Polymarket wss responses are in lists, some aren't
        if isinstance(data, dict):
            data = [data]

        logger.info(f"Polymarket user channel msg: {data}")
