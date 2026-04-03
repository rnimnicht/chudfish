import json

from fastlogging import LogInit

from listeners.base_listener import BaseListener
from shared.utils import get_kalshi_headers
from shared.constants import KALSHI_WS_URI

logger = LogInit(domain=__name__, console=True, level=10)

class KalshiUserListener(BaseListener):

    def __init__(self, r):

        super().__init__(KALSHI_WS_URI, r)

        self.read_seq_id = 1
        self.headers = get_kalshi_headers("GET", "/trade-api/ws/v2")

    # We should maybe put a restart here if we lose our sequence place
    async def check_read_sequence_id(self, seq_id):
        if seq_id != self.read_seq_id:
            logger.error(f"Sequence ID mismatch: expected {self.read_seq_id}, got {seq_id}")
        else:
            self.read_seq_id += 1

    async def handle_message(self, message):

        data = json.loads(message)
        msg_type = data.get('type')
        msg = data.get('msg', {})

        if msg_type == "fill":
            logger.info(f"Order filled: {msg}")
        else:
            logger.debug(f"Received Kalshi user msg {msg_type}: {data}")
            return

        await self.check_read_sequence_id(data.get('seq'))
