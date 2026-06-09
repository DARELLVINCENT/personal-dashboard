"""
Benchmark comparison API (yfinance).
"""
from fastapi import APIRouter, Query
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/benchmark", tags=["Benchmark"])

BENCHMARK_OPTIONS = {
    "^JKSE": "IHSG (Indonesia)", "^GSPC": "S&P 500 (USA)",
    "^N225": "Nikkei 225 (Japan)", "^HSI": "Hang Seng (HK)", "^FTSE": "FTSE 100 (UK)",
}

@router.get("")
def get_benchmark(symbol: str = "^JKSE", date_from: str = "", date_to: str = ""):
    import yfinance as yf
    if symbol not in BENCHMARK_OPTIONS:
        return {"error": "Symbol not allowed", "labels": [], "returns": []}
    if not date_from:
        date_from = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")
    try:
        df = yf.Ticker(symbol).history(start=date_from, end=date_to, interval="1d")
        if df.empty:
            return {"error": "Tidak ada data", "labels": [], "returns": []}
        first = float(df["Close"].iloc[0])
        df["ret"] = ((df["Close"] - first) / first) * 100
        return {"symbol": symbol, "name": BENCHMARK_OPTIONS[symbol],
                "labels": [str(d.date()) for d in df.index],
                "returns": [round(float(r), 4) for r in df["ret"]]}
    except Exception as e:
        return {"error": str(e), "labels": [], "returns": []}

@router.get("/options")
def benchmark_options():
    return [{"symbol": k, "name": v} for k, v in BENCHMARK_OPTIONS.items()]
