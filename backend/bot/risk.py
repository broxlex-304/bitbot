import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from bot import logger
from bot.exchange import exchange_client
from bot.database import SessionLocal, DBPosition
from bot.alerts import telegram_alerts


@dataclass
class Position:
    id:              str
    symbol:          str
    direction:       str   # BUY / SELL
    entry_price:     float
    amount:          float  # base currency amount
    amount_usdt:     float
    stop_loss_price: float
    take_profit_price: float
    stop_loss_pct:   float
    take_profit_pct: float
    confidence:      float
    opened_at:       str   = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    order_id:        str   = ""
    status:          str   = "open"  # open | closed_tp | closed_sl | closed_manual
    close_price:     float = 0.0
    pnl_usdt:        float = 0.0
    pnl_pct:         float = 0.0
    closed_at:       str   = ""

    def to_dict(self) -> Dict:
        return asdict(self)


class RiskManager:
    def __init__(self):
        self.positions: Dict[str, Position] = {}   # id → Position
        self.trade_history: List[Dict] = []
        self.total_pnl_usdt: float = 0.0
        self.win_count: int = 0
        self.loss_count: int = 0
        self._load_state()

    def _save_pos(self, pos: Position):
        try:
            db = SessionLocal()
            existing = db.query(DBPosition).filter(DBPosition.id == pos.id).first()
            
            pos_data = pos.to_dict()
            # Convert ISO strings to datetime objects for SQLAlchemy
            if pos_data.get("opened_at"):
                pos_data["opened_at"] = datetime.fromisoformat(pos_data["opened_at"].replace("Z", ""))
            if pos_data.get("closed_at"):
                pos_data["closed_at"] = datetime.fromisoformat(pos_data["closed_at"].replace("Z", ""))
            else:
                pos_data["closed_at"] = None

            if existing:
                for key, value in pos_data.items():
                    setattr(existing, key, value)
            else:
                db_pos = DBPosition(**pos_data)
                db.add(db_pos)
            
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"DB Error saving position: {e}")

    def _load_state(self):
        try:
            db = SessionLocal()
            db_positions = db.query(DBPosition).all()
            db.close()
            
            for p in db_positions:
                pos_dict = {
                    "id": p.id, "symbol": p.symbol, "direction": p.direction,
                    "entry_price": p.entry_price, "amount": p.amount, "amount_usdt": p.amount_usdt,
                    "stop_loss_price": p.stop_loss_price, "take_profit_price": p.take_profit_price,
                    "stop_loss_pct": p.stop_loss_pct, "take_profit_pct": p.take_profit_pct,
                    "confidence": p.confidence, 
                    "opened_at": p.opened_at.isoformat() + "Z" if p.opened_at else "",
                    "order_id": p.order_id,
                    "status": p.status, "close_price": p.close_price, 
                    "pnl_usdt": p.pnl_usdt, "pnl_pct": p.pnl_pct,
                    "closed_at": p.closed_at.isoformat() + "Z" if p.closed_at else ""
                }
                pos_obj = Position(**pos_dict)
                self.positions[p.id] = pos_obj
                
                if p.status != "open":
                    self.trade_history.append(pos_dict)
                    self.total_pnl_usdt += p.pnl_usdt
                    if p.pnl_usdt >= 0: self.win_count += 1
                    else: self.loss_count += 1
            
            logger.info(f"Loaded {len(self.positions)} positions from database.")
        except Exception as e:
            logger.error(f"DB Error loading state: {e}")

    def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        amount_usdt: float,
        stop_loss_pct: float,
        take_profit_pct: float,
        confidence: float,
        atr: Optional[float] = None,
        order_id: str = "",
    ) -> Optional[Position]:
        open_count = sum(1 for p in self.positions.values() if p.status == "open")
        from config import settings
        if open_count >= settings.max_open_trades:
            logger.warning(f"Max open trades ({settings.max_open_trades}) reached — skipping")
            return None

        if atr and atr > 0:
            atr_sl_pct = (atr * 2.0 / entry_price) * 100
            stop_loss_pct = max(0.5, min(5.0, atr_sl_pct))
            take_profit_pct = max(take_profit_pct, stop_loss_pct * 2.0)
            logger.info(f"Expert Risk Engine: Dynamic SL: {stop_loss_pct:.2f}% | TP: {take_profit_pct:.2f}%")

        amount = amount_usdt / entry_price

        if direction == "BUY":
            sl_price = round(entry_price * (1 - stop_loss_pct / 100), 8)
            tp_price = round(entry_price * (1 + take_profit_pct / 100), 8)
        else:  # SELL
            sl_price = round(entry_price * (1 + stop_loss_pct / 100), 8)
            tp_price = round(entry_price * (1 - take_profit_pct / 100), 8)

        pos_id = f"{symbol.replace('/', '')}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        pos = Position(
            id=pos_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            amount=amount,
            amount_usdt=amount_usdt,
            stop_loss_price=sl_price,
            take_profit_price=tp_price,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            confidence=confidence,
            order_id=order_id,
        )
        self.positions[pos_id] = pos
        self._save_pos(pos)
        
        # Notify Telegram
        telegram_alerts.notify_trade_open(pos.to_dict())
        
        logger.trade(
            f"Position opened [{symbol}] {direction} @ {entry_price} "
            f"| SL: {sl_price} | TP: {tp_price} | Amount: ${amount_usdt:.2f}",
            pos.to_dict()
        )
        return pos

    def check_positions(self, current_prices: Dict[str, float]) -> List[Dict]:
        closed = []
        for pos in list(self.positions.values()):
            if pos.status != "open":
                continue
            price = current_prices.get(pos.symbol)
            if not price:
                continue

            hit_tp = hit_sl = False
            if pos.direction == "BUY":
                hit_tp = price >= pos.take_profit_price
                hit_sl = price <= pos.stop_loss_price
            else:
                hit_tp = price <= pos.take_profit_price
                hit_sl = price >= pos.stop_loss_price

            if hit_tp or hit_sl:
                reason = "closed_tp" if hit_tp else "closed_sl"
                closed_pos = self._close_position(pos, price, reason)
                closed.append(closed_pos)

        return closed

    def _close_position(self, pos: Position, close_price: float, reason: str) -> Dict:
        logger.info(f"Executing exchange order to close {pos.symbol} position...")
        if pos.direction == "BUY":
            exchange_client.create_market_sell(pos.symbol, amount=pos.amount)
        else:
            exchange_client.create_market_buy(pos.symbol, amount_usdt=pos.amount_usdt)

        if pos.direction == "BUY":
            pnl_pct  = ((close_price - pos.entry_price) / pos.entry_price) * 100
        else:
            pnl_pct  = ((pos.entry_price - close_price) / pos.entry_price) * 100
        pnl_usdt = pos.amount_usdt * (pnl_pct / 100)

        pos.status      = reason
        pos.close_price = close_price
        pos.pnl_pct     = round(pnl_pct, 4)
        pos.pnl_usdt    = round(pnl_usdt, 4)
        pos.closed_at   = datetime.utcnow().isoformat() + "Z"

        self.total_pnl_usdt += pnl_usdt
        if pnl_usdt >= 0:
            self.win_count += 1
        else:
            self.loss_count += 1

        self.trade_history.append(pos.to_dict())
        self._save_pos(pos)
        
        # Notify Telegram
        telegram_alerts.notify_trade_close(pos.to_dict())

        emoji = "💚" if pnl_usdt >= 0 else "🔴"
        logger.trade(
            f"{emoji} Position {reason.upper()} [{pos.symbol}] @ {close_price} "
            f"| PnL: {pnl_pct:+.2f}% (${pnl_usdt:+.2f}) "
            f"| Total PnL: ${self.total_pnl_usdt:+.2f}",
            pos.to_dict()
        )
        return pos.to_dict()

    def close_position_manual(self, pos_id: str, current_price: float) -> Optional[Dict]:
        pos = self.positions.get(pos_id)
        if not pos or pos.status != "open":
            return None
        return self._close_position(pos, current_price, "closed_manual")

    def get_open_positions(self) -> List[Dict]:
        return [p.to_dict() for p in self.positions.values() if p.status == "open"]

    def get_stats(self) -> Dict:
        total_trades = self.win_count + self.loss_count
        win_rate = (self.win_count / total_trades * 100) if total_trades > 0 else 0
        return {
            "total_trades": total_trades,
            "wins":         self.win_count,
            "losses":       self.loss_count,
            "win_rate_pct": round(win_rate, 2),
            "total_pnl_usdt": round(self.total_pnl_usdt, 4),
            "open_positions": len(self.get_open_positions()),
            "trade_history": self.trade_history[-20:],
        }


# Singleton
risk_manager = RiskManager()
