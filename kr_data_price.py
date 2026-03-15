import pandas as pd
import FinanceDataReader as fdr
from pykrx import stock
from datetime import datetime, timedelta


def get_price_data(symbol):
    try:
        df = fdr.DataReader(symbol)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        rename_map = {}
        if "Open" not in df.columns and "시가" in df.columns:
            rename_map["시가"] = "Open"
        if "High" not in df.columns and "고가" in df.columns:
            rename_map["고가"] = "High"
        if "Low" not in df.columns and "저가" in df.columns:
            rename_map["저가"] = "Low"
        if "Close" not in df.columns and "종가" in df.columns:
            rename_map["종가"] = "Close"
        if "Volume" not in df.columns and "거래량" in df.columns:
            rename_map["거래량"] = "Volume"

        if rename_map:
            df = df.rename(columns=rename_map)

        needed = ["Open", "High", "Low", "Close", "Volume"]
        for col in needed:
            if col not in df.columns:
                return pd.DataFrame()

        return df[needed].dropna()

    except Exception:
        return pd.DataFrame()


def get_investor_flow_data(symbol):
    try:
        end = datetime.today()
        start = end - timedelta(days=370)

        df = stock.get_market_trading_volume_by_investor(
            start.strftime("%Y%m%d"),
            end.strftime("%Y%m%d"),
            symbol,
        )

        if df is None or len(df) == 0:
            return pd.DataFrame()

        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        return df
    except Exception:
        return pd.DataFrame()
