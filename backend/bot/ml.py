import pandas as pd
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from bot import logger

class MLPredictor:
    def __init__(self):
        # State-of-the-art Gradient Boosting for large datasets (faster & handles NaN)
        self.model = HistGradientBoostingClassifier(
            max_iter=200, 
            learning_rate=0.05, 
            max_depth=7, 
            l2_regularization=0.1,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.is_trained = False

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df_ml = df.copy()
        
        # 1. Price Action & Returns
        df_ml['ret_1'] = df_ml['close'].pct_change()
        df_ml['ret_3'] = df_ml['close'].pct_change(3)
        df_ml['ret_5'] = df_ml['close'].pct_change(5)
        df_ml['vol_change'] = df_ml['volume'].pct_change()
        
        # 2. Moving Averages & Distances
        df_ml['sma_7'] = df_ml['close'].rolling(7).mean()
        df_ml['sma_21'] = df_ml['close'].rolling(21).mean()
        df_ml['dist_sma_7'] = (df_ml['close'] - df_ml['sma_7']) / df_ml['sma_7']
        df_ml['dist_sma_21'] = (df_ml['close'] - df_ml['sma_21']) / df_ml['sma_21']
        
        # 3. Volatility & Range
        df_ml['volatility_10'] = df_ml['ret_1'].rolling(10).std()
        df_ml['range_pct'] = (df_ml['high'] - df_ml['low']) / df_ml['low']
        df_ml['body_pct'] = abs(df_ml['close'] - df_ml['open']) / (df_ml['high'] - df_ml['low'] + 1e-9)
        
        # 4. Momentum (RSI Proxy)
        delta = df_ml['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        df_ml['rsi_14'] = 100 - (100 / (1 + rs))
        
        # 5. MACD Proxy
        ema_12 = df_ml['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df_ml['close'].ewm(span=26, adjust=False).mean()
        df_ml['macd_hist'] = (ema_12 - ema_26) - (ema_12 - ema_26).ewm(span=9, adjust=False).mean()
        
        # 6. Session Awareness (Institutional Hours)
        # Assuming index is DatetimeIndex
        if isinstance(df_ml.index, pd.DatetimeIndex):
            df_ml['hour'] = df_ml.index.hour
            df_ml['is_london'] = ((df_ml['hour'] >= 8) & (df_ml['hour'] <= 16)).astype(int)
            df_ml['is_ny'] = ((df_ml['hour'] >= 13) & (df_ml['hour'] <= 21)).astype(int)
        else:
            df_ml['hour'] = 0
            df_ml['is_london'] = 0
            df_ml['is_ny'] = 0
        
        df_ml.replace([np.inf, -np.inf], np.nan, inplace=True)
        return df_ml

    def train(self, df: pd.DataFrame):
        df_ml = self.prepare_features(df)
        if len(df_ml) < 100:
            return False
            
        # Target: 1 if next candle is green, 0 if red
        df_ml['target'] = (df_ml['close'].shift(-1) > df_ml['close']).astype(int)
        df_ml.dropna(inplace=True)
        
        features = [
            'ret_1', 'ret_3', 'ret_5', 'vol_change', 'dist_sma_7', 'dist_sma_21', 
            'volatility_10', 'range_pct', 'body_pct', 'rsi_14', 'macd_hist', 'is_london', 'is_ny'
        ]
        
        X = df_ml[features]
        y = df_ml['target']
        
        if len(X) < 50:
            return False
            
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True
        return True

    def predict(self, df: pd.DataFrame) -> dict:
        if len(df) < 30:
            return {"ml_score": 50.0, "ml_direction": "NEUTRAL"}
            
        # Re-train on latest data to capture immediate market regimes
        self.train(df)
        
        if not self.is_trained:
            return {"ml_score": 50.0, "ml_direction": "NEUTRAL"}
            
        df_ml = self.prepare_features(df)
        
        features = [
            'ret_1', 'ret_3', 'ret_5', 'vol_change', 'dist_sma_7', 'dist_sma_21', 
            'volatility_10', 'range_pct', 'body_pct', 'rsi_14', 'macd_hist', 'is_london', 'is_ny'
        ]
        
        # Forward fill any recent NaNs for prediction
        df_ml[features] = df_ml[features].ffill()
        X_last = df_ml[features].iloc[-1:]
        
        if X_last.isnull().values.any():
             return {"ml_score": 50.0, "ml_direction": "NEUTRAL"}
             
        X_last_scaled = self.scaler.transform(X_last)
        
        prob = self.model.predict_proba(X_last_scaled)[0]
        prob_bull = prob[1] * 100
        
        direction = "BUY" if prob_bull >= 55 else ("SELL" if prob_bull <= 45 else "NEUTRAL")
        
        logger.analysis(f"Advanced ML Gradient Boosting: {prob_bull:.1f}% Bullish -> {direction}")
        
        return {
            "ml_score": prob_bull,
            "ml_direction": direction
        }

ml_engine = MLPredictor()
