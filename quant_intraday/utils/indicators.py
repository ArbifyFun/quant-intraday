"""Utilities for loading technical indicator functions.

This module centralises the logic for importing the optional `TA-Lib`
extension and falling back to the lightweight pure Python implementations
provided in :mod:`quant_intraday.utils.talib_fallback`.  Code that requires
technical indicators should import and call :func:`get_ta` to obtain an object
exposing the standard indicator functions.
"""
from __future__ import annotations

from typing import Any


def get_ta() -> Any:
    """Return an indicator module compatible with :mod:`talib`.

    The function first attempts to import the real `TA-Lib` package.  If it is
    unavailable, a small proxy object exposing the handful of indicators used
    in this project is returned instead.
    """
    try:
        import talib as ta  # type: ignore
        return ta
    except ImportError:
        from .talib_fallback import EMA as _EMA, ATR as _ATR, RSI as _RSI, BBANDS as _BBANDS, OBV as _OBV

        class _Fallback:
            @staticmethod
            def EMA(*args, **kwargs):
                return _EMA(*args, **kwargs)

            @staticmethod
            def ATR(*args, **kwargs):
                return _ATR(*args, **kwargs)

            @staticmethod
            def RSI(*args, **kwargs):
                return _RSI(*args, **kwargs)

            @staticmethod
            def BBANDS(*args, **kwargs):
                return _BBANDS(*args, **kwargs)

            @staticmethod
            def OBV(*args, **kwargs):
                return _OBV(*args, **kwargs)

        return _Fallback()
