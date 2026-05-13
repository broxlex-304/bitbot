import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd
from bot import logger
from bot.exchange import exchange_client
from bot.analyzer import TechnicalAnalyzer
from bot.predictor import Predictor
from bot.patterns import pattern_engine
from bot.database import SessionLocal, DBScannerResult

class MarketScanner:
    def __init__(self):
        self.analyzer = TechnicalAnalyzer()
        self.predictor = Predictor(confidence_threshold=0)
        self.scan_results: List[Dict[str, Any]] = []
        self.running = False
        self._task = None
        self.target_symbols = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 
            'XRP/USDT', 'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 
            'DOT/USDT', 'MATIC/USDT', 'LINK/USDT', 'UNI/USDT',
            'LTC/USDT', 'BCH/USDT', 'APT/USDT'
        ]
        self._load_results()

    def _save_result(self, res: Dict):
        try:
            db = SessionLocal()
            existing = db.query(DBScannerResult).filter(DBScannerResult.symbol == res["symbol"]).first()
            if existing:
                existing.confidence = res["confidence"]
                existing.direction = res["direction"]
                existing.price = res["price"]
                existing.score = res["score"]
                existing.updated_at = datetime.utcnow()
            else:
                db_res = DBScannerResult(**res)
                db.add(db_res)
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"DB Error saving scanner result: {e}")

    def _load_results(self):
        try:
            db = SessionLocal()
            db_results = db.query(DBScannerResult).all()
            db.close()
            self.scan_results = [
                {
                    "symbol": r.symbol,
                    "confidence": r.confidence,
                    "direction": r.direction,
                    "price": r.price,
                    "score": r.score
                } for r in db_results
            ]
            logger.info(f"Loaded {len(self.scan_results)} scanner results from database.")
        except Exception as e:
            logger.error(f"DB Error loading scanner results: {e}")

    def start(self):
        if self.running: return
        self.running = True
        self._task = asyncio.ensure_future(self._scan_loop())
        logger.info("Market Scanner started.")

    def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()

    async def _scan_loop(self):
        while self.running:
            try:
                for symbol in self.target_symbols:
                    if not self.running: break
                    
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, exchange_client.fetch_ohlcv, symbol, "15m", 150
                    )
                    if df.empty:
                        continue
                        
                    ta = await asyncio.get_event_loop().run_in_executor(
                        None, self.analyzer.analyze, df, symbol
                    )
                    pat = await asyncio.get_event_loop().run_in_executor(
                        None, pattern_engine.analyze, df, symbol
                    )
                    
                    pred = self.predictor.predict(
                        ta_results=ta,
                        pattern_results=pat,
                        symbol=symbol
                    )
                    
                    res = {
                        "symbol": symbol,
                        "confidence": pred.get("confidence", 0),
                        "direction": pred.get("direction", "NEUTRAL"),
                        "price": float(df["close"].iloc[-1]),
                        "score": ta.get("composite", {}).get("score", 50)
                    }
                    
                    found = False
                    for i, existing in enumerate(self.scan_results):
                        if existing["symbol"] == symbol:
                            self.scan_results[i] = res
                            found = True
                            break
                    if not found:
                        self.scan_results.append(res)
                    
                    self._save_result(res)
                    await asyncio.sleep(1)
                
                await asyncio.sleep(300)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scanner error: {e}")
                await asyncio.sleep(60)

scanner = MarketScanner()
