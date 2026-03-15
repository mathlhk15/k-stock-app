"""
kr_data_fundamental.py  v5.0
pykrx 완전 제거 → FinanceDataReader + yfinance 기반
"""
import numpy as np
import pandas as pd
import FinanceDataReader as fdr
import yfinance as yf
from datetime import datetime, timedelta


def is_valid(v):
    return v is not None and not pd.isna(v) and np.isfinite(v)


def _to_yf_symbol(symbol: str) -> str:
    """KRX 6자리 코드 → yfinance 심볼 (005930 → 005930.KS)"""
    return f"{symbol}.KS"


def _get_yf_info(symbol: str) -> dict:
    """yfinance로 현재 펀더멘털 스냅샷 가져오기"""
    try:
        ticker = yf.Ticker(_to_yf_symbol(symbol))
        info = ticker.info or {}
        return info
    except Exception:
        return {}


def _get_yf_pbr_history(symbol: str) -> pd.Series:
    """
    yfinance로 분기별 PBR 시계열 구성.
    book_value(BPS) + 주가 이용해 월별 PBR 추정.
    """
    try:
        yf_sym = _to_yf_symbol(symbol)
        ticker = yf.Ticker(yf_sym)

        # 분기 재무제표에서 BPS 추출
        bs = ticker.quarterly_balance_sheet
        if bs is None or bs.empty:
            return pd.Series(dtype=float)

        # 보통주 자본 / 발행주식수 = BPS
        equity_row = None
        for row_name in ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"]:
            if row_name in bs.index:
                equity_row = bs.loc[row_name]
                break

        shares_row = None
        info = ticker.info or {}
        shares_out = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")

        if equity_row is None or shares_out is None or shares_out == 0:
            return pd.Series(dtype=float)

        equity_row = pd.to_numeric(equity_row, errors="coerce").dropna()
        if len(equity_row) == 0:
            return pd.Series(dtype=float)

        # 분기말 날짜 → BPS 매핑
        bps_series = equity_row / shares_out
        bps_series.index = pd.to_datetime(bps_series.index)
        bps_series = bps_series.sort_index()

        # 주가 이력
        hist = ticker.history(period="10y", interval="1mo")
        if hist is None or hist.empty:
            return pd.Series(dtype=float)

        hist.index = pd.to_datetime(hist.index).tz_localize(None)
        price_monthly = hist["Close"].resample("ME").last().dropna()

        # BPS를 월별 price에 merge (forward fill)
        bps_monthly = bps_series.resample("ME").last().reindex(price_monthly.index, method="ffill")

        pbr = price_monthly / bps_monthly
        pbr = pbr.dropna()
        pbr = pbr[pbr > 0]
        return pbr

    except Exception:
        return pd.Series(dtype=float)


def build_pbr_statistics(symbol, price_df):
    """
    v5.0 — yfinance 기반 PBR 시계열 분석
    """
    try:
        pbr = _get_yf_pbr_history(symbol)

        if len(pbr) == 0:
            # FDR DataReader fallback (일부 종목 지원)
            try:
                df = fdr.DataReader(symbol)
                if df is not None and "PBR" in df.columns:
                    df.index = pd.to_datetime(df.index)
                    pbr_daily = pd.to_numeric(df["PBR"], errors="coerce").dropna()
                    pbr_daily = pbr_daily[pbr_daily > 0]
                    if len(pbr_daily) > 0:
                        pbr = pbr_daily.resample("ME").last().dropna()
            except Exception:
                pass

        if len(pbr) == 0:
            return {
                "available": False,
                "reason": "PBR 데이터 없음 (yfinance + FDR 모두 실패)",
                "current_pbr": None,
                "mean_pbr": None,
                "std_pbr": None,
                "zscore": None,
                "sample_months": 0,
                "sample_grade": "N/A",
                "percentile": None,
                "source": "NONE",
            }

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
                "source": "yfinance",
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
                "source": "yfinance",
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
            "source": "yfinance",
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
    v5.0 — yfinance 기반 현재 펀더멘털 스냅샷
    """
    try:
        info = _get_yf_info(symbol)
        if not info:
            return {}

        bvps = info.get("bookValue")
        eps = info.get("trailingEps") or info.get("forwardEps")
        per = info.get("trailingPE") or info.get("forwardPE")
        pbr = info.get("priceToBook")
        div = info.get("dividendYield")
        dps = info.get("lastDividendValue")

        return {
            "BPS": float(bvps) if bvps is not None else None,
            "PER": float(per) if per is not None else None,
            "PBR": float(pbr) if pbr is not None else None,
            "EPS": float(eps) if eps is not None else None,
            "DIV": float(div * 100) if div is not None else None,
            "DPS": float(dps) if dps is not None else None,
        }
    except Exception:
        return {}
