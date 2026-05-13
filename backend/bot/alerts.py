import asyncio
import httpx
from typing import Optional, Dict, List
from bot import logger
from config import settings

class TelegramAlerts:
    def __init__(self):
        self.token = settings.telegram_token
        self.chat_id = settings.telegram_chat_id
        self.enabled = bool(self.token and self.chat_id)
        self.last_update_id = 0
        self._poll_task = None

    def start(self):
        if self.enabled and not self._poll_task:
            self._poll_task = asyncio.create_task(self._poll_loop())
            logger.info("Telegram command listener active.")

    async def _poll_loop(self):
        """Polls Telegram for new commands from the user."""
        while True:
            try:
                url = f"https://api.telegram.org/bot{self.token}/getUpdates"
                params = {"offset": self.last_update_id + 1, "timeout": 30}
                
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, params=params, timeout=35)
                    if resp.status_code == 200:
                        updates = resp.json().get("result", [])
                        for update in updates:
                            self.last_update_id = update["update_id"]
                            await self._handle_update(update)
            except Exception as e:
                logger.error(f"Telegram polling error: {e}")
            await asyncio.sleep(2)

    async def _handle_update(self, update: Dict):
        """Processes incoming messages and routes commands."""
        msg = update.get("message")
        if not msg or "text" not in msg: return
        
        text = msg["text"].lower()
        sender_id = str(msg["from"]["id"])
        
        # Security: Only reply to YOU (the owner)
        if sender_id != str(self.chat_id):
            logger.warning(f"Unauthorized Telegram access attempt from {sender_id}")
            return

        if text == "/start":
            await self.send_message("👋 <b>BitBot Command Center Active</b>\n\nCommands:\n/status - Bot health\n/balance - Wallet balance\n/positions - Open trades\n/stats - P&L summary")
        
        elif text == "/status":
            from bot.engine import engine
            from bot.exchange import exchange_client
            mode = "LIVE" if not exchange_client.paper_mode else "PAPER"
            status_msg = (
                f"🤖 <b>Bot Status:</b> {engine.status.value.upper()}\n"
                f"📈 <b>Symbol:</b> {engine.symbol}\n"
                f"⏱️ <b>Timeframe:</b> {engine.timeframe}\n"
                f"🔗 <b>Exchange:</b> {exchange_client.exchange_id.upper()} ({mode})"
            )
            await self.send_message(status_msg)

        elif text == "/balance":
            from bot.exchange import exchange_client
            try:
                bal = exchange_client.fetch_balance()
                usdt = bal.get("USDT", 0)
                msg_bal = f"💰 <b>Current Balance:</b>\n\nUSDT: ${usdt:.2f}"
                await self.send_message(msg_bal)
            except Exception as e:
                await self.send_message(f"❌ Error fetching balance: {e}")

        elif text == "/positions":
            from bot.risk import risk_manager
            pos_list = risk_manager.get_open_positions()
            if not pos_list:
                await self.send_message("📂 No open positions currently.")
            else:
                msg_pos = "📂 <b>Active Positions:</b>\n\n"
                for p in pos_list:
                    msg_pos += f"• {p['symbol']} {p['direction']} @ {p['entry_price']}\n  PnL: {p['pnl_pct']}% (${p['pnl_usdt']})\n\n"
                await self.send_message(msg_pos)

        elif text == "/stats":
            from bot.risk import risk_manager
            s = risk_manager.get_stats()
            msg_s = (
                f"🏆 <b>Performance Stats:</b>\n\n"
                f"Total Trades: {s['total_trades']}\n"
                f"Win Rate: {s['win_rate_pct']}%\n"
                f"Total PnL: ${s['total_pnl_usdt']:.2f}\n"
                f"Wins: {s['wins']} | Losses: {s['losses']}"
            )
            await self.send_message(msg_s)

    async def send_message(self, text: str):
        if not self.enabled: return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    def notify_trade_open(self, pos: dict):
        msg = (
            f"🚀 <b>TRADE OPENED</b>\n\n"
            f"<b>Symbol:</b> {pos['symbol']}\n"
            f"<b>Direction:</b> {pos['direction']}\n"
            f"<b>Entry:</b> ${pos['entry_price']}\n"
            f"<b>Confidence:</b> {pos['confidence']}%\n"
            f"<b>SL:</b> {pos['stop_loss_price']}\n"
            f"<b>TP:</b> {pos['take_profit_price']}"
        )
        asyncio.create_task(self.send_message(msg))

    def notify_trade_close(self, pos: dict):
        emoji = "✅" if pos['pnl_usdt'] >= 0 else "❌"
        msg = (
            f"{emoji} <b>TRADE CLOSED</b>\n\n"
            f"<b>Symbol:</b> {pos['symbol']}\n"
            f"<b>Result:</b> {pos['status'].upper()}\n"
            f"<b>PnL:</b> {pos['pnl_pct']}% (${pos['pnl_usdt']})\n"
            f"<b>Exit Price:</b> ${pos['close_price']}"
        )
        asyncio.create_task(self.send_message(msg))

telegram_alerts = TelegramAlerts()
