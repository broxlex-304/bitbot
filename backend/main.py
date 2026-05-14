"""
BitBot FastAPI Server
REST API + WebSocket for real-time dashboard communication.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List

from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bot.engine import engine, BotStatus
from bot.exchange import exchange_client
from bot.risk import risk_manager
from bot.scanner import scanner
from bot.alerts import telegram_alerts
from bot import logger
from bot.logger import register_ws_client, unregister_ws_client, get_logs, broadcast_event, _dumps
from config import settings


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🔧 BitBot API starting up...")
    
    # Try loading encrypted credentials from DB first
    from bot.database import get_setting
    creds = get_setting("api_credentials", encrypted=True)
    
    if creds:
        exchange_client.connect(creds["id"], creds["key"], creds["secret"])
    elif settings.api_key:
        exchange_client.connect()
    else:
        exchange_client.connect_public()
        
    scanner.start()
    telegram_alerts.start()
    asyncio.create_task(telegram_alerts.send_message("🚀 <b>BitBot Cloud Engine Online</b>\nMonitoring markets..."))
    yield
    logger.info("BitBot API shutting down...")
    engine.stop()
    scanner.stop()


app = FastAPI(
    title="BitBot Trading API",
    description="AI-powered crypto trading bot API",
    version="1.0.0",
    lifespan=lifespan,
)

# Custom JSON Response to handle numpy types
from fastapi.responses import JSONResponse
import json
import numpy as np

def clean_data(obj):
    """Recursively convert numpy types to python types."""
    if isinstance(obj, dict):
        return {k: clean_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_data(v) for v in obj]
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat() + "Z"
    return obj

class BitBotJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return _dumps(clean_data(content)).encode("utf-8")

app.default_response_class = BitBotJSONResponse

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Models ───────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    symbol: Optional[str] = None
    timeframe: Optional[str] = None

class ExchangeConnectRequest(BaseModel):
    exchange_id: str
    api_key: str
    api_secret: str

class SettingsUpdateRequest(BaseModel):
    confidence_threshold: Optional[float] = None
    trade_amount_usdt: Optional[float] = None
    stop_loss_percent: Optional[float] = None
    take_profit_percent: Optional[float] = None
    max_open_trades: Optional[int] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None

class ClosePositionRequest(BaseModel):
    position_id: str


# ─── Bot Control Endpoints ────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    """Full bot state snapshot."""
    state = engine.get_state()
    state["paper_mode"] = exchange_client.paper_mode
    return state

@app.post("/api/bot/start")
async def start_bot(req: StartRequest):
    """Start the trading bot."""
    if not exchange_client.connected and settings.api_key:
        exchange_client.connect()
    ok = engine.start(symbol=req.symbol, timeframe=req.timeframe)
    return {"success": ok, "message": "Bot started" if ok else "Bot already running"}

@app.post("/api/bot/stop")
async def stop_bot():
    ok = engine.stop()
    return {"success": ok, "message": "Bot stopped" if ok else "Bot was not running"}

@app.post("/api/bot/pause")
async def pause_bot():
    ok = engine.pause()
    return {"success": ok, "message": "Bot paused" if ok else "Bot not running"}

@app.post("/api/bot/resume")
async def resume_bot():
    ok = engine.resume()
    return {"success": ok, "message": "Bot resumed" if ok else "Bot not paused"}

@app.post("/api/bot/analyze-now")
async def analyze_now():
    """Trigger an immediate analysis cycle."""
    asyncio.ensure_future(engine._run_cycle())
    return {"success": True, "message": "Analysis triggered"}

@app.get("/api/bot/prediction")
async def get_prediction():
    return engine.last_prediction or {"message": "No prediction yet"}

@app.get("/api/bot/analysis")
async def get_analysis():
    return engine.last_analysis or {"message": "No analysis yet"}

@app.get("/api/scanner")
async def get_scanner_results():
    """Returns top scanned coins sorted by confidence."""
    return {"results": scanner.scan_results}


# ─── Settings ─────────────────────────────────────────────────────────────────

@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    updates = {k: v for k, v in req.dict().items() if v is not None}
    engine.update_settings(**updates)
    if "max_open_trades" in updates:
        settings.max_open_trades = updates["max_open_trades"]
    return {"success": True, "updated": updates}

@app.get("/api/settings")
async def get_settings():
    return {
        "symbol": engine.symbol,
        "timeframe": engine.timeframe,
        "confidence_threshold": engine.predictor.threshold,
        "trade_amount_usdt": settings.trade_amount_usdt,
        "stop_loss_percent": settings.stop_loss_percent,
        "take_profit_percent": settings.take_profit_percent,
        "max_open_trades": settings.max_open_trades,
        "exchange_id": settings.exchange_id,
    }


# ─── Exchange ─────────────────────────────────────────────────────────────────

@app.post("/api/exchange/connect")
async def connect_exchange(req: ExchangeConnectRequest):
    ok, message = exchange_client.connect(req.exchange_id, req.api_key, req.api_secret)
    return {"success": ok, "message": message, "exchange": req.exchange_id}

@app.get("/api/exchange/supported")
async def get_supported_exchanges():
    return {"exchanges": exchange_client.get_supported_exchanges()}

@app.get("/api/exchange/symbols")
async def get_symbols():
    if exchange_client.exchange and exchange_client.exchange.markets:
        # Get all USDT perpetual swap markets
        symbols = [s for s, m in exchange_client.exchange.markets.items() if m.get('quote') == 'USDT' and (m.get('swap') or m.get('future'))]
        if not symbols: # fallback to any USDT market
            symbols = [s for s in exchange_client.exchange.markets.keys() if '/USDT' in s]
        return {"symbols": sorted(list(set(symbols)))}
    return {"symbols": ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT', 'DOGE/USDT']}

@app.get("/api/exchange/balance")
async def get_balance():
    return exchange_client.fetch_balance()

@app.get("/api/exchange/ticker/{symbol:path}")
async def get_ticker(symbol: str):
    symbol = symbol.replace(".P", "").replace(".p", "").replace("-", "/")
    return exchange_client.fetch_ticker(symbol)

@app.get("/api/exchange/candles/{symbol:path}")
async def get_candles(symbol: str, timeframe: str = "15m", limit: int = 100):
    symbol = symbol.replace(".P", "").replace(".p", "").replace("-", "/")
    df = exchange_client.fetch_ohlcv(symbol, timeframe, limit)
    if df.empty:
        return []
    df_reset = df.reset_index()
    return [
        {
            "time": int(row["timestamp"].timestamp()),
            "open": row["open"], "high": row["high"],
            "low": row["low"],   "close": row["close"],
            "volume": row["volume"],
        }
        for _, row in df_reset.iterrows()
    ]


# ─── Positions & Stats ────────────────────────────────────────────────────────

@app.get("/api/positions")
async def get_positions():
    return {
        "open":    risk_manager.get_open_positions(),
        "history": risk_manager.trade_history[-20:],
    }

@app.post("/api/positions/close")
async def close_position(req: ClosePositionRequest):
    ticker = exchange_client.fetch_ticker(engine.symbol)
    price  = ticker.get("last", 0)
    result = risk_manager.close_position_manual(req.position_id, price)
    if not result:
        raise HTTPException(status_code=404, detail="Position not found or already closed")
    return {"success": True, "position": result}

@app.get("/api/stats")
async def get_stats():
    return risk_manager.get_stats()


# ─── Logs ─────────────────────────────────────────────────────────────────────

@app.get("/api/logs")
async def get_logs_endpoint(limit: int = 100):
    return {"logs": get_logs(limit)}


# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    register_ws_client(ws)
    logger.info(f"WebSocket client connected")

    try:
        # Send initial state immediately
        import json
        await ws.send_text(_dumps({
            "type": "init",
            "data": engine.get_state(),
        }))
        await ws.send_text(_dumps({
            "type": "logs",
            "data": get_logs(50),
        }))

        # Keep alive
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30)
                # Handle ping/pong
                if data == "ping":
                    await ws.send_text("pong")
            except asyncio.TimeoutError:
                # Send heartbeat
                await ws.send_text(_dumps({
                    "type": "heartbeat",
                    "data": {
                        "status": engine.status.value,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                }))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        unregister_ws_client(ws)
        logger.info("WebSocket client disconnected")


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "bot": engine.status.value}
