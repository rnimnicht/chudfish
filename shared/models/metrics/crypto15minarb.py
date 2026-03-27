from shared.models.metrics.basemetric import BaseMetric
from typing import Optional

class Crypto15MinArbMetric(BaseMetric):

    polymarket_request_response_time: float
    kalshi_request_response_time: float
    side: str
    eff_kalshi_yes_price: Optional[float]
    eff_kalshi_no_price: Optional[float]
    eff_poly_yes_price: Optional[float]
    eff_poly_no_price: Optional[float]
    kalshi_yes_price: Optional[float]
    kalshi_no_price: Optional[float]
    poly_yes_price: Optional[float]
    poly_no_price: Optional[float]
    volume: int
    eff_combined_price: float
    kalshi_filled: float
    poly_filled: float 

