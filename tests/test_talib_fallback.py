import numpy as np
from quant_intraday.utils.talib_fallback import EMA, ATR, RSI, BBANDS, OBV

close = np.array([1,2,3,4,5,6,7,8,9,10], dtype=float)
high = close + 0.5
low = close - 0.5
volume = np.array([10,11,12,13,14,15,16,17,18,19], dtype=float)


def test_ema():
    expected = np.array([np.nan, np.nan, 2.25, 3.125, 4.0625, 5.03125,
                         6.015625, 7.0078125, 8.00390625, 9.00195312])
    np.testing.assert_allclose(EMA(close, 3), expected, equal_nan=True)


def test_atr():
    expected = np.array([0.0, 0.0, 1.33333333, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5])
    np.testing.assert_allclose(ATR(high, low, close, 3), expected, equal_nan=True)


def test_rsi():
    expected = np.array([np.nan, np.nan, 100., 100., 100., 100., 100., 100., 100., 100.])
    np.testing.assert_allclose(RSI(close, 3), expected, equal_nan=True)


def test_bbands():
    upper, mid, lower = BBANDS(close, 3, 1, 1)
    exp_u = np.array([np.nan, np.nan, 3., 4., 5., 6., 7., 8., 9., 10.])
    exp_m = np.array([np.nan, np.nan, 2., 3., 4., 5., 6., 7., 8., 9.])
    exp_l = np.array([np.nan, np.nan, 1., 2., 3., 4., 5., 6., 7., 8.])
    np.testing.assert_allclose(upper, exp_u, equal_nan=True)
    np.testing.assert_allclose(mid, exp_m, equal_nan=True)
    np.testing.assert_allclose(lower, exp_l, equal_nan=True)


def test_obv():
    expected = np.array([0., 11., 23., 36., 50., 65., 81., 98., 116., 135.])
    np.testing.assert_allclose(OBV(close, volume), expected, equal_nan=True)
