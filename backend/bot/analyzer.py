"""
BitBot Technical Analyzer
Computes 20+ indicators across multiple timeframes and generates a composite signal.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, List
from bot import logger


# ─── Indicator Helpers ─────────────────────────────────────────────────────────

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()

def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def _macd(series: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
    fast = _ema(series, 12)
    slow = _ema(series, 26)
    macd_line = fast - slow
    signal_line = _ema(macd_line, 9)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def _bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    middle = _sma(series, period)
    std = series.rolling(window=period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower

def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def _stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    low_min = df["low"].rolling(window=k_period).min()
    high_max = df["high"].rolling(window=k_period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min)
    d = k.rolling(window=d_period).mean()
    return k, d

def _williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_max = df["high"].rolling(window=period).max()
    low_min = df["low"].rolling(window=period).min()
    return -100 * (high_max - df["close"]) / (high_max - low_min)

def _cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma_tp = tp.rolling(window=period).mean()
    mad = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - x.mean())))
    return (tp - sma_tp) / (0.015 * mad)

def _obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff()).fillna(0)
    return (direction * df["volume"]).cumsum()

def _mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    rmf = tp * df["volume"]
    delta = tp.diff()
    pos_mf = rmf.where(delta > 0, 0).rolling(window=period).sum()
    neg_mf = rmf.where(delta < 0, 0).rolling(window=period).sum()
    mfr = pos_mf / neg_mf
    return 100 - (100 / (1 + mfr))

def _cmf(df: pd.DataFrame, period: int = 20) -> pd.Series:
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / (df["high"] - df["low"])
    mfm = mfm.fillna(0)
    mfv = mfm * df["volume"]
    return mfv.rolling(window=period).sum() / df["volume"].rolling(window=period).sum()

def _vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_vol = df["volume"].cumsum()
    cumulative_tp_vol = (tp * df["volume"]).cumsum()
    return cumulative_tp_vol / cumulative_vol

def _ichimoku(df: pd.DataFrame):
    tenkan = (df["high"].rolling(9).max() + df["low"].rolling(9).min()) / 2
    kijun = (df["high"].rolling(26).max() + df["low"].rolling(26).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    senkou_b = ((df["high"].rolling(52).max() + df["low"].rolling(52).min()) / 2).shift(26)
    chikou = df["close"].shift(-26)
    return tenkan, kijun, senkou_a, senkou_b, chikou

def _support_resistance(df: pd.DataFrame, window: int = 20) -> Tuple[float, float]:
    recent = df.tail(window)
    support = recent["low"].min()
    resistance = recent["high"].max()
    return support, resistance

def _pivot_points(df: pd.DataFrame) -> Dict[str, float]:
    prev = df.iloc[-2]
    pp = (prev["high"] + prev["low"] + prev["close"]) / 3
    return {
        "pp": pp,
        "r1": 2 * pp - prev["low"],
        "r2": pp + (prev["high"] - prev["low"]),
        "s1": 2 * pp - prev["high"],
        "s2": pp - (prev["high"] - prev["low"]),
    }

def _keltner_channels(df: pd.DataFrame, period: int = 20, atr_multiplier: float = 2.0):
    ema = _ema(df["close"], period)
    atr = _atr(df, period).fillna(0)
    upper = ema + (atr_multiplier * atr)
    lower = ema - (atr_multiplier * atr)
    return upper, ema, lower

def _trix(series: pd.Series, period: int = 15) -> pd.Series:
    ema1 = _ema(series, period)
    ema2 = _ema(ema1, period)
    ema3 = _ema(ema2, period)
    return ((ema3 - ema3.shift(1)) / (ema3.shift(1) + 1e-9) * 10000).fillna(0)

def _ultimate_oscillator(df: pd.DataFrame) -> pd.Series:
    bp = df["close"] - pd.concat([df["low"], df["close"].shift(1)], axis=1).min(axis=1)
    tr = pd.concat([df["high"], df["close"].shift(1)], axis=1).max(axis=1) - pd.concat([df["low"], df["close"].shift(1)], axis=1).min(axis=1)
    avg7 = bp.rolling(7).sum() / (tr.rolling(7).sum() + 1e-9)
    avg14 = bp.rolling(14).sum() / (tr.rolling(14).sum() + 1e-9)
    avg28 = bp.rolling(28).sum() / (tr.rolling(28).sum() + 1e-9)
    return (100 * ((4 * avg7) + (2 * avg14) + avg28) / 7).fillna(50)

def _detect_candlestick_patterns(df: pd.DataFrame) -> List[str]:
    patterns = []
    last = df.iloc[-1]
    prev = df.iloc[-2]
    body = abs(last["close"] - last["open"])
    total = last["high"] - last["low"]
    upper_shadow = last["high"] - max(last["close"], last["open"])
    lower_shadow = min(last["close"], last["open"]) - last["low"]

    # Doji
    if body <= 0.1 * total:
        patterns.append("Doji")

    # Hammer (bullish)
    if lower_shadow >= 2 * body and upper_shadow < 0.1 * total and last["close"] > last["open"]:
        patterns.append("Hammer (Bullish)")

    # Shooting Star (bearish)
    if upper_shadow >= 2 * body and lower_shadow < 0.1 * total and last["close"] < last["open"]:
        patterns.append("Shooting Star (Bearish)")

    # Bullish Engulfing
    if (prev["close"] < prev["open"] and last["close"] > last["open"]
            and last["open"] < prev["close"] and last["close"] > prev["open"]):
        patterns.append("Bullish Engulfing")

    # Bearish Engulfing
    if (prev["close"] > prev["open"] and last["close"] < last["open"]
            and last["open"] > prev["close"] and last["close"] < prev["open"]):
        patterns.append("Bearish Engulfing")

    # Morning Star (simplified)
    if len(df) >= 3:
        p3 = df.iloc[-3]
        if (p3["close"] < p3["open"] and abs(prev["close"] - prev["open"]) < 0.3 * abs(p3["close"] - p3["open"])
                and last["close"] > last["open"] and last["close"] > (p3["open"] + p3["close"]) / 2):
            patterns.append("Morning Star (Bullish)")

    # Three White Soldiers (simplified)
    if len(df) >= 4:
        p3 = df.iloc[-3]
        if (p3["close"] > p3["open"] and prev["close"] > prev["open"] and last["close"] > last["open"] and
            prev["close"] > p3["close"] and last["close"] > prev["close"] and
            p3["open"] < prev["open"] and prev["open"] < last["open"]):
            patterns.append("Three White Soldiers (Bullish)")

    # Three Black Crows (simplified)
    if len(df) >= 4:
        p3 = df.iloc[-3]
        if (p3["close"] < p3["open"] and prev["close"] < prev["open"] and last["close"] < last["open"] and
            prev["close"] < p3["close"] and last["close"] < prev["close"] and
            p3["open"] > prev["open"] and prev["open"] > last["open"]):
            patterns.append("Three Black Crows (Bearish)")

    # Marubozu
    std_val = df["close"].rolling(20).std().iloc[-1]
    if body > 0.9 * total and total > (std_val if not pd.isna(std_val) else 0):
        if last["close"] > last["open"]:
            patterns.append("Bullish Marubozu")
        else:
            patterns.append("Bearish Marubozu")

    # Tweezer Bottom
    if abs(last["low"] - prev["low"]) / (last["close"] + 1e-9) < 0.001 and prev["close"] < prev["open"] and last["close"] > last["open"]:
        patterns.append("Tweezer Bottom (Bullish)")
        
    # Tweezer Top
    if abs(last["high"] - prev["high"]) / (last["close"] + 1e-9) < 0.001 and prev["close"] > prev["open"] and last["close"] < last["open"]:
        patterns.append("Tweezer Top (Bearish)")

    return patterns


class TechnicalAnalyzer:
    """
    Performs full multi-indicator technical analysis on OHLCV data.
    Returns a composite score and direction signal.
    """

    def analyze(self, df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        if df.empty or len(df) < 52:
            logger.warning(f"Not enough data for analysis [{symbol}] — need at least 52 candles")
            return {}

        logger.analysis(f"Running technical analysis on {symbol} ({len(df)} candles)...")

        close = df["close"]
        results: Dict[str, Any] = {}
        signals: List[int] = []  # +1 = bullish, -1 = bearish, 0 = neutral

        # ── EMA Trend ──────────────────────────────────────────────────────────
        ema9  = _ema(close, 9).iloc[-1]
        ema21 = _ema(close, 21).iloc[-1]
        ema50 = _ema(close, 50).iloc[-1]
        ema200= _ema(close, 200).iloc[-1] if len(df) >= 200 else None
        price = close.iloc[-1]
        results["ema"] = {"ema9": ema9, "ema21": ema21, "ema50": ema50, "ema200": ema200, "price": price}
        if ema9 > ema21: signals.append(1)
        elif ema9 < ema21: signals.append(-1)
        else: signals.append(0)
        if price > ema50: signals.append(1)
        elif price < ema50: signals.append(-1)
        else: signals.append(0)
        if ema200 and price > ema200: signals.append(1)
        elif ema200 and price < ema200: signals.append(-1)

        # ── RSI ────────────────────────────────────────────────────────────────
        rsi_val = _rsi(close).iloc[-1]
        rsi_prev = _rsi(close).iloc[-2]
        results["rsi"] = {"value": rsi_val}
        if rsi_val < 30: signals.extend([1, 1])   # oversold — strong buy
        elif rsi_val > 70: signals.extend([-1, -1])# overbought — strong sell
        elif rsi_val > 50 and rsi_val > rsi_prev: signals.append(1)
        elif rsi_val < 50 and rsi_val < rsi_prev: signals.append(-1)
        else: signals.append(0)

        # ── MACD ───────────────────────────────────────────────────────────────
        macd_line, macd_signal, macd_hist = _macd(close)
        macd_curr = macd_line.iloc[-1]
        macd_sig  = macd_signal.iloc[-1]
        macd_hist_curr = macd_hist.iloc[-1]
        macd_hist_prev = macd_hist.iloc[-2]
        results["macd"] = {"macd": macd_curr, "signal": macd_sig, "histogram": macd_hist_curr}
        if macd_curr > macd_sig: signals.append(1)
        elif macd_curr < macd_sig: signals.append(-1)
        else: signals.append(0)
        if macd_hist_curr > 0 and macd_hist_curr > macd_hist_prev: signals.append(1)
        elif macd_hist_curr < 0 and macd_hist_curr < macd_hist_prev: signals.append(-1)
        else: signals.append(0)

        # ── Bollinger Bands ────────────────────────────────────────────────────
        bb_upper, bb_mid, bb_lower = _bollinger_bands(close)
        bb_u, bb_m, bb_l = bb_upper.iloc[-1], bb_mid.iloc[-1], bb_lower.iloc[-1]
        bb_pct = (price - bb_l) / (bb_u - bb_l) if (bb_u - bb_l) > 0 else 0.5
        results["bollinger"] = {"upper": bb_u, "middle": bb_m, "lower": bb_l, "pct_b": bb_pct}
        # Squeeze detection (low volatility)
        bb_width = (bb_u - bb_l) / bb_m
        bb_width_avg = ((bb_upper - bb_lower) / bb_mid).rolling(100).mean().iloc[-1]
        is_squeeze = bb_width < bb_width_avg * 0.8
        results["bollinger"]["is_squeeze"] = is_squeeze
        if is_squeeze:
            logger.info(f"BB Squeeze detected on {symbol} — expecting breakout")
            
        if price < bb_l: signals.extend([1, 1])
        elif price > bb_u: signals.extend([-1, -1])
        elif bb_pct > 0.5: signals.append(1)
        else: signals.append(-1)

        # ── Stochastic ─────────────────────────────────────────────────────────
        stoch_k, stoch_d = _stochastic(df)
        sk, sd = stoch_k.iloc[-1], stoch_d.iloc[-1]
        results["stochastic"] = {"k": sk, "d": sd}
        if sk < 20 and sd < 20: signals.extend([1, 1])
        elif sk > 80 and sd > 80: signals.extend([-1, -1])
        elif sk > sd: signals.append(1)
        elif sk < sd: signals.append(-1)
        else: signals.append(0)

        # ── Williams %R ────────────────────────────────────────────────────────
        wr = _williams_r(df).iloc[-1]
        results["williams_r"] = {"value": wr}
        if wr < -80: signals.append(1)
        elif wr > -20: signals.append(-1)
        else: signals.append(0)

        # ── CCI ────────────────────────────────────────────────────────────────
        cci_val = _cci(df).iloc[-1]
        results["cci"] = {"value": cci_val}
        if cci_val < -100: signals.append(1)
        elif cci_val > 100: signals.append(-1)
        else: signals.append(0)

        # ── VWAP ───────────────────────────────────────────────────────────────
        vwap_val = _vwap(df).iloc[-1]
        results["vwap"] = {"value": vwap_val}
        if price > vwap_val: signals.append(1)
        elif price < vwap_val: signals.append(-1)
        else: signals.append(0)

        # ── OBV Trend ──────────────────────────────────────────────────────────
        obv = _obv(df)
        obv_ema = _ema(obv, 20)
        if obv.iloc[-1] > obv_ema.iloc[-1]: signals.append(1)
        elif obv.iloc[-1] < obv_ema.iloc[-1]: signals.append(-1)
        else: signals.append(0)
        results["obv"] = {"value": float(obv.iloc[-1])}
        
        # ── MFI & CMF ──────────────────────────────────────────────────────────
        mfi_val = _mfi(df).iloc[-1]
        cmf_val = _cmf(df).iloc[-1]
        results["mfi"] = mfi_val
        results["cmf"] = cmf_val
        if mfi_val < 20: signals.append(1)
        elif mfi_val > 80: signals.append(-1)
        if cmf_val > 0.1: signals.append(1)
        elif cmf_val < -0.1: signals.append(-1)

        # ── ATR (volatility) ───────────────────────────────────────────────────
        atr_val = _atr(df).iloc[-1]
        results["atr"] = {"value": atr_val, "pct": (atr_val / price) * 100}

        # ── Ichimoku ───────────────────────────────────────────────────────────
        tenkan, kijun, senkou_a, senkou_b, chikou = _ichimoku(df)
        ichi_t, ichi_k = tenkan.iloc[-1], kijun.iloc[-1]
        ichi_a, ichi_b = senkou_a.iloc[-1], senkou_b.iloc[-1]
        results["ichimoku"] = {"tenkan": ichi_t, "kijun": ichi_k, "senkou_a": ichi_a, "senkou_b": ichi_b}
        # Price above cloud = bullish
        cloud_top = max(ichi_a, ichi_b) if not np.isnan(ichi_a) and not np.isnan(ichi_b) else price
        cloud_bot = min(ichi_a, ichi_b) if not np.isnan(ichi_a) and not np.isnan(ichi_b) else price
        if price > cloud_top: signals.extend([1, 1])
        elif price < cloud_bot: signals.extend([-1, -1])
        else: signals.append(0)
        if ichi_t > ichi_k: signals.append(1)
        elif ichi_t < ichi_k: signals.append(-1)

        # ── Support & Resistance ───────────────────────────────────────────────
        support, resistance = _support_resistance(df)
        pivots = _pivot_points(df)
        results["levels"] = {"support": support, "resistance": resistance, "pivots": pivots}
        # Near support = bullish, near resistance = bearish
        prox_support = abs(price - support) / price
        prox_resist  = abs(price - resistance) / price
        if prox_support < 0.005: signals.append(1)
        if prox_resist  < 0.005: signals.append(-1)

        # ── Volume Spike ───────────────────────────────────────────────────────
        avg_vol = df["volume"].rolling(20).mean().iloc[-1]
        curr_vol = df["volume"].iloc[-1]
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1
        results["volume"] = {"current": curr_vol, "avg": avg_vol, "ratio": vol_ratio}
        if vol_ratio > 2.0:  # Volume spike amplifies signal
            if signals and signals[-1] == 1: signals.append(1)
            elif signals and signals[-1] == -1: signals.append(-1)

        # ── Keltner Channels ───────────────────────────────────────────────────
        kc_u, kc_m, kc_l = _keltner_channels(df)
        kcu, kcm, kcl = kc_u.iloc[-1], kc_m.iloc[-1], kc_l.iloc[-1]
        results["keltner"] = {"upper": kcu, "middle": kcm, "lower": kcl}
        if price > kcu: signals.extend([1, 1])  # Breakout upside
        elif price < kcl: signals.extend([-1, -1])  # Breakout downside
        elif price > kcm: signals.append(1)
        elif price < kcm: signals.append(-1)
        else: signals.append(0)

        # ── TRIX ───────────────────────────────────────────────────────────────
        trix_s = _trix(close)
        trix_val = trix_s.iloc[-1]
        trix_prev = trix_s.iloc[-2]
        results["trix"] = {"value": trix_val}
        if trix_val > 0 and trix_val > trix_prev: signals.append(1)
        elif trix_val < 0 and trix_val < trix_prev: signals.append(-1)
        elif trix_val > 0: signals.append(1)
        elif trix_val < 0: signals.append(-1)

        # ── Ultimate Oscillator ────────────────────────────────────────────────
        uo = _ultimate_oscillator(df).iloc[-1]
        results["ultimate_oscillator"] = {"value": uo}
        if uo > 70: signals.extend([-1, -1])  # Overbought
        elif uo < 30: signals.extend([1, 1])  # Oversold
        elif uo > 50: signals.append(1)
        elif uo < 50: signals.append(-1)

        # ── Composite Score ────────────────────────────────────────────────────
        # Technical signals summary
        total_weight = len(signals) if 'signals' in locals() else 0
        bull_weight = signals.count(1) if 'signals' in locals() else 0
        bear_weight = signals.count(-1) if 'signals' in locals() else 0
        
        # Add extra weight for high-conviction states
        if rsi_val < 25 or rsi_val > 75: bull_weight += 0.5; bear_weight += 0.5; total_weight += 1
        if is_squeeze: total_weight += 1 # Squeeze increases the importance of other signals
        
        # Score: 0–100 (centered at 50)
        score = ((bull_weight / total_weight) * 100) if total_weight > 0 else 50.0
        
        # Sharpening: If it's a clear trend, push it further
        if abs(score - 50) > 10:
            score = 50 + (score - 50) * 1.15
            score = max(0, min(100, score))

        if score >= 60: # Lowered threshold slightly to be more responsive
            direction = "BUY"
        elif score <= 40:
            direction = "SELL"
        else:
            direction = "NEUTRAL"

        results["composite"] = {
            "score": round(score, 2),
            "direction": direction,
            "bull_signals": bull_weight,
            "bear_signals": bear_weight,
            "neutral_signals": total_weight - bull_weight - bear_weight,
            "total_signals": total_weight,
        }

        logger.analysis(
            f"TA complete [{symbol}] → {direction} | Score: {score:.1f}% "
            f"| RSI: {rsi_val:.1f} | MACD: {'▲' if macd_curr > macd_sig else '▼'} ",
            {"symbol": symbol, "score": score, "direction": direction}
        )

        return results
