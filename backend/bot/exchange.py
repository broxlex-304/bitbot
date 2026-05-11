"""
BitBot Exchange Layer
Wraps CCXT with auto-connect to public Binance for paper trading
when no API keys are configured. Supports 100+ exchanges.
"""

import ccxt
import pandas as pd
from typing import Optional, Dict, Any, List
from bot import logger
from config import settings


class ExchangeClient:
    def __init__(self):
        self.exchange: Optional[ccxt.Exchange] = None
        self.exchange_id = settings.exchange_id
        self.connected = False
        self.paper_mode = False  # True when using public data, no real trades

    def connect_public(self) -> bool:
        """Connect to Binance public API (no keys needed) for paper trading / analysis."""
        try:
            self.exchange = ccxt.binance({
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            })
            self.exchange.load_markets()
            self.connected = True
            self.paper_mode = True
            logger.success(
                "📊 Connected to Binance public API (Paper Trade mode) — "
                "analysis fully active, NO real orders will be placed"
            )
            return True
        except Exception as e:
            logger.error(f"Public API connection failed: {e}")
            return False

    def connect(self, exchange_id: str = None, api_key: str = None, api_secret: str = None) -> bool:
        try:
            eid    = exchange_id or self.exchange_id
            key    = api_key    or settings.api_key
            secret = api_secret or settings.api_secret

            exchange_class = getattr(ccxt, eid)
            self.exchange = exchange_class({
                "apiKey": key,
                "secret": secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            })
            self.exchange.load_markets()
            self.connected  = True
            self.paper_mode = not bool(key)   # If no key → still paper mode
            self.exchange_id = eid
            logger.success(
                f"✅ Connected to {eid.upper()} | Markets: {len(self.exchange.markets)} "
                f"| Mode: {'Paper' if self.paper_mode else 'LIVE TRADING'}"
            )
            return True
        except Exception as e:
            self.connected = False
            logger.error(f"Exchange connection failed [{eid}]: {e}")
            return False

    def ensure_connected(self) -> bool:
        """Auto-connect to public Binance if not already connected."""
        if self.connected and self.exchange:
            return True
        return self.connect_public()

    def get_supported_exchanges(self) -> List[str]:
        return ccxt.exchanges

    def fetch_ohlcv(self, symbol: str, timeframe: str = "15m", limit: int = 200) -> pd.DataFrame:
        if not self.ensure_connected():
            return pd.DataFrame()
        try:
            raw = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            return df
        except Exception as e:
            logger.error(f"OHLCV fetch error [{symbol}]: {e}")
            return pd.DataFrame()

    def fetch_ticker(self, symbol: str) -> Dict:
        if not self.ensure_connected():
            return {}
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"Ticker fetch error: {e}")
            return {}

    def fetch_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        if not self.ensure_connected():
            return {}
        try:
            return self.exchange.fetch_order_book(symbol, limit=limit)
        except Exception as e:
            logger.error(f"Orderbook fetch error: {e}")
            return {}

    def fetch_balance(self) -> Dict:
        if self.paper_mode:
            return {"USDT": 1000.0, "mode": "paper"}   # Simulated balance
        if not self.ensure_connected():
            return {}
        try:
            balance = self.exchange.fetch_balance()
            return {k: v for k, v in balance["total"].items() if v and v > 0}
        except Exception as e:
            logger.error(f"Balance fetch error: {e}")
            return {}

    def create_market_buy(self, symbol: str, amount_usdt: float) -> Optional[Dict]:
        if self.paper_mode:
            ticker = self.fetch_ticker(symbol)
            price  = ticker.get("last", 0)
            amount = amount_usdt / price if price else 0
            order  = {
                "id": f"PAPER_{symbol.replace('/','')}_{pd.Timestamp.now().strftime('%H%M%S')}",
                "symbol": symbol, "side": "buy", "type": "market",
                "amount": amount, "price": price, "status": "closed", "paper": True
            }
            logger.trade(f"📝 PAPER BUY [{symbol}] @ ${price:.2f} | Amount: {amount:.6f}", order)
            return order
        try:
            ticker = self.fetch_ticker(symbol)
            price  = ticker.get("last", 0)
            if not price:
                return None
            amount = self.exchange.amount_to_precision(symbol, amount_usdt / price)
            order  = self.exchange.create_market_buy_order(symbol, float(amount))
            logger.trade(f"🟢 LIVE BUY [{symbol}] @ ${price:.2f}", order)
            return order
        except Exception as e:
            logger.error(f"Buy order failed [{symbol}]: {e}")
            return None

    def create_market_sell(self, symbol: str, amount: float) -> Optional[Dict]:
        if self.paper_mode:
            ticker = self.fetch_ticker(symbol)
            price  = ticker.get("last", 0)
            order  = {
                "id": f"PAPER_{symbol.replace('/','')}_{pd.Timestamp.now().strftime('%H%M%S')}",
                "symbol": symbol, "side": "sell", "type": "market",
                "amount": amount, "price": price, "status": "closed", "paper": True
            }
            logger.trade(f"📝 PAPER SELL [{symbol}] @ ${price:.2f}", order)
            return order
        try:
            amount_str = self.exchange.amount_to_precision(symbol, amount)
            order = self.exchange.create_market_sell_order(symbol, float(amount_str))
            logger.trade(f"🔴 LIVE SELL [{symbol}]", order)
            return order
        except Exception as e:
            logger.error(f"Sell order failed [{symbol}]: {e}")
            return None

    def create_stop_limit_order(self, symbol: str, side: str, amount: float,
                                stop_price: float, limit_price: float) -> Optional[Dict]:
        if self.paper_mode:
            return None
        try:
            return self.exchange.create_order(
                symbol, "stop_limit", side, amount,
                limit_price, {"stopPrice": stop_price}
            )
        except Exception as e:
            logger.warning(f"Stop-limit not supported or failed: {e}")
            return None

    def cancel_order(self, order_id: str, symbol: str) -> bool:
        if self.paper_mode:
            return True
        try:
            self.exchange.cancel_order(order_id, symbol)
            logger.info(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Cancel order failed: {e}")
            return False

    def fetch_open_orders(self, symbol: str = None) -> List[Dict]:
        if self.paper_mode:
            return []
        try:
            return self.exchange.fetch_open_orders(symbol)
        except Exception as e:
            logger.error(f"Fetch open orders failed: {e}")
            return []

    def fetch_order(self, order_id: str, symbol: str) -> Optional[Dict]:
        if self.paper_mode:
            return None
        try:
            return self.exchange.fetch_order(order_id, symbol)
        except Exception as e:
            logger.error(f"Fetch order failed: {e}")
            return None


# Singleton instance
exchange_client = ExchangeClient()
