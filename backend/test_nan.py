import yfinance as yf
import numpy as np

def _safe_float(val):
    try:
        if val is None:
            return 0.0
        fval = float(val)
        import math
        if math.isnan(fval) or math.isinf(fval):
            return 0.0
        return float(round(fval, 2))
    except (TypeError, ValueError):
        return 0.0

stock = yf.Ticker("BBCA.JK")
df = stock.history(period="1y", interval="1d")
open_price = _safe_float(df["Open"].iloc[-1])
print(f"open_price: {open_price}, type: {type(open_price)}")

try:
    import json
    json.dumps({"open": open_price})
    print("JSON serialization successful!")
except Exception as e:
    print(f"JSON ERROR: {e}")
