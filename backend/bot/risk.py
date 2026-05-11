"""
BitBot Risk Manager
Tracks open positions, enforces stop-loss and take-profit.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from bot import logger
from bot import exchange as ex_module


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

    def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        amount_usdt: float,
        stop_loss_pct: float,
        take_profit_pct: float,
        confidence: float,
        order_id: str = "",
    ) -> Optional[Position]:
        # Check max open trades
        open_count = sum(1 for p in self.positions.values() if p.status == "open")
        from config import settings
        if open_count >= settings.max_open_trades:
            logger.warning(f"Max open trades ({settings.max_open_trades}) reached — skipping")
            return None

        amount = amount_usdt / entry_price

        if direction == "BUY":
            sl_price = round(entry_price * (1 - stop_loss_pct / 100), 8)
            tp_price = round(entry_price * (1 + take_profit_pct / 100), 8)
        else:  # SELL / SHORT
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
        logger.trade(
            f"Position opened [{symbol}] {direction} @ {entry_price} "
            f"| SL: {sl_price} | TP: {tp_price} | Amount: ${amount_usdt:.2f}",
            pos.to_dict()
        )
        return pos

    def check_positions(self, current_prices: Dict[str, float]) -> List[Dict]:
        """Check all open positions against current prices for SL/TP."""
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
