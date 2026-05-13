"""
BitBot Activity Logger
Stores structured bot logs and broadcasts to WebSocket clients.
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
import os
from collections import deque
import json
import numpy as np
from bot.database import SessionLocal, DBLog

LOG_FILE = "bot_logs.json"

# In-memory log store (last 500 entries)
_log_buffer: deque = deque(maxlen=500)
_ws_clients: set = set()
_id_counter: int = 0

LOG_LEVELS = {
    "info": "ℹ️",
    "success": "✅",
    "warning": "⚠️",
    "error": "❌",
    "trade": "💰",
    "analysis": "📊",
    "news": "📰",
    "signal": "🎯",
    "thinking": "🧠",
}

class BitBotJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle numpy types and other objects."""
    def default(self, obj):
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                            np.int16, np.int32, np.int64, np.uint8,
                            np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.float16, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.bool_,)):
            return bool(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        elif isinstance(obj, datetime):
            return obj.isoformat() + "Z"
        return super(BitBotJSONEncoder, self).default(obj)

def _dumps(obj: Any) -> str:
    return json.dumps(obj, cls=BitBotJSONEncoder)

def clean_data(obj: Any) -> Any:
    """Recursively convert numpy types to python types."""
    if isinstance(obj, dict):
        return {k: clean_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_data(v) for v in obj]
    elif isinstance(obj, (np.integer, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat() + "Z"
    return obj

def _make_entry(level: str, message: str, data: Optional[Dict] = None) -> Dict[str, Any]:
    global _id_counter
    _id_counter += 1
    # Sanitize data before storing
    clean_payload = clean_data(data) if data else {}
    return {
        "id": f"{datetime.utcnow().timestamp()}-{_id_counter}",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "icon": LOG_LEVELS.get(level, "ℹ️"),
        "message": message,
        "data": clean_payload,
    }

def _load_logs():
    try:
        db = SessionLocal()
        # Fetch last 500 logs from DB
        db_logs = db.query(DBLog).order_by(DBLog.id.desc()).limit(500).all()
        db.close()
        for l in reversed(db_logs):
            _log_buffer.append({
                "id": str(l.id),
                "timestamp": l.timestamp.isoformat() + "Z",
                "level": l.level,
                "icon": l.icon,
                "message": l.message,
                "data": l.data
            })
    except Exception as e:
        print(f"Error loading logs: {e}")

_load_logs()

def log(level: str, message: str, data: Optional[Dict] = None):
    entry = _make_entry(level, message, data)
    _log_buffer.append(entry)
    
    try:
        db = SessionLocal()
        db_log = DBLog(
            level=level,
            icon=entry["icon"],
            message=message,
            data=entry["data"]
        )
        db.add(db_log)
        db.commit()
        db.close()
    except Exception as e:
        print(f"Error saving log to DB: {e}")

    # Fire-and-forget broadcast
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_broadcast(entry))
    except RuntimeError:
        pass
    return entry

def info(msg: str, data: Optional[Dict] = None):    return log("info", msg, data)
def success(msg: str, data: Optional[Dict] = None): return log("success", msg, data)
def warning(msg: str, data: Optional[Dict] = None): return log("warning", msg, data)
def error(msg: str, data: Optional[Dict] = None):   return log("error", msg, data)
def trade(msg: str, data: Optional[Dict] = None):   return log("trade", msg, data)
def analysis(msg: str, data: Optional[Dict] = None):return log("analysis", msg, data)
def news(msg: str, data: Optional[Dict] = None):    return log("news", msg, data)
def signal(msg: str, data: Optional[Dict] = None):  return log("signal", msg, data)
def thinking(msg: str, data: Optional[Dict] = None):return log("thinking", msg, data)

def get_logs(limit: int = 100) -> List[Dict]:
    logs = list(_log_buffer)
    return logs[-limit:]

def register_ws_client(ws):
    _ws_clients.add(ws)

def unregister_ws_client(ws):
    _ws_clients.discard(ws)

async def _broadcast(entry: Dict):
    if not _ws_clients:
        return
    try:
        payload = _dumps({"type": "log", "data": entry})
        dead = set()
        for ws in _ws_clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            _ws_clients.discard(ws)
    except Exception as e:
        print(f"Broadcast error: {e}")

async def broadcast_event(event_type: str, data: Dict):
    """Broadcast any structured event to all WS clients."""
    if not _ws_clients:
        return
    try:
        payload = _dumps({"type": event_type, "data": data})
        dead = set()
        for ws in _ws_clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            _ws_clients.discard(ws)
    except Exception as e:
        print(f"Event broadcast error: {e}")
