from quant_intraday.utils.cost_model import CostSpec, get_costs
class DummyCli: 
    def get_instrument(self, iid): return {"tickSz":"0.01","lotSz":"1"}
def test_costs_fallback():
    c = get_costs(DummyCli(), "FOO-BAR")  # no costs.yaml entry
    assert c.tick_size == 0.01 and c.lot_size == 1.0
