"""
kr_data_fundamental.py  v5.2
디버그 결과 기반 수정:
- priceToBook/bookValue = NULL → Stockholders Equity / sharesOutstanding으로 BPS 직접 계산
- dividendYield = 1.23 (이미 퍼센트) → ×100 하지 않음
- lastDividendValue = 566 (KRW 정상) → 그대로 사용
- currentPrice = 183500 (KRW) → BPS 단위 판단 기준으로 사용
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


def _get_yf_ticker(symbol: str):
    return yf.Ticker(_to_yf_symbol(symbol))


def _calc_bps_from_balance_sheet(ticker, shares_out: int) -> pd.Series:
    """
    quarterly_balance_sheet의 Stockholders Equity / sharesOutstanding = BPS
    반환: 날짜 인덱스의 BPS 시계열 (KRW)
    """
    bs = ticker.quarterly_balance_sheet
    if bs is None or bs.empty:
        return pd.Series(dtype=float)

    equity_row = None
    for row_name in ["Stockholders Equity", "Common Stock Equity",
                     "Total Equity Gross Minority Interest"]:
        if row_name in bs.index:
            equity_row = bs.loc[row_name]
            break

    if equity_row is None:
        return pd.Series(dtype=float)

    equity_row = pd.to_numeric(equity_row, errors="coerce").dropna()
    equity_row.index = pd.to_datetime(equity_row.index).tz_localize(None)
    equity_row = equity_row.sort_index()

    bps = equity_row / shares_out

    # 단위 판단: KRX 종목의 재무제표는 KRW (억 단위)
    # sharesOutstanding이 주 단위면 equity도 원 단위
    # BPS가 비정상적으로 작으면(< 100) 달러 단위로 판단 → ×1350
    if bps.mean() < 100:
        bps = bps * 1350

    return bps


def _get_pbr_history(symbol: str) -> tuple[pd.Series, str]:
    """
    BPS 시계열 + 월별 주가 → PBR 시계열
    """
    try:
        ticker = _get_yf_ticker(symbol)
        info = ticker.info or {}

        shares_out = (
            info.get("sharesOutstanding")
            or info.get("impliedSharesOutstanding")
        )
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")

        if not shares_out or shares_out == 0:
            return pd.Series(dtype=float), "NONE"

        # 월별 주가 이력
        hist = ticker.history(period="10y", interval="1mo")
        if hist is None or hist.empty:
            return pd.Series(dtype=float), "NONE"

        hist.index = pd.to_datetime(hist.index).tz_localize(None)
        price_monthly = hist["Close"].resample("ME").last().dropna()

        if len(price_monthly) == 0:
            return pd.Series(dtype=float), "NONE"

        # 1차: 분기 BPS 시계열로 PBR 계산
        bps_series = _calc_bps_from_balance_sheet(ticker, shares_out)

        if len(bps_series) >= 4:
            bps_monthly = bps_series.resample("ME").last().reindex(
                price_monthly.index, method="ffill"
            )
            pbr = price_monthly / bps_monthly
            pbr = pbr.dropna()
            pbr = pbr[(pbr > 0) & (pbr < 100)]

            if len(pbr) >= 12:
                return pbr, "yfinance-bs"

        # 2차: 현재 주가로 BPS 역산 후 과거 주가에 적용
        # priceToBook이 없으므로 ROE와 PER로 PBR 추정
        # PBR = ROE × PER
        roe = info.get("returnOnEquity")
        per = info.get("trailingPE") or info.get("forwardPE")

        if roe and per and is_valid(float(roe)) and is_valid(float(per)):
            estimated_pbr_now = float(roe) * float(per)
            if 0.1 < estimated_pbr_now < 50 and current_price:
                current_bps = float(current_price) / estimated_pbr_now
                pbr_estimated = price_monthly / current_bps
                pbr_estimated = pbr_estimated.dropna()
                pbr_estimated = pbr_estimated[(pbr_estimated > 0) & (pbr_estimated < 100)]
                if len(pbr_estimated) >= 12:
                    return pbr_estimated, "yfinance-roe-per-estimated"

        return pd.Series(dtype=float), "NONE"

    except Exception:
        return pd.Series(dtype=float), "NONE"


def build_pbr_statistics(symbol, price_df):
    """v5.2"""
    try:
        pbr, source = _get_pbr_history(symbol)

        # FDR fallback
        if len(pbr) == 0:
            try:
                df = fdr.DataReader(symbol)
                if df is not None and "PBR" in df.columns:
                    df.index = pd.to_datetime(df.index)
                    pbr_daily = pd.to_numeric(df["PBR"], errors="coerce").dropna()
                    pbr_daily = pbr_daily[pbr_daily > 0]
                    if len(pbr_daily) > 0:
                        pbr = pbr_daily.resample("ME").last().dropna()
                        source = "fdr"
            except Exception:
                pass

        if len(pbr) == 0:
            return {
                "available": False,
                "reason": "PBR 데이터 없음 (yfinance + FDR 모두 실패)",
                "current_pbr": None, "mean_pbr": None, "std_pbr": None,
                "zscore": None, "sample_months": 0, "sample_grade": "N/A",
                "percentile": None, "source": "NONE",
            }

        if len(pbr) < 36:
            return {
                "available": False,
                "reason": f"데이터 부족(3년 미만): {len(pbr)}개월",
                "current_pbr": None, "mean_pbr": None, "std_pbr": None,
                "zscore": None, "sample_months": len(pbr),
                "sample_grade": "Abort", "percentile": None, "source": source,
            }

        pbr = pbr.tail(120)
        current_pbr = float(pbr.iloc[-1])
        mean_pbr    = float(pbr.mean())
        std_pbr     = float(pbr.std(ddof=0))
        percentile  = float((pbr <= current_pbr).mean() * 100)
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
    v5.2 — 디버그 결과 기반 단위 보정
    - dividendYield: yfinance KS 종목은 이미 퍼센트(1.23 = 1.23%) → 그대로
    - lastDividendValue: KRW 단위 정상 → 그대로
    - bookValue/trailingEps: NULL → BPS는 balance sheet에서 직접 계산
    """
    try:
        ticker = _get_yf_ticker(symbol)
        info   = ticker.info or {}

        if not info:
            return {}

        per = info.get("trailingPE") or info.get("forwardPE")
        pbr = info.get("priceToBook")   # 삼성전자는 NULL
        roe = info.get("returnOnEquity")
        div = info.get("dividendYield") # 이미 퍼센트값 (1.23 = 1.23%)
        dps = info.get("lastDividendValue")  # KRW 정상

        # BPS: balance sheet에서 직접 계산
        shares_out = (
            info.get("sharesOutstanding")
            or info.get("impliedSharesOutstanding")
        )
        bps = None
        if shares_out and shares_out > 0:
            bps_series = _calc_bps_from_balance_sheet(ticker, shares_out)
            if len(bps_series) > 0:
                bps = float(bps_series.iloc[-1])

        # EPS: ROE × BPS
        eps = None
        if roe is not None and bps is not None:
            eps = float(roe) * bps

        # PBR: currentPrice / BPS (priceToBook이 없을 때)
        if pbr is None and bps and bps > 0:
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            if current_price:
                pbr = float(current_price) / bps

        return {
            "BPS": round(bps, 0) if bps is not None else None,
            "PER": round(float(per), 2) if per is not None else None,
            "PBR": round(float(pbr), 2) if pbr is not None else None,
            "EPS": round(eps, 0) if eps is not None else None,
            "DIV": round(float(div), 2) if div is not None else None,
            "DPS": round(float(dps), 0) if dps is not None else None,
        }

    except Exception:
        return {}
