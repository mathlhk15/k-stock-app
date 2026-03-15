"""
kr_data_fundamental.py  v6.0
DART OpenAPI 기반으로 전면 업그레이드:
- PBR 시계열: DART 연도별 BPS + FDR 월별 주가 → 정확한 PBR 계산
- funda_snapshot: DART 최신 재무제표 직접 값
- ROE: DART 당기순이익 / 자본으로 직접 계산
- yfinance는 DART 실패 시 보조로만 사용
"""
import numpy as np
import pandas as pd
import FinanceDataReader as fdr
import yfinance as yf
import streamlit as st
from datetime import datetime, timedelta


def is_valid(v):
    return v is not None and not pd.isna(v) and np.isfinite(v)


def _get_dart_key() -> str | None:
    """Streamlit secrets에서 DART API 키 로드"""
    try:
        return st.secrets["DART_API_KEY"]
    except Exception:
        return None


def _to_yf_symbol(symbol: str) -> str:
    return f"{symbol}.KS"


# ──────────────────────────────────────────────
# DART 유틸
# ──────────────────────────────────────────────

def _get_dart_corp_code(symbol: str) -> str | None:
    """
    종목코드 → DART corp_code 변환
    opendartreader 사용
    """
    try:
        import opendartreader as odr
        key = _get_dart_key()
        if not key:
            return None
        odr.dart.api_key = key
        corp = odr.dart.find_corp_code(stock_code=symbol)
        if corp and len(corp) > 0:
            return corp.iloc[0]["corp_code"]
    except Exception:
        pass
    return None


def _get_dart_financial_statements(symbol: str, years: int = 5) -> pd.DataFrame:
    """
    DART에서 연도별 재무제표(단일법인, 연결 우선) 가져오기.
    반환: 연도 인덱스, 컬럼: bps, eps, roe, per, pbr, dps, div
    """
    key = _get_dart_key()
    if not key:
        return pd.DataFrame()

    try:
        import opendartreader as odr
        odr.dart.api_key = key

        current_year = datetime.today().year
        rows = []

        for year in range(current_year - years, current_year + 1):
            try:
                # 연결 재무제표 우선 (CFS), 없으면 개별 (OFS)
                for rpt_tp in ["CFS", "OFS"]:
                    df = odr.dart.finstate(
                        symbol,
                        year,
                        reprt_code="11011",  # 사업보고서
                    )
                    if df is not None and len(df) > 0:
                        break

                if df is None or len(df) == 0:
                    continue

                # 주요 항목 추출
                def _get_val(account_nm_list):
                    for nm in account_nm_list:
                        hit = df[df["account_nm"].str.contains(nm, na=False)]
                        if len(hit) > 0:
                            v = hit.iloc[0].get("thstrm_amount") or hit.iloc[0].get("thstrm_add_amount")
                            if v is not None:
                                try:
                                    return float(str(v).replace(",", "").replace(" ", ""))
                                except Exception:
                                    pass
                    return None

                net_income = _get_val(["당기순이익", "연결당기순이익"])
                equity     = _get_val(["자본총계", "지배기업주주지분", "자본합계"])
                assets     = _get_val(["자산총계"])

                if equity and equity > 0:
                    rows.append({
                        "year": year,
                        "equity": equity,
                        "net_income": net_income,
                        "assets": assets,
                        "roe": (net_income / equity) if net_income else None,
                    })

            except Exception:
                continue

        if not rows:
            return pd.DataFrame()

        result = pd.DataFrame(rows).set_index("year").sort_index()
        return result

    except Exception:
        return pd.DataFrame()


def _get_dart_key_ratios(symbol: str) -> pd.DataFrame:
    """
    DART 주요재무지표 API (fnlttSinglAcntAll 또는 fnlttMultiAcnt)
    BPS, EPS, PER, PBR, DIV, DPS 연도별 시계열
    """
    key = _get_dart_key()
    if not key:
        return pd.DataFrame()

    try:
        import opendartreader as odr
        odr.dart.api_key = key

        current_year = datetime.today().year
        rows = []

        for year in range(current_year - 10, current_year + 1):
            try:
                df = odr.dart.finstate_all(symbol, year, reprt_code="11011")
                if df is None or len(df) == 0:
                    continue

                def _pick(names):
                    for nm in names:
                        hit = df[df["account_nm"].str.contains(nm, na=False)]
                        if len(hit) > 0:
                            v = hit.iloc[0].get("thstrm_amount")
                            if v is not None:
                                try:
                                    return float(str(v).replace(",", "").replace(" ", ""))
                                except Exception:
                                    pass
                    return None

                bps = _pick(["주당순자산가치", "BPS", "주당장부가치"])
                eps = _pick(["주당순이익", "EPS", "기본주당순이익"])
                dps = _pick(["주당배당금", "DPS"])
                div = _pick(["배당수익률", "시가배당율"])

                if bps:
                    rows.append({
                        "year": year,
                        "BPS": bps,
                        "EPS": eps,
                        "DPS": dps,
                        "DIV": div,
                    })

            except Exception:
                continue

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows).set_index("year").sort_index()

    except Exception:
        return pd.DataFrame()


# ──────────────────────────────────────────────
# PBR 시계열
# ──────────────────────────────────────────────

def _get_price_monthly(symbol: str) -> pd.Series:
    """FDR에서 월별 주가 이력"""
    try:
        df = fdr.DataReader(symbol)
        if df is None or df.empty:
            return pd.Series(dtype=float)
        df.index = pd.to_datetime(df.index)
        return df["Close"].resample("ME").last().dropna()
    except Exception:
        return pd.Series(dtype=float)


def _build_pbr_from_dart_bps(symbol: str, price_monthly: pd.Series) -> tuple[pd.Series, str]:
    """
    DART 연도별 BPS + 월별 주가 → PBR 시계열
    BPS를 연말 기준으로 forward-fill
    """
    try:
        ratios = _get_dart_key_ratios(symbol)

        if ratios.empty or "BPS" not in ratios.columns:
            # finstate_all 실패 시 finstate로 직접 계산
            fin = _get_dart_financial_statements(symbol)
            if fin.empty or "equity" not in fin.columns:
                return pd.Series(dtype=float), "NONE"

            # 발행주식수 추정 (yfinance)
            try:
                info = yf.Ticker(_to_yf_symbol(symbol)).info or {}
                shares = float(
                    info.get("sharesOutstanding")
                    or info.get("impliedSharesOutstanding")
                    or 0
                )
            except Exception:
                shares = 0

            if shares <= 0:
                return pd.Series(dtype=float), "NONE"

            bps_annual = (fin["equity"] / shares).dropna()
        else:
            bps_annual = pd.to_numeric(ratios["BPS"], errors="coerce").dropna()

        if len(bps_annual) < 3:
            return pd.Series(dtype=float), "NONE"

        # 연말 날짜로 인덱스 설정
        bps_annual.index = pd.to_datetime(
            [f"{y}-12-31" for y in bps_annual.index]
        )
        bps_annual = bps_annual.sort_index()

        # 월말로 forward-fill
        bps_monthly = bps_annual.resample("ME").last().reindex(
            price_monthly.index, method="ffill"
        ).dropna()

        pbr = price_monthly.reindex(bps_monthly.index) / bps_monthly
        pbr = pbr.dropna()
        pbr = pbr[(pbr > 0) & (pbr < 50)]

        if len(pbr) >= 12:
            return pbr, "dart-bps"

    except Exception:
        pass

    return pd.Series(dtype=float), "NONE"


def build_pbr_statistics(symbol, price_df):
    """
    v6.0 — DART BPS primary, FDR/yfinance fallback
    """
    try:
        price_monthly = _get_price_monthly(symbol)

        if len(price_monthly) == 0:
            # price_df fallback
            price_monthly = price_df["Close"].resample("ME").last().dropna()

        pbr, source = pd.Series(dtype=float), "NONE"

        # 1차: DART BPS 기반
        pbr, source = _build_pbr_from_dart_bps(symbol, price_monthly)

        # 2차: FDR PBR 컬럼 직접
        if len(pbr) == 0:
            try:
                df = fdr.DataReader(symbol)
                if df is not None and not df.empty and "PBR" in df.columns:
                    df.index = pd.to_datetime(df.index)
                    pbr_daily = pd.to_numeric(df["PBR"], errors="coerce").dropna()
                    pbr_daily = pbr_daily[pbr_daily > 0]
                    if len(pbr_daily) >= 12:
                        pbr = pbr_daily.resample("ME").last().dropna()
                        source = "fdr-direct"
            except Exception:
                pass

        # 3차: yfinance equity 연도별 시계열 → BPS → PBR
        if len(pbr) == 0:
            try:
                info = yf.Ticker(_to_yf_symbol(symbol)).info or {}
                shares = float(
                    info.get("sharesOutstanding")
                    or info.get("impliedSharesOutstanding") or 0
                )

                if shares > 0:
                    ticker = yf.Ticker(_to_yf_symbol(symbol))
                    eq_series = {}
                    for bs in [ticker.balance_sheet, ticker.quarterly_balance_sheet]:
                        if bs is None or bs.empty:
                            continue
                        for rn in ["Stockholders Equity", "Common Stock Equity",
                                   "Total Equity Gross Minority Interest"]:
                            if rn in bs.index:
                                row = pd.to_numeric(bs.loc[rn], errors="coerce").dropna()
                                row.index = pd.to_datetime(row.index).tz_localize(None)
                                for dt, v in row.items():
                                    if pd.notna(v):
                                        eq_series[dt] = v
                                break

                    if len(eq_series) >= 2:
                        eq_s = pd.Series(eq_series).sort_index()
                        bps_s = eq_s / shares
                        # 단위 확인: BPS < 1000이면 달러 단위로 판단 → KRW 환산
                        if bps_s.mean() < 1000:
                            bps_s = bps_s * 1350
                        # 연말 날짜로 정규화 → 월별 forward-fill
                        bps_s.index = pd.to_datetime(
                            [f"{d.year}-12-31" for d in bps_s.index]
                        )
                        bps_s = bps_s.sort_index()
                        bps_monthly = bps_s.resample("ME").last().reindex(
                            price_monthly.index, method="ffill"
                        ).dropna()
                        if len(bps_monthly) >= 12:
                            pbr = price_monthly.reindex(bps_monthly.index) / bps_monthly
                            pbr = pbr.dropna()
                            pbr = pbr[(pbr > 0) & (pbr < 50)]
                            source = "yfinance-equity-series"

                    # 최후 수단: 최신 equity 1개로 역산
                    if len(pbr) == 0 and eq_series:
                        eq_latest = float(pd.Series(eq_series).sort_index().iloc[-1])
                        current_price = float(
                            info.get("currentPrice")
                            or info.get("regularMarketPrice") or 0
                        )
                        if eq_latest > 0 and current_price > 0:
                            current_bps = eq_latest / shares
                            if current_bps < 1000:
                                current_bps *= 1350
                            pbr = price_monthly / current_bps
                            pbr = pbr[(pbr > 0) & (pbr < 50)]
                            source = "yfinance-reverse"
            except Exception:
                pass

        if len(pbr) == 0:
            return {
                "available": False,
                "reason": "PBR 데이터 없음 (DART + FDR + yfinance 모두 실패)",
                "current_pbr": None, "mean_pbr": None, "std_pbr": None,
                "zscore": None, "sample_months": 0, "sample_grade": "N/A",
                "percentile": None, "source": "NONE",
            }

        pbr = pbr.resample("ME").last().dropna()

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


# ──────────────────────────────────────────────
# funda_snapshot
# ──────────────────────────────────────────────

def get_basic_fundamental_snapshot(symbol):
    """
    v6.0 — DART 주요재무지표 우선, yfinance 보완
    """
    result = {
        "BPS": None, "PER": None, "PBR": None,
        "EPS": None, "DIV": None, "DPS": None,
    }

    # 1차: DART 최신 연도 주요재무지표
    try:
        ratios = _get_dart_key_ratios(symbol)
        if not ratios.empty:
            last = ratios.iloc[-1]
            for col in ["BPS", "EPS", "DPS", "DIV"]:
                if col in last.index:
                    v = last[col]
                    if is_valid(v):
                        result[col] = round(float(v), 2 if col == "DIV" else 0)
    except Exception:
        pass

    # 2차: FDR 최신 행
    try:
        df = fdr.DataReader(symbol)
        if df is not None and not df.empty:
            last_row = df.iloc[-1]
            for col in ["BPS", "PER", "PBR", "EPS", "DIV"]:
                if result[col] is None and col in last_row.index:
                    v = pd.to_numeric(last_row[col], errors="coerce")
                    if pd.notna(v) and np.isfinite(v) and v != 0:
                        result[col] = round(float(v), 2)
    except Exception:
        pass

    # 3차: yfinance 보완
    try:
        info = yf.Ticker(_to_yf_symbol(symbol)).info or {}

        if result["DPS"] is None:
            dps = info.get("lastDividendValue")
            if dps is not None:
                result["DPS"] = round(float(dps), 0)

        if result["DIV"] is None:
            div = info.get("dividendYield")
            if div is not None:
                result["DIV"] = round(float(div), 2)

        # PBR/BPS (DART/FDR 모두 없을 때)
        if result["PBR"] is None or result["BPS"] is None:
            shares = float(
                info.get("sharesOutstanding")
                or info.get("impliedSharesOutstanding") or 0
            )
            current_price = float(
                info.get("currentPrice")
                or info.get("regularMarketPrice") or 0
            )
            ticker = yf.Ticker(_to_yf_symbol(symbol))
            for bs in [ticker.quarterly_balance_sheet, ticker.balance_sheet]:
                if bs is None or bs.empty:
                    continue
                for rn in ["Stockholders Equity", "Common Stock Equity"]:
                    if rn in bs.index:
                        eq = pd.to_numeric(bs.loc[rn], errors="coerce").dropna()
                        if len(eq) > 0 and shares > 0:
                            bps_calc = float(eq.iloc[0]) / shares
                            if bps_calc > 100:
                                if result["BPS"] is None:
                                    result["BPS"] = round(bps_calc, 0)
                                if result["PBR"] is None and current_price > 0:
                                    result["PBR"] = round(current_price / bps_calc, 2)
                        break
                break

        if result["PER"] is None:
            per = info.get("trailingPE") or info.get("forwardPE")
            if per:
                result["PER"] = round(float(per), 2)

    except Exception:
        pass

    return result
