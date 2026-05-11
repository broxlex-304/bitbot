
import pandas as pd
import numpy as np
from bot.analyzer import TechnicalAnalyzer

# Mock data
data = {
    "timestamp": pd.date_range(start="2024-01-01", periods=300, freq="15min"),
    "open": np.random.uniform(50000, 60000, 300),
    "high": np.random.uniform(50000, 60000, 300),
    "low": np.random.uniform(50000, 60000, 300),
    "close": np.random.uniform(50000, 60000, 300),
    "volume": np.random.uniform(100, 1000, 300),
}
df = pd.DataFrame(data)
df.set_index("timestamp", inplace=True)

analyzer = TechnicalAnalyzer()
try:
    results = analyzer.analyze(df, "BTC/USDT")
    print("Analysis Successful")
    print("Score:", results["composite"]["score"])
except Exception as e:
    print("Analysis Failed:", e)
    import traceback
    traceback.print_exc()
