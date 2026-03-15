import pandas as pd
import numpy as np
from pykrx import stock
from datetime import datetime, timedelta


def build_pbr_statistics(symbol, price_df):
    """
    현재는 pykrx 월별 PBR 우선 사용.
    추후 DART 정밀 버전으로 교체 가능.
    """
    try:
        end = datetime.today()
        start = end - timedelta(days=365 * 10 + 30)

        funda = stock.get_market_fundamental_by_date(
            start.strftime("%Y%m%d"),
            end.strftime("%Y%m%d"),
            symbol,
            freq="m",
        )

        if funda is None or len(funda) == 0 or "PBR" not in funda.columns:
            return {
                "available": False,
                "reason": "월별 PBR 데이터 없음",
                "current_pbr": None,
                "mean_pbr": None,
                "std_pbr": None,
                "zscore": None,
                "sample_months": 0,
                "sample_grade": "N/A",
                "percentile": None,
            }

        pbr = pd.to_numeric(funda["PBR"], errors="coerce").dropna()
        pbr = pbr[pbr > 0]

        if len(pbr) < 36:
            return {
                "available": False,
                "reason": "데이터 부족(3년 미만)",
                "current_pbr": None,
                "mean_pbr": None,
                "std_pbr": None,
                "zscore": None,
                "sample_months": len(pbr),
                "sample_grade": "Abort",
                "percentile": None,
            }

        pbr = pbr.tail(120)

        current_pbr = float(pbr.iloc[-1])
        mean_pbr = float(pbr.mean())
        std_pbr = float(pbr.std(ddof=0))
        percentile = float((pbr <= current_pbr).mean() * 100)

        sample_months = len(pbr)
        sample_grade = "Full" if sample_months >= 60 else "Limited"

        std_floor = max(0.03, mean_pbr * 0.05)
        if std_pbr <= std_floor:
            return {
                "available": False,
                "reason": "표준편차 과소",
                "current_pbr": current_pbr,
                "mean_pbr": mean_pbr,
                "std_pbr": std_pbr,
                "zscore": None,
                "sample_months": sample_months,
                "sample_grade": sample_grade,
                "percentile": percentile,
            }

        z = (current_pbr - mean_pbr) / std_pbr

        return {
            "available": True,
            "reason": "",
            "current_pbr": current_pbr,
            "mean_pbr": mean_pbr,
            "std_pbr": std_pbr,
            "zscore": z,
            "sample_months": sample_months,
            "sample_grade": sample_grade,
            "percentile": percentile,
        }

    except Exception as e:
        return {
            "available": False,
            "reason": f"PBR 계산 실패: {e}",
            "current_pbr": None,
            "mean_pbr": None,
            "std_pbr": None,
            "zscore": None,
            "sample_months": 0,
            "sample_grade": "N/A",
            "percentile": None,
        }


def get_basic_fundamental_snapshot(symbol):
    try:
        today = datetime.today().strftime("%Y%m%d")
        df = stock.get_market_fundamental_by_ticker(today)

        if df is None or len(df) == 0:
            return {}

        if symbol not in df.index:
            return {}

        row = df.loc[symbol]

        return {
            "BPS": row.get("BPS", None),
            "PER": row.get("PER", None),
            "PBR": row.get("PBR", None),
            "EPS": row.get("EPS", None),
            "DIV": row.get("DIV", None),
        }

    except Exception:
        return {}
