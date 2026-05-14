"""
BitBot Trading Engine — Main Orchestrator
Runs the full analysis → prediction → trade cycle on a schedule.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from bot import logger
from bot.analyzer import TechnicalAnalyzer
from bot.predictor import Predictor
from bot.patterns import pattern_engine
from bot.database import set_setting, get_setting
from bot.ml import ml_engine
from bot.news import news_analyzer
from bot.exchange import exchange_client
from bot.risk import risk_manager
from bot.logger import broadcast_event
from config import settings


class BotStatus(str, Enum):
    IDLE       = "idle"
    RUNNING    = "running"
    ANALYZING  = "analyzing"
    WAITING    = "waiting"
    PAUSED     = "paused"
    ERROR      = "error"


# ─── Timeframe pairs: (primary, higher, lower) ────────────────────────────────
TIMEFRAME_MAP = {
    "1m":  ("1m",  "5m",  None),
    "5m":  ("5m",  "15m", "1m"),
    "15m": ("15m", "1h",  "5m"),
    "30m": ("30m", "1h",  "15m"),
    "1h":  ("1h",  "4h",  "15m"),
    "4h":  ("4h",  "1d",  "1h"),
}

# How often to run the cycle per timeframe (seconds)
CYCLE_INTERVAL = {
    "1m":  60,
    "5m":  300,
    "15m": 900,
    "30m": 1800,
    "1h":  3600,
    "4h":  14400,
}


class TradingEngine:
    def __init__(self):
        self.status: BotStatus = BotStatus.IDLE
        self.status_message: str = "Bot is idle"
        self.symbol    = get_setting("symbol", settings.symbol)
        self.timeframe = get_setting("timeframe", settings.timeframe)
        self.running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self.analyzer = TechnicalAnalyzer()
        self.predictor = Predictor(confidence_threshold=get_setting("confidence_threshold", settings.confidence_threshold))
        self.cycle_count: int = 0
        self.last_analysis: Dict[str, Any] = {}
        self.last_prediction: Dict[str, Any] = {}
        self.started_at: Optional[str] = None
        self._live_update_task: Optional[asyncio.Task] = None
        self.last_df: Optional[Any] = None  # Store last fetched DF for live updates

    # ─── Control ──────────────────────────────────────────────────────────────

    def start(self, symbol: str = None, timeframe: str = None) -> bool:
        if self.running:
            logger.warning("Bot is already running")
            return False

        self.symbol    = symbol    or self.symbol
        self.timeframe = timeframe or self.timeframe
        self.running   = True
        self.started_at = datetime.utcnow().isoformat() + "Z"

        logger.success(
            f"🚀 BitBot started | Symbol: {self.symbol} | TF: {self.timeframe} "
            f"| Confidence threshold: {self.predictor.threshold}%"
        )

        self._task         = asyncio.ensure_future(self._run_loop())
        self._monitor_task = asyncio.ensure_future(self._monitor_positions())
        self._live_update_task = asyncio.ensure_future(self._run_live_update())
        return True

    def stop(self) -> bool:
        if not self.running:
            return False
        self.running = False
        if self._task:
            self._task.cancel()
        if self._monitor_task:
            self._monitor_task.cancel()
        if self._live_update_task:
            self._live_update_task.cancel()
        self._set_status(BotStatus.IDLE, "Bot stopped by user")
        logger.info("⏹️ Bot stopped")
        return True

    def pause(self) -> bool:
        if not self.running:
            return False
        self.running = False
        self._set_status(BotStatus.PAUSED, "Bot paused — no new trades")
        logger.info("⏸️ Bot paused")
        return True

    def resume(self) -> bool:
        if self.status != BotStatus.PAUSED:
            return False
        self.running = True
        self._task = asyncio.ensure_future(self._run_loop())
        self._set_status(BotStatus.RUNNING, "Bot resumed")
        logger.success("▶️ Bot resumed")
        return True

    def update_settings(self, **kwargs):
        if "symbol" in kwargs:
            self.symbol = kwargs["symbol"]
            set_setting("symbol", self.symbol)
        if "timeframe" in kwargs:
            self.timeframe = kwargs["timeframe"]
            set_setting("timeframe", self.timeframe)
        if "confidence_threshold" in kwargs:
            self.predictor.threshold = float(kwargs["confidence_threshold"])
            set_setting("confidence_threshold", self.predictor.threshold)
        if "trade_amount_usdt" in kwargs:
            settings.trade_amount_usdt = float(kwargs["trade_amount_usdt"])
            set_setting("trade_amount_usdt", settings.trade_amount_usdt)
        if "stop_loss_percent" in kwargs:
            settings.stop_loss_percent = float(kwargs["stop_loss_percent"])
            set_setting("stop_loss_percent", settings.stop_loss_percent)
        if "take_profit_percent" in kwargs:
            settings.take_profit_percent = float(kwargs["take_profit_percent"])
            set_setting("take_profit_percent", settings.take_profit_percent)
        if "max_open_trades" in kwargs:
            settings.max_open_trades = int(kwargs["max_open_trades"])
            set_setting("max_open_trades", settings.max_open_trades)
        logger.info(f"Settings updated and saved to DB: {kwargs}")

    # ─── Main Loop ────────────────────────────────────────────────────────────

    async def _run_loop(self):
        self._set_status(BotStatus.RUNNING, "Starting analysis loop...")

        while self.running:
            try:
                # Expert Logic: Align with candle close (e.g. run at 10:05:01 for 5m TF)
                now = datetime.utcnow().timestamp()
                interval = CYCLE_INTERVAL.get(self.timeframe, 60)
                wait_time = interval - (now % interval) + 1 # +1s buffer for exchange data
                
                wait_msg = f"⏳ Waiting {wait_time:.1f}s to align with next {self.timeframe} candle close..."
                self._set_status(BotStatus.WAITING, wait_msg)
                logger.info(wait_msg)
                
                await asyncio.sleep(wait_time)
                
                if not self.running: break
                
                await self._run_cycle()
                self.cycle_count += 1
                await broadcast_event("cycle_complete", {"cycle": self.cycle_count})

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Engine loop error: {e}")
                self._set_status(BotStatus.ERROR, f"Error: {e}")
                await asyncio.sleep(30)

    async def _run_cycle(self):
        """One complete analysis → predict → (optional) trade cycle."""
        self._set_status(BotStatus.ANALYZING, f"📊 Analyzing {self.symbol}...")

        primary, htf, ltf = TIMEFRAME_MAP.get(self.timeframe, (self.timeframe, None, None))

        # ── Guard: Ensure exchange is connected (fallback to public if needed) ────────
        if not exchange_client.connected:
            logger.warning("No active exchange connection. Attempting public API fallback...")
            if not exchange_client.ensure_connected():
                self._set_status(BotStatus.ERROR, "Exchange connection failed. Check API keys.")
                return

        # ── 1. Fetch OHLCV (primary + HTF) ────────────────────────────────────
        # Professional: Fetch 500 candles to ensure EMA200/MA200 accuracy
        logger.analysis(f"Fetching OHLCV data [{self.symbol}]...")
        df_primary = await asyncio.get_event_loop().run_in_executor(
            None, exchange_client.fetch_ohlcv, self.symbol, primary, 500
        )
        df_htf = await asyncio.get_event_loop().run_in_executor(
            None, exchange_client.fetch_ohlcv, self.symbol, htf, 200
        ) if htf else None
        df_ltf = await asyncio.get_event_loop().run_in_executor(
            None, exchange_client.fetch_ohlcv, self.symbol, ltf, 200
        ) if ltf else None

        if df_primary is None or df_primary.empty:
            logger.error(f"No OHLCV data received for {self.symbol}")
            return

        # ── 2. Technical Analysis ────────────────────────────────────────────
        ta_primary = await asyncio.get_event_loop().run_in_executor(
            None, self.analyzer.analyze, df_primary, self.symbol
        )
        ta_htf = await asyncio.get_event_loop().run_in_executor(
            None, self.analyzer.analyze, df_htf, f"{self.symbol}[{htf}]"
        ) if df_htf is not None else {}
        ta_ltf = await asyncio.get_event_loop().run_in_executor(
            None, self.analyzer.analyze, df_ltf, f"{self.symbol}[{ltf}]"
        ) if df_ltf is not None else {}

        self.last_analysis = ta_primary
        self.last_df = df_primary

        # ── 3. News Sentiment ────────────────────────────────────────────────
        news_data = await news_analyzer.analyze(self.symbol)

        # ── 4. Order Book Microstructure ─────────────────────────────────────
        logger.analysis("Fetching deep order book microstructure...")
        orderbook = await asyncio.get_event_loop().run_in_executor(
            None, exchange_client.fetch_orderbook, self.symbol, 100
        )

        # ── 4b. Advanced Pattern Analysis ────────────────────────────────────
        pattern_data = await asyncio.get_event_loop().run_in_executor(
            None, pattern_engine.analyze, df_primary, self.symbol
        )

        # ── 4c. ML Random Forest Analysis ────────────────────────────────────
        ml_data = await asyncio.get_event_loop().run_in_executor(
            None, ml_engine.predict, df_primary
        )

        # ── 5. AI Prediction ─────────────────────────────────────────────────
        prediction = self.predictor.predict(
            ta_results=ta_primary,
            ta_results_htf=ta_htf,
            ta_results_ltf=ta_ltf,
            news_results=news_data,
            orderbook=orderbook,
            pattern_results=pattern_data,
            ml_results=ml_data,
            symbol=self.symbol,
        )
        self.last_prediction = prediction

        # Broadcast updated analysis to frontend
        await broadcast_event("analysis_update", {
            "ta": ta_primary.get("composite"),
            "prediction": prediction,
            "news": news_data,
            "patterns": pattern_data,
            "price": df_primary["close"].iloc[-1] if not df_primary.empty else 0,
            "candles": self._df_to_candles(df_primary, limit=100),
        })

        # ── 6. Check SL/TP on open positions ─────────────────────────────────
        ticker = exchange_client.fetch_ticker(self.symbol)
        current_price = ticker.get("last", 0)
        if current_price:
            closed = risk_manager.check_positions({self.symbol: current_price})
            for c in closed:
                await broadcast_event("position_closed", c)

        # ── 7. Execute Trade if Signal is Confident ──────────────────────────
            amount_usdt = settings.trade_amount_usdt

            # Expert Risk Guard: Check balance before execution
            balance = exchange_client.fetch_balance()
            usdt_avail = balance.get("USDT", 0)
            if usdt_avail < amount_usdt:
                logger.warning(f"Insufficient funds for trade: Have ${usdt_avail:.2f}, need ${amount_usdt:.2f}")
                return

            # Expert Logic: Get ATR for volatility-adjusted risk
            atr_val = ta_primary.get("atr", {}).get("value")
            
            logger.trade(
                f"🎯 HIGH CONFIDENCE SIGNAL! {direction} @ {current_price} "
                f"| Confidence: {confidence}% | Executing trade..."
            )

            order = None
            if direction == "BUY":
                order = await asyncio.get_event_loop().run_in_executor(
                    None, exchange_client.create_market_buy, self.symbol, amount_usdt
                )
            elif direction == "SELL":
                # Expert: Handle SHORT (passing amount_usdt specifically)
                order = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: exchange_client.create_market_sell(self.symbol, amount_usdt=amount_usdt)
                )

            if order:
                pos = risk_manager.open_position(
                    symbol=self.symbol,
                    direction=direction,
                    entry_price=current_price,
                    amount_usdt=amount_usdt,
                    stop_loss_pct=sl_pct,
                    take_profit_pct=tp_pct,
                    confidence=confidence,
                    atr=atr_val,
                    order_id=order.get("id", ""),
                )
                if pos:
                    await broadcast_event("position_opened", pos.to_dict())
        else:
            self._set_status(
                BotStatus.WAITING,
                f"🔍 Monitoring {self.symbol} — confidence {prediction.get('confidence', 0):.1f}% "
                f"(need ≥ {self.predictor.threshold}%) — next scan in {CYCLE_INTERVAL.get(self.timeframe,900)}s"
            )

    # ─── Position Monitor ─────────────────────────────────────────────────────

    async def _monitor_positions(self):
        """Monitors open positions every 30 seconds for SL/TP."""
        while True:
            try:
                await asyncio.sleep(30)
                open_pos = risk_manager.get_open_positions()
                if not open_pos:
                    continue
                ticker = exchange_client.fetch_ticker(self.symbol)
                price = ticker.get("last", 0)
                if price:
                    closed = risk_manager.check_positions({self.symbol: price})
                    for c in closed:
                        await broadcast_event("position_closed", c)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Position monitor error: {e}")

    async def _run_live_update(self):
        """Fetches current price and updates the last candle every 2 seconds."""
        while self.running:
            try:
                # Respect rate limits: 2 seconds is enough for dashboard updates
                await asyncio.sleep(2.0)
                if not self.running:
                    break

                # Fetch last 2 candles to ensure we have the most recent closed and open one
                df = await asyncio.get_event_loop().run_in_executor(
                    None, exchange_client.fetch_ohlcv, self.symbol, self.timeframe, 2
                )
                
                if df.empty:
                    continue

                last_row = df.iloc[-1]
                price = last_row["close"]
                
                candle_data = {
                    "time": int(df.index[-1].timestamp()),
                    "open": last_row["open"],
                    "high": last_row["high"],
                    "low":  last_row["low"],
                    "close": last_row["close"],
                    "volume": last_row["volume"],
                }

                # 3. Broadcast
                await broadcast_event("price_update", {
                    "price": price,
                    "candle": candle_data,
                    "symbol": self.symbol
                })

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Live update error: {e}")

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _set_status(self, status: BotStatus, message: str):
        self.status = status
        self.status_message = message
        asyncio.ensure_future(broadcast_event("status_update", {
            "status": status.value,
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }))

    def _df_to_candles(self, df, limit: int = 100) -> list:
        df = df.tail(limit).reset_index()
        return [
            {
                "time": int(row["timestamp"].timestamp()),
                "open": row["open"],
                "high": row["high"],
                "low":  row["low"],
                "close": row["close"],
                "volume": row["volume"],
            }
            for _, row in df.iterrows()
        ]

    def get_state(self) -> Dict[str, Any]:
        return {
            "status":        self.status.value,
            "status_message": self.status_message,
            "symbol":        self.symbol,
            "timeframe":     self.timeframe,
            "running":       self.running,
            "cycle_count":   self.cycle_count,
            "started_at":    self.started_at,
            "confidence_threshold": self.predictor.threshold,
            "last_prediction": self.last_prediction,
            "open_positions": risk_manager.get_open_positions(),
            "stats":          risk_manager.get_stats(),
            "exchange":       exchange_client.exchange_id,
            "exchange_connected": exchange_client.connected,
            "paper_mode":         exchange_client.paper_mode,
        }


# Singleton
engine = TradingEngine()
