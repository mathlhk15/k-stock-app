import numpy as np
import pandas as pd
import FinanceDataReader as fdr


def build_pbr_statistics(symbol, price_df):

    try:

        funda = fdr.DataReader(symbol, "2010")

    except:

        return {"available": False}

    if "Close" not in price_df:
        return {"available": False}

    monthly = price_df["Close"].resample("M").last()

    if len(monthly) < 36:

        return {"available": False, "reason": "데이터 부족"}

    mean = monthly.mean()
    std = monthly.std()

    current = monthly.iloc[-1]

    if std == 0:
        return {"available": False}

    z = (current - mean) / std

    return {

        "available": True,
        "current_pbr": round(current, 3),
        "mean_pbr": round(mean, 3),
        "std_pbr": round(std, 3),
        "zscore": round(z, 3),
        "sample_months": len(monthly)

    }