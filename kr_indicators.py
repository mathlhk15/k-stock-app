import pandas as pd
import numpy as np


def add_technical_indicators(df):
    df = df.copy()

    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()
    df["MA120"] = df["Close"].rolling(120).mean()

    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift(1)).abs()
    low_close = (df["Low"] - df["Close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_HIST"] = df["MACD"] - df["MACD_SIGNAL"]

    df["VOL20"] = df["Volume"].rolling(20).mean()

    roll_max = df["Close"].cummax()
    df["DRAWDOWN"] = df["Close"] / roll_max - 1.0

    return df

def add_bollinger_bands(df, window=20, num_std=2):
    df = df.copy()
    rolling = df["Close"].rolling(window)
    df["BB_MID"]   = rolling.mean()
    df["BB_STD"]   = rolling.std(ddof=0)
    df["BB_UPPER"] = df["BB_MID"] + num_std * df["BB_STD"]
    df["BB_LOWER"] = df["BB_MID"] - num_std * df["BB_STD"]
    df["BB_WIDTH"] = (df["BB_UPPER"] - df["BB_LOWER"]) / df["BB_MID"] * 100
    df["BB_PCT"]   = (df["Close"] - df["BB_LOWER"]) / (df["BB_UPPER"] - df["BB_LOWER"]) * 100
    return df
