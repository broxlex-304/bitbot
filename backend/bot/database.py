import os
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, DateTime, JSON
from sqlalchemy.orm import sessionmaker, declarative_base
from cryptography.fernet import Fernet

# --- Encryption Vault ---
class Vault:
    def __init__(self):
        # In a real production app, the key should be in a secure environment variable
        self.key_file = "vault.key"
        self._key = self._load_or_create_key()
        self.fernet = Fernet(self._key)

    def _load_or_create_key(self):
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as f:
                return f.read()
        key = Fernet.generate_key()
        with open(self.key_file, "wb") as f:
            f.write(key)
        return key

    def encrypt(self, data: str) -> str:
        if not data: return ""
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, token: str) -> str:
        if not token: return ""
        try:
            return self.fernet.decrypt(token.encode()).decode()
        except Exception:
            return ""

vault = Vault()

from config import settings

# --- Database Setup ---
DB_URL = settings.database_url
# Use a higher pool size for PostgreSQL in the cloud
if DB_URL.startswith("postgresql"):
    engine = create_engine(DB_URL, pool_size=10, max_overflow=20)
else:
    # SQLite logic
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Models ---

class DBLog(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String)
    icon = Column(String)
    message = Column(Text)
    data = Column(JSON)

class DBPosition(Base):
    __tablename__ = "positions"
    id = Column(String, primary_key=True)
    symbol = Column(String)
    direction = Column(String)
    entry_price = Column(Float)
    amount = Column(Float)
    amount_usdt = Column(Float)
    stop_loss_price = Column(Float)
    take_profit_price = Column(Float)
    stop_loss_pct = Column(Float)
    take_profit_pct = Column(Float)
    confidence = Column(Float)
    opened_at = Column(DateTime)
    status = Column(String) # open | closed_tp | closed_sl | closed_manual
    close_price = Column(Float, default=0.0)
    pnl_usdt = Column(Float, default=0.0)
    pnl_pct = Column(Float, default=0.0)
    order_id = Column(String, default="")
    closed_at = Column(DateTime, nullable=True)

class DBScannerResult(Base):
    __tablename__ = "scanner_results"
    symbol = Column(String, primary_key=True)
    confidence = Column(Float)
    direction = Column(String)
    price = Column(Float)
    score = Column(Float)
    updated_at = Column(DateTime, default=datetime.utcnow)

class DBSettings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True)
    value = Column(Text) # JSON serialized

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from typing import Any
def set_setting(key: str, value: Any, encrypt: bool = False):
    db = SessionLocal()
    try:
        val_str = json.dumps(value)
        if encrypt:
            val_str = vault.encrypt(val_str)
        
        existing = db.query(DBSettings).filter(DBSettings.key == key).first()
        if existing:
            existing.value = val_str
        else:
            db_set = DBSettings(key=key, value=val_str)
            db.add(db_set)
        db.commit()
    finally:
        db.close()

def get_setting(key: str, default: Any = None, encrypted: bool = False) -> Any:
    db = SessionLocal()
    try:
        item = db.query(DBSettings).filter(DBSettings.key == key).first()
        if not item: return default
        val_str = item.value
        if encrypted:
            val_str = vault.decrypt(val_str)
        return json.loads(val_str)
    except Exception:
        return default
    finally:
        db.close()
