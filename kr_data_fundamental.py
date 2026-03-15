"""
kr_data_fundamental.py  v5.1
- PBR: yfinance priceToBook 직접 조회 + 월별 추정 방식 fallback
- funda_snapshot: BPS/EPS 단위 보정 (yfinance는 원화 종목도 달러로 반환)
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


def _get_pbr_history_from_price_book(symbol: str) -> tuple[pd.Series, str]:
    """
    yfinance history(period=10y) + quarterly priceToBook 이용
    priceToBook이 분기별로 존재하면 월별 forward-fill로 시계열 구성.
    없으면 분기 재무제표 BPS + 주가로 직접 추정.
    """
    try:
        ticker = _get_yf_ticker(symbol)
        hist = ticker.history(period="10y", interval="1mo")
        if hist is None or hist.empty:
            return pd.Series(dtype=float), "NONE"

        hist.index = pd.to_datetime(hist.index).tz_localize(None)
        price_monthly = hist["Close"].resample("ME").last().dropna()

        # 1차: quarterly financials에서 PBR 직접 추출 시도
        # yfinance info에서 현재 priceToBook은 있으나 과거는 없으므로
        # BPS = bookValue (info), 과거 BPS는 quarterly_balance_sheet에서 추정
        info = ticker.info or {}
        current_pbr = info.get("priceToBook")
        shares_out = (
            info.get("sharesOutstanding")
            or info.get("impliedSharesOutstanding")
        )

        bs = ticker.quarterly_balance_sheet
        if bs is not None and not bs.empty and shares_out and shares_out > 0:
            equity_row = None
            for row_name in [
                "Stockholders Equity",
                "Common Stock Equity",
                "Total Equity Gross Minority Interest",
                "Total Stockholder Equity",
            ]:
                if row_name in bs.index:
                    equity_row = bs.loc[row_name]
                    break

            if equity_row is not None:
                equity_row = pd.to_numeric(equity_row, errors="coerce").dropna()
                equity_row.index = pd.to_datetime(equity_row.index).tz_localize(None)
                equity_row = equity_row.sort_index()

                # 원화 환산 필요 여부 체크 (yfinance KS 종목은 financials가 KRW)
                # equity가 너무 작으면(달러 단위) 환율 보정
                bps_raw = equity_row / shares_out
                # KRW BPS는 수만~수십만 원 수준, 달러면 수십~수백 수준
                if bps_raw.mean() < 1000:
                    # 달러로 보임 → 환율 적용 (고정 1350 근사)
                    bps_raw = bps_raw * 1350

                bps_monthly = bps_raw.resample("ME").last().reindex(
                    price_monthly.index, method="ffill"
                )
                pbr = price_monthly / bps_monthly
                pbr = pbr.dropna()
                pbr = pbr[pbr > 0]
                pbr = pbr[pbr < 100]  # 이상값 제거

                if len(pbr) >= 12:
                    return pbr, "yfinance-bs"

        # 2차: 현재 PBR만 있고 과거가 없을 경우 → 주가 기반 추정
        # 현재 PBR과 현재 주가로 현재 BPS 추정 후 주가 변동으로 과거 PBR 역산
        if current_pbr and is_valid(current_pbr):
            current_price = price_monthly.iloc[-1] if len(price_monthly) > 0 else None
            if current_price and current_price > 0:
                current_bps = current_price / current_pbr
                # BPS는 완만히 변하므로 고정 BPS로 역산 (보수적 추정)
                pbr_estimated = price_monthly / current_bps
                pbr_estimated = pbr_estimated.dropna()
                pbr_estimated = pbr_estimated[pbr_estimated > 0]
                pbr_estimated = pbr_estimated[pbr_estimated < 100]
                if len(pbr_estimated) >= 12:
                    return pbr_estimated, "yfinance-estimated"

        return pd.Series(dtype=float), "NONE"

    except Exception:
        return pd.Series(dtype=float), "NONE"


def build_pbr_statistics(symbol, price_df):
    """
    v5.1 — PBR 시계열 안정화
    """
    try:
        pbr, source = _get_pbr_history_from_price_book(symbol)

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
        mean_pbr = float(pbr.mean())
        std_pbr = float(pbr.std(ddof=0))
        percentile = float((pbr <= current_pbr).mean() * 100)
        sample_months = len(pbr)
        sample_grade = "Full" if sample_months >= 60 else "Limited"

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
    v5.1 — yfinance info 기반, 단위 보정 포함
    KS 종목의 yfinance info는 일부 필드가 달러 단위로 반환되므로
    bookValue/EPS는 주가 대비 크기로 KRW 여부 판단 후 보정
    """
    try:
        ticker = _get_yf_ticker(symbol)
        info = ticker.info or {}

        if not info:
            return {}

        # 현재 주가 (KRW)
        current_price_krw = info.get("currentPrice") or info.get("regularMarketPrice")

        bvps = info.get("bookValue")       # KRW or USD
        eps  = info.get("trailingEps") or info.get("forwardEps")  # KRW or USD
        per  = info.get("trailingPE") or info.get("forwardPE")    # 배율 (단위 없음)
        pbr  = info.get("priceToBook")     # 배율 (단위 없음)
        div_yield = info.get("dividendYield")   # 소수 (0.02 = 2%)
        dps  = info.get("lastDividendValue")    # KRW or USD

        # 단위 보정: bookValue가 현재가 대비 너무 작으면 달러 → KRW 환산
        FX = 1350  # 근사 환율
        if bvps is not None and current_price_krw is not None:
            if current_price_krw > 1000 and bvps < current_price_krw / 100:
                bvps = bvps * FX

        if eps is not None and current_price_krw is not None:
            if current_price_krw > 1000 and abs(eps) < current_price_krw / 100:
                eps = eps * FX

        if dps is not None and current_price_krw is not None:
            if current_price_krw > 1000 and dps < current_price_krw / 1000:
                dps = dps * FX

        # DIV는 소수(0.02) → 퍼센트(2.0)로 변환
        div_pct = float(div_yield * 100) if div_yield is not None else None

        return {
            "BPS": float(bvps) if bvps is not None else None,
            "PER": float(per)  if per  is not None else None,
            "PBR": float(pbr)  if pbr  is not None else None,
            "EPS": float(eps)  if eps  is not None else None,
            "DIV": div_pct,
            "DPS": float(dps)  if dps  is not None else None,
        }

    except Exception:
        return {}
