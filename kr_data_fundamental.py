import numpy as np
import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta


def is_valid(v):
    return v is not None and not pd.isna(v) and np.isfinite(v)


def build_pbr_statistics(symbol, price_df):
    """
    v4.1 안정화 버전
    - pykrx 월별 PBR 우선 사용
    - 최근 최대 120개월
    - 최소 36개월
    - 60개월 이상 Full / 36~59개월 Limited
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

        if funda is None or len(funda) == 0:
            return {
                "available": False,
                "reason": "pykrx fundamental 데이터 없음",
                "current_pbr": None,
                "mean_pbr": None,
                "std_pbr": None,
                "zscore": None,
                "sample_months": 0,
                "sample_grade": "N/A",
                "percentile": None,
                "source": "NONE",
            }

        if "PBR" not in funda.columns:
            return {
                "available": False,
                "reason": f"PBR 컬럼 없음: {list(funda.columns)}",
                "current_pbr": None,
                "mean_pbr": None,
                "std_pbr": None,
                "zscore": None,
                "sample_months": 0,
                "sample_grade": "N/A",
                "percentile": None,
                "source": "NONE",
            }

        pbr = pd.to_numeric(funda["PBR"], errors="coerce").dropna()
        pbr = pbr[pbr > 0]

        if len(pbr) < 36:
            return {
                "available": False,
                "reason": f"데이터 부족(3년 미만): {len(pbr)}개월",
                "current_pbr": None,
                "mean_pbr": None,
                "std_pbr": None,
                "zscore": None,
                "sample_months": len(pbr),
                "sample_grade": "Abort",
                "percentile": None,
                "source": "pykrx",
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
                "source": "pykrx",
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
            "source": "pykrx",
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
            "source": "NONE",
        }


def get_basic_fundamental_snapshot(symbol):
    try:
        today = datetime.today().strftime("%Y%m%d")
        df = stock.get_market_fundamental_by_ticker(today)

        if df is None or len(df) == 0:
            return {}

        # 티커가 index인 경우
        if symbol in df.index:
            row = df.loc[symbol]
        else:
            # 혹시 reset_index된 형태를 대비
            temp = df.reset_index()
            symbol_col = "티커" if "티커" in temp.columns else temp.columns[0]
            hit = temp[temp[symbol_col].astype(str) == str(symbol)]
            if len(hit) == 0:
                return {}
            row = hit.iloc[0]

        return {
            "BPS": row.get("BPS", None),
            "PER": row.get("PER", None),
            "PBR": row.get("PBR", None),
            "EPS": row.get("EPS", None),
            "DIV": row.get("DIV", None),
        }

    except Exception:
        return {}
