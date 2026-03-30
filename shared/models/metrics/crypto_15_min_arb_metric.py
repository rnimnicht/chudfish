from shared.models.metrics.basemetric import BaseMetric
from shared.constants import poly_crypto_fee, kalshi_crypto_fee
from typing import Optional

class Crypto15MinArbMetric(BaseMetric):

    polymarket_request_response_time: float
    kalshi_request_response_time: float
    total_execution_time: float
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

    def __init__(self, kalshi_resp, poly_resp, kalshi_side, **kwargs):
        super().__init__(kwargs)

        self.kalshi_resp = kalshi_resp
        self.poly_resp = poly_resp
        self.side = 'kalshi_yes_poly_no' if kalshi_side == 'yes' else 'kalshi_no_poly_yes'

        # if kalshi_side == 'yes':
        #     self.side = 'kalshi_yes_poly_no'
        #     self.eff_kalshi_yes_price = kalshi_crypto_fee(kalshi_price)
        #     self.kalshi_yes_price = kalshi_price
        #     self.eff_poly_no_price = poly_crypto_fee(poly_price)
        #     self.poly_no_price = poly_price
        # elif kalshi_side == 'no':
        #     self.side = 'kalshi_no_poly_yes'
        #     self.eff_kalshi_no_price = kalshi_crypto_fee(kalshi_price)
        #     self.kalshi_no_price = kalshi_price
        #     self.eff_poly_yes_price = poly_crypto_fee(poly_price)
        #     self.poly_yes_price = poly_price

        # self.kalshi_order_id = #
        # self.polymarket_order_id = #
        # self.kalshi_filled=float(kalshi_resp['order']['fill_count_fp'])

    def populate(self):
        return

        # TODO track the order down and find the fill volume
        #self.poly_filled=if not isinstance(poly_resp, Exception) else 0.0

# metric = Crypto15MinArbMetric(
#             market=market_name,
#             timestamp=str(datetime.now(timezone.utc)),
#             execution_time=execution_time,
#             expected_return=(1.0 - eff_arb) * volume,
#             polymarket_request_response_time=poly_rtt,
#             kalshi_request_response_time=kalshi_rtt,
#             side='kalshi_yes_poly_no' if kalshi_side == 'yes' else 'kalshi_no_poly_yes',
#             eff_combined_price=eff_arb,
#             volume=int(volume),
#             eff_kalshi_yes_price=kalshi_fee(kalshi_price) if kalshi_side == 'yes' else None,
#             eff_poly_no_price=poly_fee(polymarket_price) if kalshi_side == 'yes' else None,
#             kalshi_yes_price=kalshi_price if kalshi_side == 'yes' else None,
#             poly_no_price=polymarket_price if kalshi_side == 'yes' else None,
#             eff_kalshi_no_price=kalshi_fee(kalshi_price) if kalshi_side == 'no' else None,
#             eff_poly_yes_price=poly_fee(polymarket_price) if kalshi_side == 'no' else None,
#             kalshi_no_price=kalshi_price if kalshi_side == 'no' else None,
#             poly_yes_price=polymarket_price if kalshi_side == 'no' else None,
#             kalshi_filled=float(kalshi_resp['order']['fill_count_fp']),
#             poly_filled=volume if not isinstance(poly_resp, Exception) else 0.0
#         )