"""
BitBot Market Context Analyzer
Tracks global market health (BTC/ETH regimes) to provide 'Beta' context
for individual asset predictions.
"""

import asyncio
import pandas as pd
from typing import Dict, Any, Optional
from bot import logger
from bot.patterns import detect_market_regime
from bot.exchange import exchange_client

class MarketContext:
    def __init__(self):
        self.btc_status: Dict[str, Any] = {"regime": "UNKNOWN", "adx": 0}
        self.eth_status: Dict[str, Any] = {"regime": "UNKNOWN", "adx": 0}
        self.market_score: float = 50.0 # 0 (Crash) to 100 (Moon)
        self.last_update: Optional[float] = None

    async def update(self):
        """Fetch and analyze BTC and ETH to determine global market sentiment."""
        try:
            logger.analysis("🌐 Synchronizing Global Market Context (BTC & ETH)...")
            
            # Fetch BTC and ETH 1h data for macro context
            loop = asyncio.get_event_loop()
            btc_df = await loop.run_in_executor(None, exchange_client.fetch_ohlcv, "BTC/USDT", "1h", 100)
            eth_df = await loop.run_in_executor(None, exchange_client.fetch_ohlcv, "ETH/USDT", "1h", 100)

            if btc_df is not None and not btc_df.empty:
                self.btc_status = detect_market_regime(btc_df)
            
            if eth_df is not None and not eth_df.empty:
                self.eth_status = detect_market_regime(eth_df)

            self._calculate_market_score()
            logger.info(f"🌐 Market Context Synced: Score {self.market_score:.1f} | BTC: {self.btc_status.get('regime')} | ETH: {self.eth_status.get('regime')}")

        except Exception as e:
            logger.error(f"Failed to update market context: {e}")

    def _calculate_market_score(self):
        """Synthesize BTC and ETH regimes into a single 0-100 score."""
        score = 50.0
        
        # BTC Weight (60%)
        btc_regime = self.btc_status.get("regime", "UNKNOWN")
        if btc_regime == "TRENDING_UP": score += 20
        elif btc_regime == "TRENDING_DOWN": score -= 25
        elif btc_regime == "RANGING": score -= 5
        
        # ETH Weight (40%)
        eth_regime = self.eth_status.get("regime", "UNKNOWN")
        if eth_regime == "TRENDING_UP": score += 10
        elif eth_regime == "TRENDING_DOWN": score -= 15
        
        # Add momentum from ADX
        btc_adx = self.btc_status.get("adx", 0)
        if btc_regime == "TRENDING_UP" and btc_adx > 30: score += 5
        if btc_regime == "TRENDING_DOWN" and btc_adx > 30: score -= 10
        
        self.market_score = max(0, min(100, score))

    def get_context_penalty(self, direction: str) -> float:
        """Returns a penalty (0-20) if the market context contradicts the signal."""
        penalty = 0.0
        if direction == "BUY":
            if self.market_score < 40:
                penalty = (40 - self.market_score) * 0.5
            if self.btc_status.get("regime") == "TRENDING_DOWN":
                penalty += 10
        elif direction == "SELL":
            if self.market_score > 60:
                penalty = (self.market_score - 60) * 0.5
            if self.btc_status.get("regime") == "TRENDING_UP":
                penalty += 10
        
        return round(min(25, penalty), 2)

market_context = MarketContext()
