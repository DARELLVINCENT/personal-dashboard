"""
Forecasting router — Advanced stock price prediction.

Models available:
* ARIMA    : Auto-tuned via pmdarima (auto_arima)
* LSTM     : 2-layer LSTM deep-learning model (PyTorch)
* XGBOOST  : XGBoost gradient boosting with lag features
* ENSEMBLE : Weighted blend of best available models

Data preparation pipeline:
1. Fetch 2 years of daily close prices from yfinance
2. Forward/backward fill missing values
3. Outlier detection via IQR on daily returns (cap extreme moves)
4. Stationarity check via ADF test
5. Feature engineering: SMA(5/20/50), RSI(14), Bollinger Bands
6. Min-Max scaling for LSTM input
7. Walk-forward validation (80/20 train/test split)
"""

from fastapi import APIRouter, HTTPException
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import timedelta
import logging
import warnings
import os
import traceback

warnings.filterwarnings("ignore")

router = APIRouter(prefix="/api/forecast", tags=["Forecast"])
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Lazy imports  (fail gracefully per model)
# ─────────────────────────────────────────────

_HAS_PMDARIMA = False
_HAS_STATSMODELS = False
_HAS_TORCH = False
_HAS_XGBOOST = False
_HAS_SKLEARN = False

try:
    import pmdarima as pm
    _HAS_PMDARIMA = True
except ImportError:
    pass

try:
    from statsmodels.tsa.arima.model import ARIMA as StatsARIMA
    from statsmodels.tsa.stattools import adfuller
    _HAS_STATSMODELS = True
except ImportError:
    pass

try:
    import torch
    import torch.nn as nn
    _HAS_TORCH = True
except ImportError:
    pass

try:
    import xgboost as xgb
    _HAS_XGBOOST = True
except ImportError:
    pass

try:
    from sklearn.preprocessing import MinMaxScaler
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    _HAS_SKLEARN = True
except ImportError:
    MinMaxScaler = None


# ══════════════════════════════════════════════
#  1. DATA PREPARATION
# ══════════════════════════════════════════════

def fetch_data(ticker: str, period: str = "2y") -> pd.DataFrame:
    """Fetch OHLCV data from yfinance with validation."""
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval="1d")
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Tidak ada data untuk ticker {ticker}")
    return df


def clean_data(df: pd.DataFrame) -> dict:
    """
    Clean & prepare data.
    Returns a dict with close, returns, features_df, and prep_info.
    """
    close = df["Close"].copy()
    prep_info = {
        "raw_count": len(close),
        "missing_filled": 0,
        "outliers_capped": 0,
        "is_stationary": False,
        "adf_pvalue": None,
    }

    # ── 1. Fill missing values ──
    n_missing = int(close.isna().sum())
    close = close.ffill().bfill()
    prep_info["missing_filled"] = n_missing

    # ── 2. Outlier detection on daily returns (IQR method) ──
    returns = close.pct_change().dropna()
    q1 = returns.quantile(0.25)
    q3 = returns.quantile(0.75)
    iqr = q3 - q1
    lower_fence = q1 - 3.0 * iqr
    upper_fence = q3 + 3.0 * iqr
    outlier_mask = (returns < lower_fence) | (returns > upper_fence)
    n_outliers = int(outlier_mask.sum())
    prep_info["outliers_capped"] = n_outliers

    if n_outliers > 0:
        returns = returns.clip(lower=lower_fence, upper=upper_fence)
        # Reconstruct close from capped returns
        close_reconstructed = close.iloc[0] * (1 + returns).cumprod()
        close = pd.concat([close.iloc[:1], close_reconstructed])
        close = close[~close.index.duplicated(keep="last")]

    # ── 3. Stationarity check (ADF test) ──
    if _HAS_STATSMODELS and len(close) >= 30:
        try:
            adf_result = adfuller(close.values, autolag="AIC")
            prep_info["adf_pvalue"] = round(float(adf_result[1]), 6)
            prep_info["is_stationary"] = bool(adf_result[1] < 0.05)
        except Exception:
            pass

    # ── 4. Feature engineering ──
    features_df = pd.DataFrame(index=close.index)
    features_df["close"] = close
    features_df["return"] = close.pct_change()
    features_df["sma5"] = close.rolling(5).mean()
    features_df["sma20"] = close.rolling(20).mean()
    features_df["sma50"] = close.rolling(50).mean()

    # RSI 14
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    features_df["rsi14"] = 100 - (100 / (1 + rs))

    # Bollinger Bands
    bb_sma = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    features_df["bb_upper"] = bb_sma + 2 * bb_std
    features_df["bb_lower"] = bb_sma - 2 * bb_std
    features_df["bb_width"] = (features_df["bb_upper"] - features_df["bb_lower"]) / bb_sma

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    features_df["macd"] = ema12 - ema26
    features_df["macd_signal"] = features_df["macd"].ewm(span=9, adjust=False).mean()

    # Drop NaN rows created by rolling windows
    features_df = features_df.dropna()
    close = close.loc[features_df.index]

    return {
        "close": close,
        "returns": close.pct_change().dropna(),
        "features_df": features_df,
        "prep_info": prep_info,
    }


# ══════════════════════════════════════════════
#  2. WALK-FORWARD VALIDATION METRICS
# ══════════════════════════════════════════════

def compute_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    """Compute comprehensive forecast evaluation metrics."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)

    n = min(len(actual), len(predicted))
    actual = actual[:n]
    predicted = predicted[:n]

    if n == 0:
        return {"mape": 0, "rmse": 0, "mae": 0, "directional_accuracy": 0}

    # MAPE
    mask = actual != 0
    if mask.any():
        mape = float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)
    else:
        mape = 0.0

    # RMSE
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))

    # MAE
    mae = float(np.mean(np.abs(actual - predicted)))

    # Directional accuracy
    if n >= 2:
        actual_dir = np.diff(actual) > 0
        pred_dir = np.diff(predicted) > 0
        dir_acc = float(np.mean(actual_dir == pred_dir) * 100)
    else:
        dir_acc = 0.0

    return {
        "mape": round(mape, 2),
        "rmse": round(rmse, 2),
        "mae": round(mae, 2),
        "directional_accuracy": round(dir_acc, 2),
    }


# ══════════════════════════════════════════════
#  3. AUTO-TUNED ARIMA
# ══════════════════════════════════════════════

def forecast_arima(close: pd.Series, days: int, test_size: int = 0) -> dict:
    """Auto-tuned ARIMA forecast via pmdarima, with statsmodels fallback."""
    values = close.values.astype(float)

    if test_size > 0 and test_size < len(values):
        train = values[:-test_size]
        test = values[-test_size:]
    else:
        train = values
        test = None

    order_used = None
    aic_val = None

    if _HAS_PMDARIMA:
        model = pm.auto_arima(
            train,
            start_p=1, max_p=5,
            start_q=1, max_q=5,
            max_d=2,
            seasonal=False,
            stepwise=True,
            suppress_warnings=True,
            error_action="ignore",
            trace=False,
            n_fits=30,
        )
        order_used = model.order
        aic_val = round(float(model.aic()), 2)

        fc, conf = model.predict(n_periods=days, return_conf_int=True, alpha=0.05)
        forecast_values = fc.tolist()
        lower_bound = conf[:, 0].tolist()
        upper_bound = conf[:, 1].tolist()

        if test is not None:
            test_fc = model.predict(n_periods=len(test), return_conf_int=False)
            metrics = compute_metrics(test, test_fc)
        else:
            fitted = model.predict_in_sample()
            metrics = compute_metrics(train[1:], fitted[1:])

    elif _HAS_STATSMODELS:
        # Fallback: grid search
        best_aic = np.inf
        best_order = (1, 1, 0)
        for p in range(0, 4):
            for q in range(0, 3):
                for d in range(0, 3):
                    try:
                        m = StatsARIMA(train, order=(p, d, q))
                        res = m.fit()
                        if res.aic < best_aic:
                            best_aic = res.aic
                            best_order = (p, d, q)
                    except Exception:
                        continue

        model = StatsARIMA(train, order=best_order)
        fitted_model = model.fit()
        order_used = best_order
        aic_val = round(float(fitted_model.aic), 2)

        fc_result = fitted_model.get_forecast(steps=days)
        forecast_values = fc_result.predicted_mean.tolist()
        conf_int = fc_result.conf_int(alpha=0.05)
        lower_bound = [float(v[0]) for v in conf_int]
        upper_bound = [float(v[1]) for v in conf_int]

        if test is not None:
            test_fc = fitted_model.get_forecast(steps=len(test)).predicted_mean
            metrics = compute_metrics(test, test_fc)
        else:
            fitted = fitted_model.fittedvalues
            metrics = compute_metrics(train[1:], fitted[1:])
    else:
        raise HTTPException(status_code=500, detail="Tidak ada library ARIMA yang terinstal.")

    return {
        "forecast_values": [round(float(v), 2) for v in forecast_values],
        "lower_bound": [round(float(v), 2) for v in lower_bound],
        "upper_bound": [round(float(v), 2) for v in upper_bound],
        "model_name": f"Auto-ARIMA{order_used}",
        "aic": aic_val,
        "metrics": metrics,
    }


# ══════════════════════════════════════════════
#  4. LSTM DEEP LEARNING (PyTorch)
# ══════════════════════════════════════════════

class LSTMModel(nn.Module if _HAS_TORCH else object):
    """2-layer LSTM for time series forecasting."""
    def __init__(self, n_features, hidden1=64, hidden2=32):
        super().__init__()
        self.lstm1 = nn.LSTM(n_features, hidden1, batch_first=True)
        self.dropout1 = nn.Dropout(0.2)
        self.lstm2 = nn.LSTM(hidden1, hidden2, batch_first=True)
        self.dropout2 = nn.Dropout(0.2)
        self.fc1 = nn.Linear(hidden2, 16)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(16, 1)

    def forward(self, x):
        out, _ = self.lstm1(x)
        out = self.dropout1(out)
        out, _ = self.lstm2(out)
        out = self.dropout2(out[:, -1, :])  # take last time step
        out = self.relu(self.fc1(out))
        out = self.fc2(out)
        return out


def forecast_lstm(features_df: pd.DataFrame, days: int, test_size: int = 0) -> dict:
    """
    2-layer LSTM with multi-variate features (PyTorch).
    Architecture uses LSTM, Dropout, and Dense layers.
    """
    if not _HAS_TORCH:
        raise HTTPException(status_code=500,
                            detail="PyTorch belum terinstal. Gunakan model ARIMA, XGBOOST, atau ENSEMBLE.")
    if not _HAS_SKLEARN:
        raise HTTPException(status_code=500, detail="scikit-learn belum terinstal.")

    LOOK_BACK = 30

    # ── Select features ──
    feature_cols = ["close", "sma5", "sma20", "rsi14", "bb_width", "macd"]
    available_cols = [c for c in feature_cols if c in features_df.columns]
    data = features_df[available_cols].values.astype(float)

    if len(data) < LOOK_BACK + 20:
        raise HTTPException(status_code=400,
                            detail=f"Data tidak cukup untuk LSTM. Minimum {LOOK_BACK + 20} hari, tersedia {len(data)}.")

    # ── Scale data ──
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled = scaler.fit_transform(data)

    close_scaler = MinMaxScaler(feature_range=(0, 1))
    close_data = features_df[["close"]].values.astype(float)
    close_scaler.fit(close_data)

    # ── Create sequences ──
    def create_sequences(arr, look_back):
        X, y = [], []
        for i in range(look_back, len(arr)):
            X.append(arr[i - look_back:i])
            y.append(arr[i, 0])  # predict close (column 0)
        return np.array(X), np.array(y)

    X, y = create_sequences(scaled, LOOK_BACK)

    if len(X) < 20:
        raise HTTPException(status_code=400, detail="Data terlalu sedikit untuk training LSTM.")

    # ── Train/Val split ──
    if test_size > 0 and test_size < len(X):
        X_train, X_val = X[:-test_size], X[-test_size:]
        y_train, y_val = y[:-test_size], y[-test_size:]
    else:
        split = int(len(X) * 0.8)
        X_train, X_val = X[:split], X[split:]
        y_train, y_val = y[:split], y[split:]

    n_features = X_train.shape[2]

    # ── Convert to tensors ──
    X_train_t = torch.FloatTensor(X_train)
    y_train_t = torch.FloatTensor(y_train).unsqueeze(1)
    X_val_t = torch.FloatTensor(X_val)
    y_val_t = torch.FloatTensor(y_val).unsqueeze(1)

    # ── Build & train model ──
    model = LSTMModel(n_features)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    # Training with early stopping
    best_val_loss = float("inf")
    patience = 7
    patience_counter = 0
    best_state = None
    epochs = 80

    # Mini-batch training
    batch_size = 32
    n_batches = max(1, len(X_train_t) // batch_size)

    for epoch in range(epochs):
        model.train()
        # Shuffle training data
        perm = torch.randperm(len(X_train_t))
        X_shuffled = X_train_t[perm]
        y_shuffled = y_train_t[perm]

        epoch_loss = 0.0
        for i in range(n_batches):
            start = i * batch_size
            end = min(start + batch_size, len(X_train_t))
            X_batch = X_shuffled[start:end]
            y_batch = y_shuffled[start:end]

            optimizer.zero_grad()
            output = model(X_batch)
            loss = criterion(output, y_batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            epoch_loss += loss.item()

        # Validation
        model.eval()
        with torch.no_grad():
            val_pred = model(X_val_t)
            val_loss = criterion(val_pred, y_val_t).item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break

    # Restore best weights
    if best_state is not None:
        model.load_state_dict(best_state)

    # ── Validation metrics ──
    model.eval()
    with torch.no_grad():
        val_pred_scaled = model(X_val_t).numpy().flatten()

    val_pred = close_scaler.inverse_transform(val_pred_scaled.reshape(-1, 1)).flatten()
    val_actual = close_scaler.inverse_transform(y_val.reshape(-1, 1)).flatten()
    metrics = compute_metrics(val_actual, val_pred)

    # ── Recursive forecasting ──
    last_sequence = scaled[-LOOK_BACK:].copy()
    predictions_scaled = []

    model.eval()
    for _ in range(days):
        inp = torch.FloatTensor(last_sequence).unsqueeze(0)  # (1, LOOK_BACK, n_features)
        with torch.no_grad():
            pred = model(inp).item()
        predictions_scaled.append(pred)

        # Shift window
        new_row = last_sequence[-1].copy()
        new_row[0] = pred
        last_sequence = np.vstack([last_sequence[1:], new_row])

    # Inverse transform
    pred_array = np.array(predictions_scaled).reshape(-1, 1)
    forecast_values = close_scaler.inverse_transform(pred_array).flatten()

    # ── Confidence intervals ──
    residuals = val_actual - val_pred
    std_err = float(np.std(residuals)) if len(residuals) > 0 else 0
    lower_bound = []
    upper_bound = []
    for h, fv in enumerate(forecast_values, 1):
        margin = 1.96 * std_err * np.sqrt(h)
        lower_bound.append(float(fv - margin))
        upper_bound.append(float(fv + margin))

    return {
        "forecast_values": [round(float(v), 2) for v in forecast_values],
        "lower_bound": [round(float(v), 2) for v in lower_bound],
        "upper_bound": [round(float(v), 2) for v in upper_bound],
        "model_name": f"LSTM(64→32) lookback={LOOK_BACK}",
        "aic": None,
        "metrics": metrics,
    }


# ══════════════════════════════════════════════
#  5. XGBOOST WITH LAG FEATURES
# ══════════════════════════════════════════════

def forecast_xgboost(features_df: pd.DataFrame, days: int, test_size: int = 0) -> dict:
    """
    XGBoost gradient-boosted trees with lag features for time series.
    Creates rich lag features + technical indicators as inputs.
    """
    if not _HAS_XGBOOST:
        raise HTTPException(status_code=500, detail="XGBoost belum terinstal.")
    if not _HAS_SKLEARN:
        raise HTTPException(status_code=500, detail="scikit-learn belum terinstal.")

    close = features_df["close"].values.astype(float)
    n_lags = 30

    if len(close) < n_lags + 20:
        raise HTTPException(status_code=400,
                            detail=f"Data tidak cukup untuk XGBoost. Minimum {n_lags + 20} hari.")

    # ── Build lag features ──
    feature_cols = ["close", "return", "sma5", "sma20", "rsi14", "bb_width", "macd"]
    available_cols = [c for c in feature_cols if c in features_df.columns]
    base_data = features_df[available_cols].copy()

    # Add lag features for close price
    for lag in [1, 2, 3, 5, 7, 14, 21, 30]:
        if lag < len(base_data):
            base_data[f"close_lag_{lag}"] = base_data["close"].shift(lag)

    # Add rolling statistics
    for window in [5, 10, 20]:
        if window < len(base_data):
            base_data[f"close_roll_mean_{window}"] = base_data["close"].rolling(window).mean()
            base_data[f"close_roll_std_{window}"] = base_data["close"].rolling(window).std()

    # Day of week
    base_data["dayofweek"] = features_df.index.dayofweek

    base_data = base_data.dropna()

    if len(base_data) < 50:
        raise HTTPException(status_code=400, detail="Data tidak cukup setelah feature engineering.")

    # ── Split features / target ──
    target = base_data["close"].values
    feature_names = [c for c in base_data.columns if c != "close"]
    X = base_data[feature_names].values
    y = target

    # ── Train / test split ──
    if test_size > 0 and test_size < len(X):
        X_train, X_test = X[:-test_size], X[-test_size:]
        y_train, y_test = y[:-test_size], y[-test_size:]
    else:
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

    # ── Train model ──
    model = xgb.XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        verbosity=0,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # ── Validation metrics ──
    test_pred = model.predict(X_test)
    metrics = compute_metrics(y_test, test_pred)

    # ── Recursive forecasting ──
    # Start from the last known row of features
    last_features = base_data.iloc[-1:].copy()
    forecast_values = []
    current_close = float(base_data["close"].iloc[-1])
    recent_closes = list(base_data["close"].values[-30:])

    for step in range(days):
        # Build feature row for next prediction
        new_row = {}
        for col in feature_names:
            if col.startswith("close_lag_"):
                lag = int(col.split("_")[-1])
                if lag <= len(recent_closes):
                    new_row[col] = recent_closes[-lag]
                else:
                    new_row[col] = recent_closes[0]
            elif col.startswith("close_roll_mean_"):
                window = int(col.split("_")[-1])
                vals = recent_closes[-window:]
                new_row[col] = np.mean(vals)
            elif col.startswith("close_roll_std_"):
                window = int(col.split("_")[-1])
                vals = recent_closes[-window:]
                new_row[col] = np.std(vals) if len(vals) > 1 else 0
            elif col == "return":
                new_row[col] = (current_close - recent_closes[-2]) / recent_closes[-2] if len(recent_closes) >= 2 and recent_closes[-2] != 0 else 0
            elif col == "dayofweek":
                new_row[col] = (features_df.index[-1].weekday() + step + 1) % 5
            elif col in last_features.columns:
                new_row[col] = float(last_features[col].iloc[0])
            else:
                new_row[col] = 0.0

        X_pred = np.array([[new_row[c] for c in feature_names]])
        pred = float(model.predict(X_pred)[0])
        forecast_values.append(pred)

        # Update state
        recent_closes.append(pred)
        current_close = pred

    # ── Confidence intervals ──
    residuals = y_test - test_pred
    std_err = float(np.std(residuals)) if len(residuals) > 0 else 0
    lower_bound = []
    upper_bound = []
    for h, fv in enumerate(forecast_values, 1):
        margin = 1.96 * std_err * np.sqrt(h)
        lower_bound.append(float(fv - margin))
        upper_bound.append(float(fv + margin))

    return {
        "forecast_values": [round(float(v), 2) for v in forecast_values],
        "lower_bound": [round(float(v), 2) for v in lower_bound],
        "upper_bound": [round(float(v), 2) for v in upper_bound],
        "model_name": f"XGBoost(n=300, depth=6)",
        "aic": None,
        "metrics": metrics,
    }


# ══════════════════════════════════════════════
#  6. ENSEMBLE (best available models)
# ══════════════════════════════════════════════

def forecast_ensemble(close: pd.Series, features_df: pd.DataFrame,
                      days: int, test_size: int = 0) -> dict:
    """
    Weighted ensemble of available models.
    Weights: ARIMA 30%, deep learning / ML model 70%.
    Falls back gracefully depending on available libraries.
    """
    results = {}
    weights = {}

    # Always try ARIMA
    try:
        results["arima"] = forecast_arima(close, days, test_size)
        weights["arima"] = 0.3
    except Exception as e:
        logger.warning(f"ARIMA failed in ensemble: {e}")

    # Try LSTM first, fallback to XGBoost
    ml_model_used = None
    if _HAS_TORCH:
        try:
            results["lstm"] = forecast_lstm(features_df, days, test_size)
            weights["lstm"] = 0.4
            ml_model_used = "lstm"
        except Exception as e:
            logger.warning(f"LSTM failed in ensemble: {e}")

    if _HAS_XGBOOST:
        try:
            results["xgboost"] = forecast_xgboost(features_df, days, test_size)
            if ml_model_used == "lstm":
                weights["xgboost"] = 0.3
            else:
                weights["xgboost"] = 0.7
        except Exception as e:
            logger.warning(f"XGBoost failed in ensemble: {e}")

    if not results:
        raise HTTPException(status_code=500, detail="Semua model gagal dalam ensemble.")

    # Normalize weights
    total_w = sum(weights.values())
    if total_w > 0:
        weights = {k: v / total_w for k, v in weights.items()}

    # Blend forecasts
    ensemble_fc = np.zeros(days)
    ensemble_lb = np.zeros(days)
    ensemble_ub = np.zeros(days)
    ensemble_metrics = {"mape": 0, "rmse": 0, "mae": 0, "directional_accuracy": 0}

    for key, w in weights.items():
        res = results[key]
        ensemble_fc += w * np.array(res["forecast_values"])
        ensemble_lb += w * np.array(res["lower_bound"])
        ensemble_ub += w * np.array(res["upper_bound"])
        for mk in ensemble_metrics:
            ensemble_metrics[mk] += w * res["metrics"][mk]

    ensemble_metrics = {k: round(v, 2) for k, v in ensemble_metrics.items()}

    # Build model name
    parts = []
    for key, w in weights.items():
        name = results[key]["model_name"].split("(")[0]
        parts.append(f"{name} {w:.0%}")
    model_name = "Ensemble (" + " + ".join(parts) + ")"

    sub_models = {}
    for key in results:
        sub_models[key] = {
            "name": results[key]["model_name"],
            "metrics": results[key]["metrics"],
            "weight": round(weights.get(key, 0), 2),
        }

    return {
        "forecast_values": [round(float(v), 2) for v in ensemble_fc],
        "lower_bound": [round(float(v), 2) for v in ensemble_lb],
        "upper_bound": [round(float(v), 2) for v in ensemble_ub],
        "model_name": model_name,
        "aic": results.get("arima", {}).get("aic"),
        "metrics": ensemble_metrics,
        "sub_models": sub_models,
    }


# ══════════════════════════════════════════════
#  7. MAIN ENDPOINT
# ══════════════════════════════════════════════

@router.get("")
def get_forecast(ticker: str, days: int = 14, model_type: str = "ARIMA"):
    """
    Run forecast for a given ticker.
    Query params: ticker, days, and model_type.
    """
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker wajib diisi.")
    if days < 1 or days > 60:
        raise HTTPException(status_code=400, detail="Jumlah hari forecast harus antara 1 - 60.")

    ticker = ticker.upper()
    model_type = model_type.upper()

    try:
        # ── 1. Fetch & prepare data ──
        df = fetch_data(ticker, period="2y")

        if len(df) < 60:
            raise HTTPException(status_code=404,
                                detail=f"Data histori terlalu sedikit untuk {ticker} "
                                       f"(minimum 60 hari, tersedia {len(df)}).")

        cleaned = clean_data(df)
        close = cleaned["close"]
        features_df = cleaned["features_df"]
        prep_info = cleaned["prep_info"]

        # Walk-forward test size: 20% of data, capped at 60 days
        test_size = min(int(len(close) * 0.2), 60)

        # ── 2. Run model ──
        if model_type == "ARIMA":
            result = forecast_arima(close, days, test_size)
        elif model_type == "LSTM":
            result = forecast_lstm(features_df, days, test_size)
        elif model_type == "XGBOOST":
            result = forecast_xgboost(features_df, days, test_size)
        elif model_type == "ENSEMBLE":
            result = forecast_ensemble(close, features_df, days, test_size)
        else:
            raise HTTPException(status_code=400,
                                detail=f"Model '{model_type}' tidak didukung. "
                                       f"Gunakan: ARIMA, LSTM, XGBOOST, atau ENSEMBLE.")

        # ── 3. Generate forecast dates ──
        last_date = close.index[-1]
        # Detect if asset trades on weekends (e.g. Crypto) by checking last 14 days
        trades_on_weekends = any(d.weekday() >= 5 for d in close.index[-14:])
        
        forecast_dates = []
        current_date = last_date
        for _ in range(days):
            current_date += timedelta(days=1)
            if not trades_on_weekends:
                while current_date.weekday() >= 5:
                    current_date += timedelta(days=1)
            forecast_dates.append(current_date.strftime("%Y-%m-%d"))

        # ── 4. Historical data for charting (last 60 days) ──
        hist_n = min(60, len(close))
        hist_dates = [d.strftime("%Y-%m-%d") for d in close.index[-hist_n:]]
        hist_values = [round(float(v), 2) for v in close.values[-hist_n:]]

        # ── 5. Trend analysis ──
        f_values = result["forecast_values"]
        price_start = f_values[0]
        price_end = f_values[-1]
        change_pct = ((price_end - price_start) / price_start) * 100 if price_start else 0

        if change_pct > 1.5:
            trend = "BULLISH"
        elif change_pct < -1.5:
            trend = "BEARISH"
        else:
            trend = "SIDEWAYS"

        support = min(result["lower_bound"])
        resistance = max(result["upper_bound"])
        
        # ── Connect lines visually by prepending last historical point ──
        forecast_dates.insert(0, hist_dates[-1])
        f_values.insert(0, hist_values[-1])
        result["lower_bound"].insert(0, hist_values[-1])
        result["upper_bound"].insert(0, hist_values[-1])

        # ── 6. Build response ──
        response = {
            "ticker": ticker,
            "days": days,
            "historical": {
                "dates": hist_dates,
                "values": hist_values,
            },
            "forecast": {
                "dates": forecast_dates,
                "values": f_values,
                "lower_bound": result["lower_bound"],
                "upper_bound": result["upper_bound"],
            },
            "analysis": {
                "trend": trend,
                "trend_pct": round(change_pct, 2),
                "support": round(support, 2),
                "resistance": round(resistance, 2),
            },
            "model_info": {
                "name": result["model_name"],
                "aic": result.get("aic"),
                "mse": round(result["metrics"]["rmse"] ** 2, 2) if result["metrics"]["rmse"] else 0,
                "rmse": result["metrics"]["rmse"],
                "mape": result["metrics"]["mape"],
                "mae": result["metrics"]["mae"],
                "directional_accuracy": result["metrics"]["directional_accuracy"],
            },
            "data_preparation": {
                "total_data_points": prep_info["raw_count"],
                "missing_filled": prep_info["missing_filled"],
                "outliers_capped": prep_info["outliers_capped"],
                "is_stationary": prep_info["is_stationary"],
                "adf_pvalue": prep_info["adf_pvalue"],
                "test_set_size": test_size,
            },
        }

        # Add sub-model info for ensemble
        if "sub_models" in result:
            response["sub_models"] = result["sub_models"]

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in forecasting {ticker}: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
