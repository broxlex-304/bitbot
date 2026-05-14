"""
BitBot Exchange Layer
Wraps CCXT with auto-connect to public Binance for paper trading
when no API keys are configured. Supports 100+ exchanges.
"""

import ccxt
import pandas as pd
from typing import Optional, Dict, Any, List, Tuple
from bot import logger
from config import settings


class ExchangeClient:
    def __init__(self):
        self.exchange: Optional[ccxt.Exchange] = None
        self.exchange_id = settings.exchange_id
        self.connected = False
        self.paper_mode = False  # True when using public data, no real trades

    def _normalize_symbol(self, symbol: str) -> str:
        """Convert various symbol formats to standard CCXT format."""
        if not symbol: return ""
        s = symbol.upper()
        # Remove common prefixes
        s = s.replace("BINANCE:", "").replace("MEXC:", "").replace("BYBIT:", "")
        # Remove common suffixes
        s = s.replace("PERP", "").replace(".P", "").replace(".p", "")
        # Replace dashes/underscores with slash
        s = s.replace("-", "/").replace("_", "/")
        
        # Ensure it has a slash
        if "/" not in s:
            # Assume USDT pair if no slash
            if s.endswith("USDT"):
                s = s[:-4] + "/USDT"
            else:
                s = s + "/USDT"
        
        # If MEXC and perpetual, we might need :USDT suffix for some CCXT versions
        if self.exchange_id == "mexc" and "USDT" in s and ":" not in s:
             # Standard CCXT format for MEXC perpetuals is BTC/USDT:USDT
             # But often BTC/USDT works too depending on defaultType
             pass
             
        return s

    def connect(self, exchange_id: str = None, api_key: str = None, api_secret: str = None) -> Tuple[bool, str]:
        try:
            eid    = exchange_id or self.exchange_id
            key    = (api_key    or settings.api_key or "").strip()
            secret = (api_secret or settings.api_secret or "").strip()

            exchange_class = getattr(ccxt, eid)
            self.exchange = exchange_class({
                "apiKey": key,
                "secret": secret,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "swap", # Switched to Perpetual Futures as requested
                    "recvWindow": 60000 
                },
            })
            self.exchange.load_markets()
            
            # Verify keys if provided
            if key and secret:
                try:
                    self.exchange.fetch_balance()
                    self.paper_mode = False
                    msg = "MEXC Wallet Connected (Live Trading)"
                    logger.success(f"✅ {msg}")
                    # Save credentials encrypted for next restart
                    from bot.database import set_setting
                    set_setting("api_credentials", {"id": eid, "key": key, "secret": secret}, encrypt=True)
                    self.connected = True
                    self.exchange_id = eid
                    return True, msg
                except Exception as e:
                    self.connected = False
                    err_msg = f"Key Verification Failed: {str(e)}"
                    logger.error(f"❌ {err_msg}")
                    return False, err_msg
            else:
                self.paper_mode = True
                msg = f"Connected to {(eid or 'UNKNOWN').upper()} (Public/Paper Mode)"
                logger.info(f"📊 {msg}")
                self.connected = True
                self.exchange_id = eid
                return True, msg

        except Exception as e:
            self.connected = False
            err_msg = f"Connection failed: {str(e)}"
            logger.error(f"❌ {err_msg}")
            return False, err_msg

    def ensure_connected(self) -> bool:
        """Auto-connect to public Binance if not already connected."""
        if self.connected and self.exchange:
            return True
        success, _ = self.connect_public()
        return success

    def connect_public(self) -> Tuple[bool, str]:
        """Connect to public API (no keys needed) for paper trading / analysis."""
        try:
            eid = self.exchange_id or "mexc"
            
            # If the exchange is binance and we are getting blocked, we can safely fallback to mexc
            if eid == "binance":
                eid = "mexc"
                
            exchange_class = getattr(ccxt, eid)
            self.exchange = exchange_class({
                "enableRateLimit": True,
                "options": {"defaultType": "swap"}, # Perpetual Futures
            })
            self.exchange.load_markets()
            self.connected = True
            self.paper_mode = True
            msg = f"Connected to {eid.upper()} Public API (Paper mode)"
            logger.success(f"📊 {msg}")
            return True, msg
        except Exception as e:
            logger.error(f"Public API connection failed: {e}")
            return False, str(e)

    def get_supported_exchanges(self) -> List[str]:
        return ccxt.exchanges

    def fetch_ohlcv(self, symbol: str, timeframe: str = "15m", limit: int = 200) -> pd.DataFrame:
        if not self.ensure_connected():
            return pd.DataFrame()
        symbol = self._normalize_symbol(symbol)
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
        symbol = self._normalize_symbol(symbol)
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"Ticker fetch error: {e}")
            return {}

    def fetch_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        if not self.ensure_connected():
            return {}
        symbol = self._normalize_symbol(symbol)
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

    def create_market_buy(self, symbol: str, amount_usdt: Optional[float] = None, amount: Optional[float] = None) -> Optional[Dict]:
        if not amount and not amount_usdt:
            return None
        symbol = self._normalize_symbol(symbol)
        if self.paper_mode:
            ticker = self.fetch_ticker(symbol)
            price  = ticker.get("last", 0)
            if not amount:
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
            
            if not amount:
                amount = amount_usdt / price
            
            amount_str = self.exchange.amount_to_precision(symbol, amount)
            order  = self.exchange.create_market_buy_order(symbol, float(amount_str))
            logger.trade(f"🟢 LIVE BUY [{symbol}] @ ${price:.2f}", order)
            return order
        except Exception as e:
            logger.error(f"Buy order failed [{symbol}]: {e}")
            return None

    def create_market_sell(self, symbol: str, amount: Optional[float] = None, amount_usdt: Optional[float] = None) -> Optional[Dict]:
        if not amount and not amount_usdt:
            return None
        symbol = self._normalize_symbol(symbol)
        if self.paper_mode:
            ticker = self.fetch_ticker(symbol)
            price  = ticker.get("last", 0)
            if not amount:
                amount = amount_usdt / price if price else 0
            order  = {
                "id": f"PAPER_{symbol.replace('/','')}_{pd.Timestamp.now().strftime('%H%M%S')}",
                "symbol": symbol, "side": "sell", "type": "market",
                "amount": amount, "price": price, "status": "closed", "paper": True
            }
            logger.trade(f"📝 PAPER SELL [{symbol}] @ ${price:.2f} | Amount: {amount:.6f}", order)
            return order
        try:
            if not amount:
                ticker = self.fetch_ticker(symbol)
                price = ticker.get("last", 0)
                if not price: return None
                amount = amount_usdt / price
                
            amount_str = self.exchange.amount_to_precision(symbol, amount)
            order = self.exchange.create_market_sell_order(symbol, float(amount_str))
            logger.trade(f"🔴 LIVE SELL [{symbol}] @ ${order.get('price', 0)}", order)
            return order
        except Exception as e:
            logger.error(f"Sell order failed [{symbol}]: {e}")
            return None

    def create_stop_limit_order(self, symbol: str, side: str, amount: float,
                                stop_price: float, limit_price: float) -> Optional[Dict]:
        symbol = self._normalize_symbol(symbol)
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
        symbol = self._normalize_symbol(symbol)
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
        if symbol:
            symbol = self._normalize_symbol(symbol)
        if self.paper_mode:
            return []
        try:
            return self.exchange.fetch_open_orders(symbol)
        except Exception as e:
            logger.error(f"Fetch open orders failed: {e}")
            return []

    def fetch_order(self, order_id: str, symbol: str) -> Optional[Dict]:
        symbol = self._normalize_symbol(symbol)
        if self.paper_mode:
            return None
        try:
            return self.exchange.fetch_order(order_id, symbol)
        except Exception as e:
            logger.error(f"Fetch order failed: {e}")
            return None


# Singleton instance
exchange_client = ExchangeClient()
