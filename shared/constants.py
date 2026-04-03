from enum import Enum

class MarketType(Enum):
    LONGSTANDING = "LONGSTANDING"
    CRYPTO_15_MIN = "CRYPTO_15_MIN"

class PlatformName(Enum):
    KALSHI = "KALSHI"
    POLYMARKET = "POLYMARKET"

kalshi_crypto_fee = lambda x : (x * 0.07 * (1.0-x)) + x
poly_crypto_fee = lambda x: (x * 0.25 * ((x * (1.0-x) )**2)) + x

KALSHI_TRADE_WS_URI = "wss://api.elections.kalshi.com/trade-api/ws/v2"
KALSHI_USER_WS_URI = "wss://api.elections.kalshi.com/trade-api/ws/v2"