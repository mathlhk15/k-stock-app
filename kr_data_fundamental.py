"""
kr_data_fundamental.py  v5.3
핵심 수정:
- PBR 시계열: quarterly(4분기) → annual(최대 4년) + 월별 주가 연결
- 현재 PBR: marketCap / Stockholders Equity (가장 정확)
- BPS: Stockholders Equity / sharesOutstanding (보통주 기준)
- funda_snapshot: 계산값 신뢰도 향상
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


def _extract_equity_series(ticker) -> pd.Series:
    """
    연간 + 분기 balance_sheet에서 보통주 자본(Stockholders Equity) 시계열 추출.
    연간 우선, 분기로 최신값 보완.
    단위: 원화(KRW) — yfinance KS 종목 재무제표는 KRW 단위.
    """
    combined = {}

    # 연간 (최대 4개년)
    try:
        ann = ticker.balance_sheet
        if ann is not None and not ann.empty:
            for row_name in ["Stockholders Equity", "Common Stock Equity",
                             "Total Equity Gross Minority Interest"]:
                if row_name in ann.index:
                    row = pd.to_numeric(ann.loc[row_name], errors="coerce").dropna()
                    row.index = pd.to_datetime(row.index).tz_localize(None)
                    for dt, val in row.items():
                        combined[dt] = val
                    break
    except Exception:
        pass

    # 분기 (최근 8분기) — 연간보다 최신
    try:
        qtr = ticker.quarterly_balance_sheet
        if qtr is not None and not qtr.empty:
            for row_name in ["Stockholders Equity", "Common Stock Equity",
                             "Total Equity Gross Minority Interest"]:
                if row_name in qtr.index:
                    row = pd.to_numeric(qtr.loc[row_name], errors="coerce").dropna()
                    row.index = pd.to_datetime(row.index).tz_localize(None)
                    for dt, val in row.items():
                        combined[dt] = val  # 분기값이 덮어씀 (더 최신)
                    break
    except Exception:
        pass

    if not combined:
        return pd.Series(dtype=float)

    equity = pd.Series(combined).sort_index()
    # 단위 확인: KRW라면 삼성전자 자본은 수백조 원 → 1e11 이상
    # 달러라면 수천억 달러 → 1e11 수준이므로 구분 어려움
    # 대신 per-share 계산 후 주가와 비교로 단위 판단
    return equity


def _get_pbr_history(symbol: str) -> tuple[pd.Series, str]:
    """
    PBR 시계열 계산 전략:
    1. marketCap / Stockholders Equity → 연도별 PBR (가장 정확)
       - 연간 marketCap 이력이 없으므로 연도말 주가 × 발행주식수로 대체
    2. BPS + 월별 주가로 월별 PBR 구성
    """
    try:
        ticker = _get_yf_ticker(symbol)
        info = ticker.info or {}

        shares_out = (
            info.get("sharesOutstanding")
            or info.get("impliedSharesOutstanding")
        )
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")

        if not shares_out or not current_price:
            return pd.Series(dtype=float), "NONE"

        shares_out = float(shares_out)
        current_price = float(current_price)

        # 월별 주가 이력
        hist = ticker.history(period="10y", interval="1mo")
        if hist is None or hist.empty:
            return pd.Series(dtype=float), "NONE"

        hist.index = pd.to_datetime(hist.index).tz_localize(None)
        price_monthly = hist["Close"].resample("ME").last().dropna()

        if len(price_monthly) == 0:
            return pd.Series(dtype=float), "NONE"

        # Stockholders Equity 시계열
        equity_series = _extract_equity_series(ticker)

        if len(equity_series) >= 2:
            # equity를 월말로 forward-fill
            equity_monthly = equity_series.resample("ME").last().reindex(
                price_monthly.index, method="ffill"
            ).dropna()

            if len(equity_monthly) >= 12:
                # 시가총액 = 주가 × 발행주식수
                # PBR = 시가총액 / 자본
                marketcap_monthly = price_monthly.reindex(equity_monthly.index) * shares_out
                pbr = marketcap_monthly / equity_monthly
                pbr = pbr.dropna()
                pbr = pbr[(pbr > 0) & (pbr < 50)]

                if len(pbr) >= 12:
                    return pbr, "yfinance-equity"

        # fallback: 현재 PBR로 BPS 역산 후 과거 주가에 적용
        # 현재 PBR = marketCap / equity_latest
        if len(equity_series) > 0:
            equity_latest = float(equity_series.iloc[-1])
            if equity_latest > 0:
                current_marketcap = current_price * shares_out
                current_pbr_calc = current_marketcap / equity_latest

                if 0.1 < current_pbr_calc < 30:
                    # 고정 자본으로 과거 PBR 추정 (보수적)
                    pbr_estimated = (price_monthly * shares_out) / equity_latest
                    pbr_estimated = pbr_estimated.dropna()
                    pbr_estimated = pbr_estimated[(pbr_estimated > 0) & (pbr_estimated < 50)]
                    if len(pbr_estimated) >= 12:
                        return pbr_estimated, "yfinance-equity-fixed"

        return pd.Series(dtype=float), "NONE"

    except Exception:
        return pd.Series(dtype=float), "NONE"


def build_pbr_statistics(symbol, price_df):
    """v5.3"""
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
    v5.3 — marketCap / equity 기반 PBR, BPS 정확도 향상
    dividendYield: yfinance KS 종목은 이미 퍼센트 (1.23 = 1.23%)
    """
    try:
        ticker = _get_yf_ticker(symbol)
        info   = ticker.info or {}

        if not info:
            return {}

        per   = info.get("trailingPE") or info.get("forwardPE")
        div   = info.get("dividendYield")   # 이미 퍼센트
        dps   = info.get("lastDividendValue")
        roe   = info.get("returnOnEquity")
        shares_out = float(
            info.get("sharesOutstanding")
            or info.get("impliedSharesOutstanding")
            or 0
        )
        current_price = float(
            info.get("currentPrice") or info.get("regularMarketPrice") or 0
        )

        # BPS: 최신 Stockholders Equity / sharesOutstanding
        bps = None
        equity_series = _extract_equity_series(ticker)
        if len(equity_series) > 0 and shares_out > 0:
            equity_latest = float(equity_series.iloc[-1])
            bps_raw = equity_latest / shares_out
            # 단위 확인: 삼성전자 BPS는 약 40,000~80,000원
            # 만약 0.001 미만이면 단위 오류
            if bps_raw < 1:
                bps_raw = bps_raw * 1e9  # 십억 단위 보정 시도
            bps = round(bps_raw, 0)

        # PBR: marketCap / equity (or currentPrice / BPS)
        pbr = None
        if bps and bps > 0 and current_price > 0:
            pbr = round(current_price / bps, 2)

        # EPS: ROE × BPS
        eps = None
        if roe is not None and bps is not None:
            eps = round(float(roe) * bps, 0)

        return {
            "BPS": bps,
            "PER": round(float(per), 2) if per is not None else None,
            "PBR": pbr,
            "EPS": eps,
            "DIV": round(float(div), 2) if div is not None else None,
            "DPS": round(float(dps), 0) if dps is not None else None,
        }

    except Exception:
        return {}
