from quant_intraday.config import QIConfig, InstrumentCfg


def test_portfolio_instruments_isolated():
    a = QIConfig()
    b = QIConfig()
    a.portfolio.instruments.append(InstrumentCfg(inst="BTC-USDT", tf="1m"))
    assert len(b.portfolio.instruments) == 0
