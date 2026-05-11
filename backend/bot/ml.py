import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from bot import logger

class MLPredictor:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        self.is_trained = False

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df_ml = df.copy()
        
        # Create features
        df_ml['ret_1'] = df_ml['close'].pct_change()
        df_ml['ret_2'] = df_ml['close'].pct_change(2)
        df_ml['ret_3'] = df_ml['close'].pct_change(3)
        df_ml['vol_change'] = df_ml['volume'].pct_change()
        
        # Moving averages
        df_ml['sma_5'] = df_ml['close'].rolling(5).mean()
        df_ml['sma_10'] = df_ml['close'].rolling(10).mean()
        df_ml['dist_sma_5'] = (df_ml['close'] - df_ml['sma_5']) / df_ml['sma_5']
        
        # Volatility
        df_ml['volatility'] = df_ml['ret_1'].rolling(10).std()
        
        df_ml.dropna(inplace=True)
        return df_ml

    def train(self, df: pd.DataFrame):
        df_ml = self.prepare_features(df)
        if len(df_ml) < 50:
            return False
            
        # Target: 1 if next candle is green, 0 if red
        df_ml['target'] = (df_ml['close'].shift(-1) > df_ml['close']).astype(int)
        df_ml.dropna(inplace=True)
        
        features = ['ret_1', 'ret_2', 'ret_3', 'vol_change', 'dist_sma_5', 'volatility']
        X = df_ml[features]
        y = df_ml['target']
        
        if len(X) < 10:
            return False
            
        self.model.fit(X, y)
        self.is_trained = True
        return True

    def predict(self, df: pd.DataFrame) -> dict:
        if len(df) < 20:
            return {"ml_score": 50.0, "ml_direction": "NEUTRAL"}
            
        # Re-train on latest data
        self.train(df)
        
        if not self.is_trained:
            return {"ml_score": 50.0, "ml_direction": "NEUTRAL"}
            
        df_ml = self.prepare_features(df)
        if df_ml.empty:
             return {"ml_score": 50.0, "ml_direction": "NEUTRAL"}
             
        features = ['ret_1', 'ret_2', 'ret_3', 'vol_change', 'dist_sma_5', 'volatility']
        X_last = df_ml[features].iloc[-1:]
        
        prob = self.model.predict_proba(X_last)[0]
        prob_bull = prob[1] * 100
        
        direction = "BUY" if prob_bull >= 55 else ("SELL" if prob_bull <= 45 else "NEUTRAL")
        
        logger.analysis(f"ML Model Prediction: {prob_bull:.1f}% Bullish -> {direction}")
        
        return {
            "ml_score": prob_bull,
            "ml_direction": direction
        }

ml_engine = MLPredictor()
