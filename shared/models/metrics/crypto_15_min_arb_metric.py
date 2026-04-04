from datetime import datetime, timezone

from shared.models.metrics.basemetric import BaseMetric
from shared.constants import poly_crypto_fee, kalshi_crypto_fee
from typing import Optional

class Crypto15MinArbMetric(BaseMetric):

    polymarket_request_response_time: Optional[float] = None
    kalshi_request_response_time: Optional[float] = None
    total_execution_time: Optional[float] = None
    side: Optional[str] = None
    eff_kalshi_yes_price: Optional[float] = None
    eff_kalshi_no_price: Optional[float] = None
    eff_poly_yes_price: Optional[float] = None
    eff_poly_no_price: Optional[float] = None
    kalshi_yes_price: Optional[float] = None
    kalshi_no_price: Optional[float] = None
    poly_yes_price: Optional[float] = None
    poly_no_price: Optional[float] = None
    volume: Optional[int] = None
    eff_combined_price: Optional[float] = None
    kalshi_filled: Optional[float] = None
    poly_filled: Optional[float] = None

    def __init__(self, kalshi_resp, poly_resp, kalshi_side, market: str, kalshi_price: float, poly_price: float, volume: int, **kwargs):
        eff_kalshi = kalshi_crypto_fee(kalshi_price)
        eff_poly = poly_crypto_fee(poly_price)
        eff_combined = eff_kalshi + eff_poly

        try:
            kalshi_filled = float(kalshi_resp['order']['fill_count_fp'])
        except Exception:
            kalshi_filled = 0.0

        poly_filled = float(volume) if not isinstance(poly_resp, Exception) else 0.0

        super().__init__(
            market=market,
            timestamp=str(datetime.now(timezone.utc)),
            execution_time=0.0,
            expected_return=(1.0 - eff_combined) * volume,
            side='kalshi_yes_poly_no' if kalshi_side == 'yes' else 'kalshi_no_poly_yes',
            eff_combined_price=eff_combined,
            volume=volume,
            kalshi_filled=kalshi_filled,
            poly_filled=poly_filled,
            eff_kalshi_yes_price=eff_kalshi if kalshi_side == 'yes' else None,
            kalshi_yes_price=kalshi_price if kalshi_side == 'yes' else None,
            eff_poly_no_price=eff_poly if kalshi_side == 'yes' else None,
            poly_no_price=poly_price if kalshi_side == 'yes' else None,
            eff_kalshi_no_price=eff_kalshi if kalshi_side == 'no' else None,
            kalshi_no_price=kalshi_price if kalshi_side == 'no' else None,
            eff_poly_yes_price=eff_poly if kalshi_side == 'no' else None,
            poly_yes_price=poly_price if kalshi_side == 'no' else None,
            **kwargs
        )

    def populate(self):
        pass