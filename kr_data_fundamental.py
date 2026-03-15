import numpy as np
import pandas as pd
import FinanceDataReader as fdr
from pykrx import stock
from datetime import datetime, timedelta


def _get_last_trading_date() -> str:
    """오늘이 주말/공휴일이면 가장 최근 거래일(평일)로 fallback"""
    today = datetime.today()
    for i in range(7):
        d = today - timedelta(days=i)
        if d.weekday() < 5:
            return d.strftime("%Y%m%d")
    return today.strftime("%Y%m%d")


def is_valid(v):
    return v is not None and not pd.isna(v) and np.isfinite(v)


def _rename_fundamental_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame()

    temp = df.copy()
    rename_map = {
        "티커": "Symbol",
        "BPS": "BPS",
        "PER": "PER",
        "PBR": "PBR",
        "EPS": "EPS",
        "DIV": "DIV",
        "DPS": "DPS",
        "배당수익률": "DIV",
        "주당배당금": "DPS",
    }
    temp = temp.rename(columns=rename_map)
    return temp


def _get_pbr_from_fdr(symbol: str) -> pd.Series:
    """
    FinanceDataReader로 PBR 시계열 가져오기.
    FDR의 DataReader는 일별 OHLCV만 반환하므로,
    KRX 상장 종목 리스트의 PBR을 활용하거나
    pykrx를 fallback으로 사용.
    """
    # 1차 시도: pykrx (빠른 네트워크 환경)
    try:
        end = datetime.today()
        start = end - timedelta(days=365 * 10 + 30)
        funda = stock.get_market_fundamental_by_date(
            start.strftime("%Y%m%d"),
            end.strftime("%Y%m%d"),
            symbol,
            timeout=10,
        )
        if funda is not None and len(funda) > 0:
            funda.index = pd.to_datetime(funda.index)
            funda = _rename_fundamental_columns(funda)
            if "PBR" in funda.columns:
                pbr = pd.to_numeric(funda["PBR"], errors="coerce").dropna()
                pbr = pbr[pbr > 0]
                if len(pbr) > 0:
                    return pbr, "pykrx"
    except Exception:
        pass

    # 2차 시도: FDR DataReader (펀더멘털 지원 종목)
    try:
        df = fdr.DataReader(symbol)
        if df is not None and "PBR" in df.columns:
            df.index = pd.to_datetime(df.index)
            pbr = pd.to_numeric(df["PBR"], errors="coerce").dropna()
            pbr = pbr[pbr > 0]
            if len(pbr) > 0:
                return pbr, "fdr"
    except Exception:
        pass

    return pd.Series(dtype=float), "NONE"


def build_pbr_statistics(symbol, price_df):
    """
    v4.3 — pykrx 실패 시 FDR fallback
    """
    try:
        pbr_daily, source = _get_pbr_from_fdr(symbol)

        if len(pbr_daily) == 0:
            return {
                "available": False,
                "reason": "PBR 데이터 없음 (pykrx + FDR 모두 실패)",
                "current_pbr": None,
                "mean_pbr": None,
                "std_pbr": None,
                "zscore": None,
                "sample_months": 0,
                "sample_grade": "N/A",
                "percentile": None,
                "source": "NONE",
            }

        # 월말 리샘플링
        pbr = pbr_daily.resample("ME").last().dropna()

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
                "source": source,
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
                "source": source,
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
            "source": source,
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
    """
    v4.3 — pykrx 실패 시 FDR fallback
    """
    # 1차: pykrx
    try:
        today = _get_last_trading_date()
        df = stock.get_market_fundamental_by_ticker(today)

        if df is not None and len(df) > 0:
            df = _rename_fundamental_columns(df)

            if symbol in df.index:
                row = df.loc[symbol]
            else:
                temp = df.reset_index()
                symbol_col = "Symbol" if "Symbol" in temp.columns else temp.columns[0]
                hit = temp[temp[symbol_col].astype(str) == str(symbol)]
                if len(hit) > 0:
                    row = hit.iloc[0]
                    return {
                        "BPS": row.get("BPS", None),
                        "PER": row.get("PER", None),
                        "PBR": row.get("PBR", None),
                        "EPS": row.get("EPS", None),
                        "DIV": row.get("DIV", None),
                        "DPS": row.get("DPS", None),
                    }
    except Exception:
        pass

    # 2차: FDR
    try:
        df2 = fdr.DataReader(symbol)
        if df2 is not None and len(df2) > 0:
            last = df2.iloc[-1]
            result = {}
            for col in ["BPS", "PER", "PBR", "EPS", "DIV", "DPS"]:
                result[col] = float(last[col]) if col in last.index and pd.notna(last[col]) else None
            if any(v is not None for v in result.values()):
                return result
    except Exception:
        pass

    return {}
