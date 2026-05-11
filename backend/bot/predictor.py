"""
BitBot AI Predictor — v2
Fuses: Technical Analysis + Advanced Patterns + News Sentiment +
       Multi-Timeframe Momentum + Order Book Microstructure
into a single confidence score and trade signal.
"""

from typing import Dict, Any, Optional, Tuple, List
from bot import logger


# ── Weights for signal fusion ──────────────────────────────────────────────────
W_ML        = 0.25   # Machine Learning Random Forest Model
W_TECHNICAL = 0.25   # 20+ indicator TA composite
W_PATTERNS  = 0.15   # Regime, Fibonacci, divergence, order blocks
W_SENTIMENT = 0.15   # News + Fear & Greed
W_MOMENTUM  = 0.10   # Multi-timeframe agreement
W_MICROSTR  = 0.10   # Order book bid/ask imbalance


def _market_structure_score(orderbook: Optional[Dict]) -> Tuple[float, str]:
    """Analyze bid/ask depth imbalance."""
    if not orderbook:
        return 50.0, "NEUTRAL"
    bids = orderbook.get("bids", [])
    asks = orderbook.get("asks", [])
    if not bids or not asks:
        return 50.0, "NEUTRAL"
    bid_vol = sum(b[1] for b in bids[:10])
    ask_vol = sum(a[1] for a in asks[:10])
    total = bid_vol + ask_vol
    if total == 0:
        return 50.0, "NEUTRAL"
    bid_pct = (bid_vol / total) * 100
    if bid_pct >= 62:
        return round(bid_pct, 2), "BUY"
    elif bid_pct <= 38:
        return round(bid_pct, 2), "SELL"
    return round(bid_pct, 2), "NEUTRAL"


def _multi_timeframe_momentum(ta_list: List[Dict]) -> Tuple[float, str]:
    """Average score across multiple timeframes."""
    scores = [t.get("composite", {}).get("score", 50.0) for t in ta_list if t]
    if not scores:
        return 50.0, "NEUTRAL"
    avg = sum(scores) / len(scores)
    return round(avg, 2), "BUY" if avg >= 60 else ("SELL" if avg <= 40 else "NEUTRAL")


class Predictor:
    """
    Fuses all signal sources into one confidence score.
    Trades only when confidence ≥ threshold AND direction is clear.
    """

    def __init__(self, confidence_threshold: float = 85.0):
        self.threshold = confidence_threshold

    def predict(
        self,
        ta_results: Dict[str, Any],
        ta_results_htf: Optional[Dict] = None,
        ta_results_ltf: Optional[Dict] = None,
        news_results: Optional[Dict] = None,
        orderbook: Optional[Dict] = None,
        pattern_results: Optional[Dict] = None,
        ml_results: Optional[Dict] = None,
        symbol: str = "",
    ) -> Dict[str, Any]:

        logger.thinking(f"🧠 Running AI fusion prediction for {symbol}...")

        # ── 1. Technical Analysis Score ────────────────────────────────────────
        comp     = ta_results.get("composite", {})
        ta_score = comp.get("score", 50.0)
        ta_dir   = comp.get("direction", "NEUTRAL")

        # ── 2. Advanced Pattern Score ──────────────────────────────────────────
        if pattern_results:
            pat_comp  = pattern_results.get("composite", {})
            pat_score = pat_comp.get("score", 50.0)
            pat_dir   = pat_comp.get("direction", "NEUTRAL")
            regime    = pattern_results.get("regime", {})
            # Ranging / choppy market → dampen pattern confidence
            if not regime.get("tradeable", True):
                orig = pat_score
                pat_score = 50.0 + (pat_score - 50.0) * 0.3   # Dampen towards neutral
                logger.warning(
                    f"Non-tradeable regime ({regime.get('regime','?')}) — "
                    f"pattern score dampened {orig:.1f}% → {pat_score:.1f}%"
                )
        else:
            pat_score = 50.0
            pat_dir   = "NEUTRAL"
            regime    = {}

        # ── 3. News / Sentiment Score ──────────────────────────────────────────
        if news_results:
            sent_pct = news_results.get("sentiment_pct", 50.0)
            sent_dir = news_results.get("sentiment", "NEUTRAL")
            if news_results.get("coin_is_trending", False):
                sent_pct = min(100, sent_pct + 5)
        else:
            sent_pct = 50.0
            sent_dir = "NEUTRAL"

        # ── 4. Multi-Timeframe Momentum ────────────────────────────────────────
        mtf_score, mtf_dir = _multi_timeframe_momentum(
            [r for r in [ta_results_ltf, ta_results, ta_results_htf] if r]
        )

        # ── 5. Order Book Microstructure ───────────────────────────────────────
        micro_score, micro_dir = _market_structure_score(orderbook)

        # ── 5b. Machine Learning Score ─────────────────────────────────────────
        ml_score = (ml_results or {}).get("ml_score", 50.0)
        ml_dir   = (ml_results or {}).get("ml_direction", "NEUTRAL")

        # ── 6. Weighted Fusion ─────────────────────────────────────────────────
        raw_score = (
            ml_score    * W_ML        +
            ta_score    * W_TECHNICAL +
            pat_score   * W_PATTERNS  +
            sent_pct    * W_SENTIMENT +
            mtf_score   * W_MOMENTUM  +
            micro_score * W_MICROSTR
        )

        # ── 7. Direction Consensus Voting ──────────────────────────────────────
        directions = [ml_dir, ta_dir, pat_dir, sent_dir, mtf_dir, micro_dir]
        buy_votes  = directions.count("BUY")
        sell_votes = directions.count("SELL")

        # Full consensus (4-5/5) → stronger boost
        if buy_votes >= 4:
            raw_score = min(100, raw_score + 7)
            final_dir = "BUY"
        elif sell_votes >= 4:
            raw_score = max(0, raw_score - 7)
            final_dir = "SELL"
        elif buy_votes >= 3:
            raw_score = min(100, raw_score + 3)
            final_dir = "BUY"
        elif sell_votes >= 3:
            raw_score = max(0, raw_score - 3)
            final_dir = "SELL"
        elif buy_votes > sell_votes:
            final_dir = "BUY"
        elif sell_votes > buy_votes:
            final_dir = "SELL"
        else:
            final_dir = "NEUTRAL"

        # ── 8. Contradiction Penalties ─────────────────────────────────────────
        rsi_val = ta_results.get("rsi", {}).get("value", 50)
        penalty = 0.0

        if final_dir == "BUY" and rsi_val > 80:
            penalty += 8
            logger.warning(f"RSI overbought ({rsi_val:.1f}) → BUY confidence penalised −8%")
        elif final_dir == "SELL" and rsi_val < 20:
            penalty += 8
            logger.warning(f"RSI oversold ({rsi_val:.1f}) → SELL confidence penalised −8%")

        # Divergence contradictions
        div = (pattern_results or {}).get("divergence", {})
        if final_dir == "SELL" and div.get("bullish_divergence"):
            penalty += 5
            logger.warning("Bullish divergence detected against SELL signal → −5%")
        if final_dir == "BUY" and div.get("bearish_divergence"):
            penalty += 5
            logger.warning("Bearish divergence detected against BUY signal → −5%")

        # Ranging market penalty for directional trade
        if regime.get("regime") == "RANGING" and final_dir != "NEUTRAL":
            penalty += 8
            logger.warning("Ranging market → directional trade confidence −8%")

        # ── 8b. HTF Confirmation ──────────────────────────────────────────────
        atr_pct = ta_results.get("atr", {}).get("pct", 1.0)
        adx_val = regime.get("adx", 20)

        if ta_results_htf:
            htf_comp = ta_results_htf.get("composite", {})
            htf_dir  = htf_comp.get("direction", "NEUTRAL")
            if final_dir != "NEUTRAL" and htf_dir != "NEUTRAL" and htf_dir != final_dir:
                penalty += 12
                logger.warning(f"HTF Contradiction! Signal is {final_dir} but HTF is {htf_dir} → −12%")
            elif final_dir != "NEUTRAL" and final_dir == htf_dir:
                raw_score = min(100, raw_score + 5)
                logger.info(f"HTF Confirmation! Both timeframes aligned on {final_dir} → +5%")

        # ── 8c. Volatility Filter ─────────────────────────────────────────────
        if atr_pct > 3.0:  # High volatility / panic
            penalty += 10
            logger.warning(f"Extreme volatility (ATR {atr_pct:.1f}%) → −10% confidence")

        # ── 8d. Trend Strength Filter ─────────────────────────────────────────
        if adx_val < 20 and final_dir != "NEUTRAL":
            penalty += 5
            logger.warning(f"Weak trend (ADX {adx_val:.1f}) → −5% confidence")

        confidence = round(max(0, min(98.0, raw_score - penalty)), 2)
        should_trade = confidence >= self.threshold and final_dir in ("BUY", "SELL")

        # ── 9. Adaptive Risk Parameters ────────────────────────────────────────
        # Tighter SL in strong trends, wider in weaker ones
        sl_multiplier = 1.2 if adx_val > 30 else 1.8
        stop_loss_pct   = round(max(0.8, min(5.0, atr_pct * sl_multiplier)), 2)
        take_profit_pct = round(stop_loss_pct * 2.2, 2)   # 2.2:1 R/R

        # ── 10. Reasoning Build ────────────────────────────────────────────────
        reasoning: List[str] = []
        if ml_dir != "NEUTRAL":
            reasoning.append(f"AI ML: {ml_dir} signal (Random Forest probability: {ml_score:.1f}%)")
        if ta_dir != "NEUTRAL":
            reasoning.append(f"TA: {ta_dir} signal ({ta_score:.0f}% score, {comp.get('bull_signals',0)}↑/{comp.get('bear_signals',0)}↓)")
        if pat_dir != "NEUTRAL":
            reasoning.append(f"Patterns: {pat_dir} — Regime: {regime.get('regime','?')} ADX {regime.get('adx',0):.1f}")
        bb = ta_results.get("bollinger", {})
        if bb.get("is_squeeze"):
            reasoning.append("Volatility: BB Squeeze detected (breakout imminent)")
        if htf_dir == final_dir and final_dir != "NEUTRAL":
            reasoning.append(f"Confirmation: Higher Timeframe ({htf_dir}) aligns with signal")
        fib = (pattern_results or {}).get("fibonacci", {})
        if fib.get("at_support"):
            reasoning.append(f"At Fibonacci support ({fib.get('nearest_fib',0)*100:.1f}% level)")
        if fib.get("at_resistance"):
            reasoning.append(f"At Fibonacci resistance ({fib.get('nearest_fib',0)*100:.1f}% level)")
        vp = (pattern_results or {}).get("volume_profile", {})
        if vp.get("poc"):
            reasoning.append(f"Volume POC: ${vp['poc']:.2f} ({vp.get('price_vs_poc','?')} POC, VA={'in' if vp.get('in_value_area') else 'out'})")
        if div.get("bullish_divergence"):
            reasoning.append("RSI Bullish Divergence detected ↗")
        if div.get("bearish_divergence"):
            reasoning.append("RSI Bearish Divergence detected ↘")
        if sent_dir != "NEUTRAL":
            reasoning.append(f"Sentiment: {sent_dir} ({sent_pct:.0f}%)")
        if mtf_dir != "NEUTRAL":
            reasoning.append(f"Multi-timeframe: {mtf_dir} ({mtf_score:.0f}%)")
        candle_patterns = ta_results.get("candle_patterns", [])
        if candle_patterns:
            reasoning.append(f"Candle patterns: {', '.join(candle_patterns)}")
        ichi = ta_results.get("ichimoku", {})
        if ichi.get("tenkan", 0) > ichi.get("kijun", 1):
            reasoning.append("Ichimoku: Tenkan > Kijun (bullish cross)")

        result = {
            "symbol":            symbol,
            "direction":         final_dir,
            "confidence":        confidence,
            "should_trade":      should_trade,
            "threshold":         self.threshold,
            "stop_loss_pct":     stop_loss_pct,
            "take_profit_pct":   take_profit_pct,
            "reasoning":         reasoning,
            "component_scores": {
                "ml_ai":          round(ml_score,    2),
                "technical":      round(ta_score,    2),
                "patterns":       round(pat_score,   2),
                "sentiment":      round(sent_pct,    2),
                "momentum_mtf":   round(mtf_score,   2),
                "microstructure": round(micro_score, 2),
            },
            "direction_votes": {
                "BUY":     buy_votes,
                "SELL":    sell_votes,
                "NEUTRAL": max(0, 5 - buy_votes - sell_votes),
            },
            "pattern_summary": {
                "regime":            regime.get("regime", "?"),
                "adx":               round(regime.get("adx", 0), 2),
                "di_plus":           round(regime.get("di_plus", 0), 2),
                "di_minus":          round(regime.get("di_minus", 0), 2),
                "tradeable":         regime.get("tradeable", True),
                "bullish_div":       div.get("bullish_divergence", False),
                "bearish_div":       div.get("bearish_divergence", False),
                "at_fib_support":    fib.get("at_support", False),
                "at_fib_resistance": fib.get("at_resistance", False),
                "nearest_fib":       fib.get("nearest_fib", None),
                "poc":               vp.get("poc", 0),
                "in_value_area":     vp.get("in_value_area", False),
            },
            "raw_score":  round(raw_score, 2),
            "penalty":    round(penalty, 2),
        }

        emoji  = "🚀" if final_dir == "BUY" else ("🔻" if final_dir == "SELL" else "⏸️")
        status = "✅ TRADE SIGNAL" if should_trade else "🔍 Monitoring"
        logger.signal(
            f"{status} [{symbol}] {emoji} {final_dir} | "
            f"Confidence: {confidence}% (raw:{raw_score:.1f}% pen:{penalty:.1f}%) | "
            f"Threshold: {self.threshold}% | SL: {stop_loss_pct}% TP: {take_profit_pct}% | "
            f"Votes: {buy_votes}↑/{sell_votes}↓",
            result,
        )
        if not should_trade:
            logger.thinking(
                f"Below threshold ({confidence}% < {self.threshold}%) — "
                f"monitoring {symbol}, next cycle will re-evaluate"
            )
        return result
