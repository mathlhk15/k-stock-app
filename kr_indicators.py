import pandas as pd


def add_technical_indicators(df):

    df["MA20"] = df["Close"].rolling(20).mean()

    df["MA60"] = df["Close"].rolling(60).mean()

    df["MA120"] = df["Close"].rolling(120).mean()

    delta = df["Close"].diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()

    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss

    df["RSI"] = 100 - (100 / (1 + rs))

    return df