"""
BitBot Advanced Pattern Engine
Detects: Market Regime, Fibonacci Levels, Elliott Wave, Volume Profile,
         Divergences, Order Blocks, Trend Strength (ADX), Smart Money Concepts.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from bot import logger


# ─── Market Regime Detection ─────────────────────────────────────────────────

def detect_market_regime(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Classifies market as: Trending Up / Trending Down / Ranging / Volatile.
    Uses ADX + Choppiness Index + EMA slope.
    """
    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    n = 14

    # ADX
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(n).mean()
    up   = (high - high.shift()).clip(lower=0)
    down = (low.shift() - low).clip(lower=0)
    di_plus  = 100 * (up.rolling(n).mean() / atr)
    di_minus = 100 * (down.rolling(n).mean() / atr)
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus)
    adx = dx.rolling(n).mean().iloc[-1]

    # EMA slope
    ema50 = close.ewm(span=50, adjust=False).mean()
    slope_pct = ((ema50.iloc[-1] - ema50.iloc[-5]) / ema50.iloc[-5]) * 100

    # Choppiness Index (100×ATR14_sum / (highest_high - lowest_low))
    atr14_sum    = tr.rolling(14).sum()
    hh14 = high.rolling(14).max()
    ll14 = low.rolling(14).min()
    chop = 100 * np.log10(atr14_sum / (hh14 - ll14 + 1e-9)) / np.log10(14)
    chop_val = chop.iloc[-1]

    if adx > 25:
        if slope_pct > 0.1:
            regime = "TRENDING_UP"
            desc   = f"Strong uptrend (ADX {adx:.1f})"
        else:
            regime = "TRENDING_DOWN"
            desc   = f"Strong downtrend (ADX {adx:.1f})"
    elif chop_val > 61.8:
        regime = "RANGING"
        desc   = f"Choppy/ranging market (Chop {chop_val:.1f})"
    else:
        regime = "TRANSITIONING"
        desc   = f"Market transitioning (ADX {adx:.1f})"

    return {
        "regime": regime,
        "adx": round(adx, 2),
        "di_plus": round(di_plus.iloc[-1], 2),
        "di_minus": round(di_minus.iloc[-1], 2),
        "choppiness": round(chop_val, 2),
        "ema50_slope_pct": round(slope_pct, 4),
        "description": desc,
        "tradeable": regime in ("TRENDING_UP", "TRENDING_DOWN"),
    }


# ─── Fibonacci Retracements ───────────────────────────────────────────────────

FIB_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618]

def calculate_fibonacci(df: pd.DataFrame, lookback: int = 50) -> Dict[str, Any]:
    """Calculate Fib retracement/extension levels from recent swing high/low."""
    recent = df.tail(lookback)
    swing_high = recent["high"].max()
    swing_low  = recent["low"].min()
    diff = swing_high - swing_low
    price = df["close"].iloc[-1]

    levels = {f"fib_{str(l).replace('.','_')}": round(swing_low + diff * (1 - l), 6) for l in FIB_LEVELS}

    # Which level is price nearest to?
    nearest_level = min(FIB_LEVELS, key=lambda l: abs(price - (swing_low + diff * (1 - l))))
    distance_pct  = abs(price - levels[f"fib_{str(nearest_level).replace('.','_')}"]) / price * 100

    # Support/resistance via Fib
    fib_618 = swing_low + diff * (1 - 0.618)
    fib_382 = swing_low + diff * (1 - 0.382)
    at_support    = price <= fib_618 * 1.005
    at_resistance = price >= fib_382 * 0.995

    return {
        "swing_high": swing_high,
        "swing_low": swing_low,
        "levels": levels,
        "nearest_fib": nearest_level,
        "distance_pct": round(distance_pct, 3),
        "at_support": at_support,
        "at_resistance": at_resistance,
        "fib_618": fib_618,
        "fib_382": fib_382,
    }


# ─── Volume Profile ───────────────────────────────────────────────────────────

def analyze_volume_profile(df: pd.DataFrame, bins: int = 20) -> Dict[str, Any]:
    """Identify Point of Control (POC) and high-volume nodes."""
    recent = df.tail(100)
    price_min = recent["low"].min()
    price_max = recent["high"].max()
    bin_size   = (price_max - price_min) / bins

    profile = {}
    for _, row in recent.iterrows():
        bin_idx = int((row["close"] - price_min) / (bin_size + 1e-9))
        bin_idx = min(bin_idx, bins - 1)
        profile[bin_idx] = profile.get(bin_idx, 0) + row["volume"]

    if not profile:
        return {}

    # Point of Control
    poc_bin  = max(profile, key=profile.get)
    poc_price = price_min + poc_bin * bin_size + bin_size / 2

    # Value Area (70% of volume)
    total_vol = sum(profile.values())
    target_vol = total_vol * 0.70
    sorted_bins = sorted(profile.items(), key=lambda x: x[1], reverse=True)
    cumvol = 0
    va_bins = []
    for b, v in sorted_bins:
        cumvol += v
        va_bins.append(b)
        if cumvol >= target_vol:
            break
    va_high = price_min + max(va_bins) * bin_size + bin_size
    va_low  = price_min + min(va_bins) * bin_size

    price = df["close"].iloc[-1]
    return {
        "poc": round(poc_price, 6),
        "va_high": round(va_high, 6),
        "va_low": round(va_low, 6),
        "price_vs_poc": "above" if price > poc_price else "below",
        "in_value_area": va_low <= price <= va_high,
    }


# ─── RSI / MACD Divergence ────────────────────────────────────────────────────

def detect_divergence(df: pd.DataFrame) -> Dict[str, Any]:
    """Detect bullish/bearish RSI and MACD divergences."""
    close = df["close"]
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    rsi = (100 - 100 / (1 + gain / loss)).values

    # Find recent local lows (for bullish div) and highs (for bearish div)
    price_arr = close.values
    lookback = min(30, len(price_arr) - 1)

    bullish_div = False
    bearish_div = False

    # Bullish: price makes lower low but RSI makes higher low
    if (price_arr[-1] < price_arr[-lookback] and
            rsi[-1] > rsi[-lookback] and
            rsi[-1] < 50):
        bullish_div = True

    # Bearish: price makes higher high but RSI makes lower high
    if (price_arr[-1] > price_arr[-lookback] and
            rsi[-1] < rsi[-lookback] and
            rsi[-1] > 50):
        bearish_div = True

    return {
        "bullish_divergence": bullish_div,
        "bearish_divergence": bearish_div,
        "current_rsi": round(rsi[-1], 2),
    }


# ─── Smart Money Concepts — Order Blocks ─────────────────────────────────────

def detect_order_blocks(df: pd.DataFrame, lookback: int = 30) -> List[Dict]:
    """
    Order blocks: the last bearish candle before a bullish impulse (demand),
    or last bullish candle before a bearish impulse (supply).
    """
    blocks = []
    data = df.tail(lookback).reset_index(drop=True)
    for i in range(2, len(data) - 1):
        candle = data.iloc[i]
        next_c = data.iloc[i + 1]
        # Bullish OB: bearish candle followed by strong bullish move
        if candle["close"] < candle["open"]:  # bearish candle
            impulse = (next_c["close"] - next_c["open"]) / next_c["open"]
            if impulse > 0.005:  # 0.5% impulse
                blocks.append({
                    "type": "demand",
                    "top": float(candle["open"]),
                    "bottom": float(candle["close"]),
                    "index": i,
                })
        # Bearish OB: bullish candle followed by strong bearish move
        elif candle["close"] > candle["open"]:  # bullish candle
            impulse = (next_c["open"] - next_c["close"]) / next_c["open"]
            if impulse > 0.005:
                blocks.append({
                    "type": "supply",
                    "top": float(candle["close"]),
                    "bottom": float(candle["open"]),
                    "index": i,
                })
    return blocks[-4:]  # Return last 4 blocks


# ─── Trend Strength (ADX Direction) ──────────────────────────────────────────

def trend_strength_score(regime: Dict) -> Tuple[float, int]:
    """
    Returns (score 0-100, signal: +1/-1/0)
    based on ADX and DI+/DI-.
    """
    adx = regime.get("adx", 0)
    di_plus = regime.get("di_plus", 0)
    di_minus = regime.get("di_minus", 0)
    r = regime.get("regime", "")

    if adx < 20:
        return 50.0, 0  # Weak trend, no signal

    strength = min(100, (adx / 50) * 100)  # Normalize ADX to 0-100
    if di_plus > di_minus:
        return strength, 1
    elif di_minus > di_plus:
        return 100 - strength, -1
    return 50.0, 0


# ─── Main Pattern Engine ──────────────────────────────────────────────────────

class PatternEngine:
    def analyze(self, df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        if len(df) < 52:
            return {}
        logger.analysis(f"🔬 Running advanced pattern analysis [{symbol}]...")

        regime    = detect_market_regime(df)
        fibonacci = calculate_fibonacci(df)
        vol_prof  = analyze_volume_profile(df)
        divergence= detect_divergence(df)
        ob_blocks = detect_order_blocks(df)
        ts_score, ts_signal = trend_strength_score(regime)

        signals: List[int] = []

        # Regime signals
        if regime["regime"] == "TRENDING_UP":   signals.extend([1, 1])
        elif regime["regime"] == "TRENDING_DOWN": signals.extend([-1, -1])
        elif regime["regime"] == "RANGING":      signals.append(0)

        # Fibonacci signals
        if fibonacci.get("at_support"):    signals.extend([1, 1])
        if fibonacci.get("at_resistance"): signals.extend([-1, -1])

        # Volume Profile signals
        if vol_prof.get("price_vs_poc") == "above" and vol_prof.get("in_value_area"):
            signals.append(1)
        elif vol_prof.get("price_vs_poc") == "below" and vol_prof.get("in_value_area"):
            signals.append(-1)

        # Divergence signals
        if divergence.get("bullish_divergence"): signals.extend([1, 1])
        if divergence.get("bearish_divergence"): signals.extend([-1, -1])

        # Trend strength
        if ts_signal == 1:  signals.append(1)
        elif ts_signal == -1: signals.append(-1)

        # Order block signals
        price = df["close"].iloc[-1]
        for ob in ob_blocks:
            if ob["type"] == "demand" and ob["bottom"] <= price <= ob["top"] * 1.01:
                signals.extend([1, 1])
            elif ob["type"] == "supply" and ob["bottom"] * 0.99 <= price <= ob["top"]:
                signals.extend([-1, -1])

        total = len(signals)
        bull  = signals.count(1)
        bear  = signals.count(-1)
        score = (bull / total * 100) if total > 0 else 50.0

        result = {
            "regime":     regime,
            "fibonacci":  fibonacci,
            "volume_profile": vol_prof,
            "divergence": divergence,
            "order_blocks": ob_blocks,
            "trend_strength": {"score": ts_score, "signal": ts_signal},
            "composite": {
                "score": round(score, 2),
                "direction": "BUY" if score >= 60 else ("SELL" if score <= 40 else "NEUTRAL"),
                "bull_signals": bull,
                "bear_signals": bear,
                "total_signals": total,
            }
        }

        logger.analysis(
            f"Patterns [{symbol}]: Regime={regime['regime']} | ADX={regime['adx']:.1f} | "
            f"FibNearest={fibonacci.get('nearest_fib','-')} | "
            f"BullDiv={divergence['bullish_divergence']} | BearDiv={divergence['bearish_divergence']} | "
            f"Score={score:.1f}%"
        )
        return result


pattern_engine = PatternEngine()
