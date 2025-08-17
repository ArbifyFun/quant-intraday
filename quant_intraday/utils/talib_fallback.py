"""
Simple fallback implementations for a handful of common TA‑Lib indicators.

The original project relies on the `TA‑Lib` C extension for technical
indicators such as EMA, ATR, RSI, Bollinger Bands and OBV.  In environments
where `TA‑Lib` is unavailable or cannot be installed, importing it will
raise an ImportError and break the runtime.  To make the toolkit easier to
deploy in constrained environments (for example, this evaluation sandbox
without system C libraries), this module provides pure‑Python (pandas and
NumPy) implementations of the subset of indicators used in the toolkit.

These functions accept NumPy arrays or list‑like objects and return NumPy
arrays.  Their signatures intentionally mirror the corresponding `TA‑Lib`
functions closely enough to be used interchangeably in the existing code.

Note that these implementations are approximations: they follow common
formulae for each indicator but may differ slightly from the C library in
edge case handling or default parameter behaviour.  They are sufficient
for backtesting and live trading in most cases, but if precise parity
with `TA‑Lib` is critical you should install the official library.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

def _to_series(arr) -> pd.Series:
    """Utility to coerce an input into a pandas Series."""
    if isinstance(arr, pd.Series):
        return arr
    return pd.Series(arr)

def EMA(data, period: int) -> np.ndarray:
    """Exponential Moving Average.

    Parameters
    ----------
    data : array‑like
        Price series.
    period : int
        Window length.

    Returns
    -------
    np.ndarray
        Array of EMA values.
    """
    series = _to_series(data)
    # use adjust=False for trading indicator semantics
    ema = series.ewm(span=period, adjust=False, min_periods=period).mean()
    return ema.to_numpy()

def ATR(high, low, close, period: int) -> np.ndarray:
    """Average True Range.

    The ATR is calculated as the rolling mean of the true range over
    `period` bars.  True range is the maximum of:

    * current high – current low
    * absolute difference between current high and previous close
    * absolute difference between current low and previous close

    Parameters
    ----------
    high, low, close : array‑like
        High, low and close price series.
    period : int
        Lookback window.

    Returns
    -------
    np.ndarray
        ATR values.
    """
    h = _to_series(high)
    l = _to_series(low)
    c = _to_series(close)
    prev_close = c.shift(1)
    tr_components = pd.concat([
        h - l,
        (h - prev_close).abs(),
        (l - prev_close).abs(),
    ], axis=1)
    tr = tr_components.max(axis=1)
    atr = tr.rolling(period, min_periods=period).mean()
    # fill NaN values with zeros to match talib semantics
    return atr.fillna(0).to_numpy()

def RSI(data, period: int) -> np.ndarray:
    """Relative Strength Index.

    A simple implementation using the Wilder smoothing method.

    Parameters
    ----------
    data : array‑like
        Closing price series.
    period : int
        Lookback window.

    Returns
    -------
    np.ndarray
        RSI values in the range 0–100.  NaN values are produced for
        the first `period` samples.
    """
    series = _to_series(data)
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    # Use exponential moving average for Wilder's smoothing
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.to_numpy()

def BBANDS(data, period: int, nbdevup: float, nbdevdn: float):
    """Bollinger Bands (upper, middle, lower).

    Parameters
    ----------
    data : array‑like
        Price series.
    period : int
        Window length for the moving average.
    nbdevup, nbdevdn : float
        Number of standard deviations for the upper and lower bands.

    Returns
    -------
    tuple of np.ndarray
        Upper band, middle band and lower band arrays.
    """
    series = _to_series(data)
    ma = series.rolling(period, min_periods=period).mean()
    std = series.rolling(period, min_periods=period).std()
    upper = ma + std * nbdevup
    lower = ma - std * nbdevdn
    return upper.to_numpy(), ma.to_numpy(), lower.to_numpy()

def OBV(close, volume) -> np.ndarray:
    """On Balance Volume.

    Parameters
    ----------
    close : array‑like
        Closing price series.
    volume : array‑like
        Volume series.

    Returns
    -------
    np.ndarray
        Cumulative OBV values.
    """
    close = _to_series(close)
    volume = _to_series(volume)
    direction = close.diff().apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)
    obv = (volume * direction).fillna(0).cumsum()
    return obv.to_numpy()
