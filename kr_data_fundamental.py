"""
kr_data_fundamental.py  v5.4
핵심 변경:
- PBR 시계열: FinanceDataReader KRX 일별 데이터를 primary로 사용
  fdr.DataReader(symbol) → 일별 OHLCV + PBR/PER/EPS/BPS/DIV 포함
- yfinance는 ROE/DPS/DIV 등 FDR에 없는 항목만 보조로 사용
- funda_snapshot: FDR 최신값 우선, yfinance 보완
"""
import numpy as np
import pandas as pd
import FinanceDataReader as fdr
import yfinance as yf
from datetime import datetime, timedelta


def is_valid(v):
    return v is not None and not pd.isna(v) and np.isfinite(v)


def _to_yf_symbol(symbol: str) -> str:
    return f"{symbol}.KS"


def _load_fdr_data(symbol: str) -> pd.DataFrame:
    """
    FDR로 전체 이력 로드.
    컬럼: Open High Low Close Volume + Change Comp MarketCap
    KRX 종목은 펀더멘털 컬럼(PBR 등)이 없을 수 있음 → 별도 처리
    """
    try:
        df = fdr.DataReader(symbol)
        if df is None or df.empty:
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        return df
    except Exception:
        return pd.DataFrame()


def _load_fdr_fundamental_history(symbol: str) -> pd.Series:
    """
    FDR KRX fundamental 일별 PBR 시계열.
    fdr.DataReader(symbol)에 PBR 컬럼이 없으면
    fdr.StockListing + 날짜별 조회로 대체.
    """
    # 방법 1: DataReader에 PBR 컬럼 포함 여부 확인
    try:
        df = fdr.DataReader(symbol)
        if df is not None and not df.empty and "PBR" in df.columns:
            df.index = pd.to_datetime(df.index)
            pbr = pd.to_numeric(df["PBR"], errors="coerce").dropna()
            pbr = pbr[pbr > 0]
            if len(pbr) >= 12:
                return pbr, "fdr-direct"
    except Exception:
        pass

    return pd.Series(dtype=float), "NONE"


def _get_yf_info(symbol: str) -> dict:
    try:
        return yf.Ticker(_to_yf_symbol(symbol)).info or {}
    except Exception:
        return {}


def _get_yf_equity_latest(symbol: str) -> float | None:
    """yfinance 분기 balance sheet에서 최신 Stockholders Equity"""
    try:
        ticker = yf.Ticker(_to_yf_symbol(symbol))
        for bs in [ticker.quarterly_balance_sheet, ticker.balance_sheet]:
            if bs is None or bs.empty:
                continue
            for row_name in ["Stockholders Equity", "Common Stock Equity",
                             "Total Equity Gross Minority Interest"]:
                if row_name in bs.index:
                    row = pd.to_numeric(bs.loc[row_name], errors="coerce").dropna()
                    if len(row) > 0:
                        return float(row.iloc[0])
    except Exception:
        pass
    return None


def build_pbr_statistics(symbol, price_df):
    """
    v5.4 — FDR 일별 PBR primary
    """
    try:
        pbr_daily, source = _load_fdr_fundamental_history(symbol)

        # FDR에 PBR 없으면 yfinance equity + 월별 주가로 구성
        if len(pbr_daily) == 0:
            try:
                info = _get_yf_info(symbol)
                shares_out = float(
                    info.get("sharesOutstanding")
                    or info.get("impliedSharesOutstanding")
                    or 0
                )
                current_price = float(
                    info.get("currentPrice")
                    or info.get("regularMarketPrice")
                    or 0
                )
                equity_latest = _get_yf_equity_latest(symbol)

                if shares_out > 0 and equity_latest and equity_latest > 0 and current_price > 0:
                    # 현재 PBR = 시가총액 / 자본
                    current_marketcap = current_price * shares_out
                    current_pbr_now = current_marketcap / equity_latest

                    if 0.1 < current_pbr_now < 30:
                        # 현재 BPS 역산 후 price_df 주가 이력에 적용
                        current_bps = current_price / current_pbr_now
                        price_hist = price_df["Close"].resample("ME").last().dropna()
                        pbr_daily = price_hist / current_bps
                        pbr_daily = pbr_daily[(pbr_daily > 0) & (pbr_daily < 50)]
                        source = "yfinance-equity-reverse"
            except Exception:
                pass

        if len(pbr_daily) == 0:
            return {
                "available": False,
                "reason": "PBR 데이터 없음 (FDR + yfinance 모두 실패)",
                "current_pbr": None, "mean_pbr": None, "std_pbr": None,
                "zscore": None, "sample_months": 0, "sample_grade": "N/A",
                "percentile": None, "source": "NONE",
            }

        # 월말 리샘플링
        pbr = pbr_daily.resample("ME").last().dropna()
        pbr = pbr[(pbr > 0) & (pbr < 50)]

        if len(pbr) < 36:
            return {
                "available": False,
                "reason": f"데이터 부족(3년 미만): {len(pbr)}개월",
                "current_pbr": None, "mean_pbr": None, "std_pbr": None,
                "zscore": None, "sample_months": len(pbr),
                "sample_grade": "Abort", "percentile": None, "source": source,
            }

        pbr = pbr.tail(120)
        current_pbr  = float(pbr.iloc[-1])
        mean_pbr     = float(pbr.mean())
        std_pbr      = float(pbr.std(ddof=0))
        percentile   = float((pbr <= current_pbr).mean() * 100)
        sample_months = len(pbr)
        sample_grade  = "Full" if sample_months >= 60 else "Limited"

        std_floor = max(0.03, mean_pbr * 0.05)
        if std_pbr <= std_floor:
            return {
                "available": False, "reason": "표준편차 과소",
                "current_pbr": current_pbr, "mean_pbr": mean_pbr,
                "std_pbr": std_pbr, "zscore": None,
                "sample_months": sample_months, "sample_grade": sample_grade,
                "percentile": percentile, "source": source,
            }

        z = (current_pbr - mean_pbr) / std_pbr

        return {
            "available": True, "reason": "",
            "current_pbr": current_pbr, "mean_pbr": mean_pbr,
            "std_pbr": std_pbr, "zscore": z,
            "sample_months": sample_months, "sample_grade": sample_grade,
            "percentile": percentile, "source": source,
        }

    except Exception as e:
        return {
            "available": False, "reason": f"PBR 계산 실패: {e}",
            "current_pbr": None, "mean_pbr": None, "std_pbr": None,
            "zscore": None, "sample_months": 0, "sample_grade": "N/A",
            "percentile": None, "source": "NONE",
        }


def get_basic_fundamental_snapshot(symbol):
    """
    v5.4
    - FDR 최신 행에서 PBR/PER/BPS/EPS/DIV 우선
    - yfinance에서 ROE/DPS 보완
    """
    result = {
        "BPS": None, "PER": None, "PBR": None,
        "EPS": None, "DIV": None, "DPS": None,
    }

    # 1차: FDR
    try:
        df = fdr.DataReader(symbol)
        if df is not None and not df.empty:
            last = df.iloc[-1]
            for col in ["BPS", "PER", "PBR", "EPS", "DIV"]:
                if col in last.index:
                    v = pd.to_numeric(last[col], errors="coerce")
                    if pd.notna(v) and np.isfinite(v) and v != 0:
                        result[col] = round(float(v), 2)
    except Exception:
        pass

    # 2차: yfinance 보완 (FDR에 없는 항목)
    try:
        info = _get_yf_info(symbol)
        if info:
            # DPS
            if result["DPS"] is None:
                dps = info.get("lastDividendValue")
                if dps is not None:
                    result["DPS"] = round(float(dps), 0)

            # DIV (yfinance는 이미 퍼센트)
            if result["DIV"] is None:
                div = info.get("dividendYield")
                if div is not None:
                    result["DIV"] = round(float(div), 2)

            # PBR (FDR에 없을 때)
            if result["PBR"] is None:
                shares_out = float(
                    info.get("sharesOutstanding")
                    or info.get("impliedSharesOutstanding")
                    or 0
                )
                current_price = float(
                    info.get("currentPrice")
                    or info.get("regularMarketPrice")
                    or 0
                )
                equity = _get_yf_equity_latest(symbol)
                if equity and equity > 0 and shares_out > 0 and current_price > 0:
                    bps_calc = equity / shares_out
                    if bps_calc > 100:  # KRW 단위 확인
                        pbr_calc = current_price / bps_calc
                        result["PBR"] = round(pbr_calc, 2)
                        if result["BPS"] is None:
                            result["BPS"] = round(bps_calc, 0)

    except Exception:
        pass

    return result
