"""
kr_scoring.py  v7.1
- Quality: DART ROE primary, yfinance fallback
- 모멘텀 / 리스크 / 주주환원 지표 추가
- v7.1: Python 3.9 호환 (str | None → Optional[str] 등)
"""
from __future__ import annotations
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
import streamlit as st
from datetime import datetime, timedelta


def is_valid(v):
    return v is not None and not pd.isna(v) and np.isfinite(v)


def percentile_rank(series: pd.Series, x: float) -> float:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0:
        return np.nan
    return float((s <= x).mean() * 100)


def _to_yf_symbol(symbol: str) -> str:
    return f"{symbol}.KS"


def _get_dart_key() -> Optional[str]:
    try:
        return st.secrets["DART_API_KEY"]
    except Exception:
        return None


def _get_roe_from_dart(symbol: str) -> Optional[float]:
    try:
        key = _get_dart_key()
        if not key:
            return None
        import opendartreader as odr
        odr.dart.api_key = key
        year = datetime.today().year - 1

        df = odr.dart.finstate_all(symbol, year, reprt_code="11011")
        if df is None or len(df) == 0:
            return None

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

        net_income = _pick(["당기순이익"])
        equity = _pick(["자본총계", "자본합계"])
        if net_income and equity and equity > 0:
            return net_income / equity
    except Exception:
        pass
    return None


def _get_roe_from_yf(symbol: str) -> Optional[float]:
    try:
        info = yf.Ticker(_to_yf_symbol(symbol)).info or {}
        roe = info.get("returnOnEquity")
        if roe is not None and np.isfinite(float(roe)):
            return float(roe)
    except Exception:
        pass
    return None


def _build_market_roe_table(listing_df: pd.DataFrame, market: str) -> pd.DataFrame:
    try:
        subset = listing_df.copy()
        subset["Symbol"] = subset["Symbol"].astype(str)
        if "Market" in subset.columns:
            subset = subset[subset["Market"].str.upper() == market.upper()]
        if "Marcap" in subset.columns:
            subset = subset.sort_values("Marcap", ascending=False).head(100)
        else:
            subset = subset.head(100)

        results = []
        for sym in subset["Symbol"].tolist():
            try:
                info = yf.Ticker(f"{sym}.KS").info or {}
                roe = info.get("returnOnEquity")
                sector = info.get("sector") or info.get("industry") or "N/A"
                if roe is not None:
                    results.append({"Symbol": sym, "ROE": float(roe), "Sector": sector})
            except Exception:
                continue

        if not results:
            return pd.DataFrame(columns=["Symbol", "ROE", "Sector"])
        return pd.DataFrame(results)
    except Exception:
        return pd.DataFrame(columns=["Symbol", "ROE", "Sector"])


def calculate_quality_score(symbol, market, listing_df):
    try:
        current_roe = _get_roe_from_dart(symbol)
        roe_source = "dart"
        if current_roe is None:
            current_roe = _get_roe_from_yf(symbol)
            roe_source = "yfinance"

        if current_roe is None:
            return {
                "available": False, "score": 0,
                "roe": None, "roe_percentile": None,
                "sector": None, "reason": "ROE 데이터 없음",
            }

        try:
            info = yf.Ticker(_to_yf_symbol(symbol)).info or {}
            sector = info.get("sector") or info.get("industry") or "N/A"
        except Exception:
            sector = "N/A"

        market_table = _build_market_roe_table(listing_df, market)

        if len(market_table) < 5:
            if current_roe >= 0.15:
                score = 20
            elif current_roe >= 0.08:
                score = 10
            else:
                score = 0
            return {
                "available": True, "score": score,
                "roe": current_roe, "roe_percentile": None,
                "sector": sector, "reason": f"절대값 기준 ({roe_source})",
            }

        peer = market_table.copy()
        if sector != "N/A":
            peer_sector = peer[peer["Sector"] == sector]
            if len(peer_sector) >= 5:
                peer = peer_sector

        pct = percentile_rank(peer["ROE"], current_roe)

        if pct >= 90:
            score = 30
        elif pct >= 70:
            score = 20
        elif pct >= 60:
            score = 10
        else:
            score = 0

        return {
            "available": True, "score": score,
            "roe": current_roe, "roe_percentile": float(pct),
            "sector": sector, "reason": f"source: {roe_source}",
        }

    except Exception as e:
        return {
            "available": False, "score": 0,
            "roe": None, "roe_percentile": None,
            "sector": None, "reason": f"Quality 계산 실패: {e}",
        }


# ── 모멘텀 계산 ──────────────────────────────
def calculate_momentum_result(price_df: pd.DataFrame) -> dict:
    try:
        close = price_df["Close"]
        current = float(close.iloc[-1])

        def ret(days):
            if len(close) > days:
                return (current / float(close.iloc[-days]) - 1) * 100
            return None

        r1m  = ret(21)
        r3m  = ret(63)
        r6m  = ret(126)
        r12m = ret(252)

        # 200MA 괴리
        ma200 = close.rolling(200).mean().iloc[-1]
        ma200_gap = ((current / float(ma200)) - 1) * 100 if is_valid(ma200) else None

        # 52주 고가 대비 위치
        high52 = float(price_df["High"].tail(252).max())
        low52  = float(price_df["Low"].tail(252).min())
        from_high = ((current / high52) - 1) * 100 if high52 > 0 else None
        from_low  = ((current / low52)  - 1) * 100 if low52  > 0 else None

        # 모멘텀 점수 (6M 수익률 기준)
        score = 0
        if r6m is not None:
            if r6m >= 20:
                score = 10
            elif r6m >= 5:
                score = 5
            elif r6m <= -20:
                score = -10
            elif r6m <= -5:
                score = -5

        return {
            "available": True,
            "r1m": r1m, "r3m": r3m, "r6m": r6m, "r12m": r12m,
            "ma200_gap": ma200_gap,
            "high_52": high52, "low_52": low52,
            "from_high": from_high, "from_low": from_low,
            "score": score,
        }
    except Exception as e:
        return {"available": False, "score": 0, "reason": str(e)}


# ── 리스크 계산 ──────────────────────────────
def calculate_risk_result(symbol: str, price_df: pd.DataFrame) -> dict:
    try:
        close = price_df["Close"]
        daily_ret = close.pct_change().dropna()

        # 연간 변동성
        vol_1y = float(daily_ret.tail(252).std() * np.sqrt(252) * 100) if len(daily_ret) >= 60 else None

        # Beta (코스피 대비)
        beta = None
        try:
            mkt = fdr.DataReader("KS11")["Close"].pct_change().dropna()
            merged = pd.concat([daily_ret.rename("stock"), mkt.rename("mkt")], axis=1).dropna().tail(252)
            if len(merged) >= 60:
                cov = np.cov(merged["stock"], merged["mkt"])
                beta = float(cov[0, 1] / cov[1, 1])
        except Exception:
            pass

        # Sharpe (무위험 이자율 3.5% 가정)
        sharpe = None
        if vol_1y is not None and vol_1y > 0:
            ann_ret = float(daily_ret.tail(252).mean() * 252 * 100)
            sharpe = round((ann_ret - 3.5) / vol_1y, 2)

        # 리스크 점수
        score = 0
        if beta is not None:
            if beta > 1.5:
                score -= 5
            elif beta < 0.8:
                score += 3

        return {
            "available": True,
            "vol_1y": vol_1y,
            "beta": beta,
            "sharpe": sharpe,
            "score": score,
        }
    except Exception as e:
        return {"available": False, "score": 0, "reason": str(e)}


# ── 주주환원 계산 ─────────────────────────────
def calculate_shareholder_result(symbol: str, funda_snapshot: dict) -> dict:
    try:
        div_yield = funda_snapshot.get("DIV")
        dps       = funda_snapshot.get("DPS")
        per       = funda_snapshot.get("PER")
        eps       = funda_snapshot.get("EPS")
        bps       = funda_snapshot.get("BPS")

        # PEG = PER / EPS 성장률 (yfinance earningsGrowth 활용)
        peg = None
        eps_growth = None
        try:
            info = yf.Ticker(_to_yf_symbol(symbol)).info or {}
            eg = info.get("earningsGrowth") or info.get("earningsQuarterlyGrowth")
            if eg is not None and eg > 0 and per is not None and per > 0:
                eps_growth = float(eg) * 100
                peg = round(per / eps_growth, 2)
        except Exception:
            pass

        # 주주환원 점수
        score = 0
        if div_yield is not None:
            if div_yield >= 3.0:
                score += 5
            elif div_yield >= 1.5:
                score += 3

        return {
            "available": True,
            "div_yield": div_yield,
            "dps": dps,
            "per": per,
            "eps": eps,
            "bps": bps,
            "peg": peg,
            "eps_growth": eps_growth,
            "score": score,
        }
    except Exception as e:
        return {"available": False, "score": 0, "reason": str(e)}


# ── 종합 점수 ─────────────────────────────────
def calculate_scores(price_df, pbr_stats, quality_result,
                     momentum_result=None, risk_result=None, shareholder_result=None):
    score = 0
    reasons = []

    # 모멘텀 강도 사전 계산 (Valuation 감점 완화에 사용)
    mo_strong = False
    if momentum_result and momentum_result.get("available"):
        r6m = momentum_result.get("r6m")
        r12m = momentum_result.get("r12m")
        if (r6m is not None and r6m >= 30) or (r12m is not None and r12m >= 30):
            mo_strong = True

    # Valuation (모멘텀 강할 때 고평가 감점 반감)
    if pbr_stats.get("available"):
        z = pbr_stats.get("zscore")
        if z <= -1.5:
            score += 40; reasons.append("Valuation +40")
        elif z <= -1.0:
            score += 30; reasons.append("Valuation +30")
        elif z <= -0.5:
            score += 20; reasons.append("Valuation +20")
        elif z >= 1.5:
            if mo_strong:
                score -= 20; reasons.append("Valuation -20 (모멘텀 반감)")
            else:
                score -= 40; reasons.append("Valuation -40")
        elif z >= 1.0:
            if mo_strong:
                score -= 10; reasons.append("Valuation -10 (모멘텀 반감)")
            else:
                score -= 20; reasons.append("Valuation -20")

    # Quality
    if quality_result.get("available"):
        qs = quality_result.get("score", 0)
        score += qs; reasons.append(f"Quality +{qs}")

    # Momentum
    if momentum_result and momentum_result.get("available"):
        ms = momentum_result.get("score", 0)
        if ms != 0:
            score += ms
            reasons.append(f"Momentum {'+' if ms > 0 else ''}{ms}")

    # Risk
    if risk_result and risk_result.get("available"):
        rs = risk_result.get("score", 0)
        if rs != 0:
            score += rs
            reasons.append(f"Risk {'+' if rs > 0 else ''}{rs}")

    # 주주환원 + PEG 점수
    if shareholder_result and shareholder_result.get("available"):
        ss = shareholder_result.get("score", 0)
        if ss != 0:
            score += ss
            reasons.append(f"배당 +{ss}")
        # PEG 가산점: PEG < 1이면 성장 대비 저평가
        peg = shareholder_result.get("peg")
        if peg is not None:
            if peg < 0.5:
                score += 15; reasons.append("PEG<0.5 +15")
            elif peg < 1.0:
                score += 10; reasons.append("PEG<1.0 +10")
            elif peg < 1.5:
                score += 5;  reasons.append("PEG<1.5 +5")

    # 기술적
    ma20  = price_df["MA20"].iloc[-1]
    ma60  = price_df["MA60"].iloc[-1]
    ma120 = price_df["MA120"].iloc[-1]
    if is_valid(ma20) and is_valid(ma60) and is_valid(ma120):
        if ma20 > ma60 > ma120:
            score += 5; reasons.append("정배열 +5")

    rsi = price_df["RSI"].iloc[-1]
    if is_valid(rsi) and rsi >= 50:
        score += 5; reasons.append("RSI>=50 +5")

    # ── 등급 판정 ──────────────────────────────
    # 성장주 판별: 모멘텀 강 + ROE 우량 + PEG < 1
    peg_val  = (shareholder_result or {}).get("peg")
    roe_pct  = quality_result.get("roe_percentile")
    is_growth = (
        mo_strong
        and is_valid(roe_pct) and roe_pct >= 70
        and peg_val is not None and peg_val < 1.0
    )

    if score >= 80:   grade = "Strong Buy"
    elif score >= 65: grade = "Buy"
    elif score >= 50:
        grade = "Growth" if is_growth else "Hold"
    elif score >= 35:
        grade = "Growth" if is_growth else "Caution"
    elif score >= 20:
        grade = "Growth" if is_growth else "Avoid"
    else:
        grade = "Avoid"

    if not pbr_stats.get("available") and grade in ["Strong Buy", "Buy"]:
        grade = "Hold"
    if pbr_stats.get("sample_grade") == "Limited" and grade == "Strong Buy":
        grade = "Buy"

    return {"score": score, "grade": grade, "reasons": reasons, "is_growth": is_growth}


# ── 애널리스트 목표가 ──────────────────────────
def get_analyst_data(symbol: str) -> dict:
    try:
        t = yf.Ticker(f"{symbol}.KS")
        info = t.info or {}
        result = {
            "target_high":   info.get("targetHighPrice"),
            "target_low":    info.get("targetLowPrice"),
            "target_mean":   info.get("targetMeanPrice"),
            "rec_key":       info.get("recommendationKey", ""),
            "num_analysts":  info.get("numberOfAnalystOpinions"),
            "strong_buy": 0, "buy": 0, "hold": 0,
            "sell": 0, "strong_sell": 0,
        }
        try:
            rec_df = t.recommendations_summary
            if rec_df is not None and not rec_df.empty:
                latest = rec_df.iloc[0]
                result["strong_buy"]  = int(latest.get("strongBuy",  0) or 0)
                result["buy"]         = int(latest.get("buy",         0) or 0)
                result["hold"]        = int(latest.get("hold",        0) or 0)
                result["sell"]        = int(latest.get("sell",        0) or 0)
                result["strong_sell"] = int(latest.get("strongSell",  0) or 0)
        except Exception:
            pass
        return result
    except Exception:
        return {}


# ── 실적 서프라이즈 ───────────────────────────
def get_earnings_surprise(symbol: str) -> list:
    try:
        t = yf.Ticker(f"{symbol}.KS")
        hist = t.earnings_history
        if hist is None or (hasattr(hist, "empty") and hist.empty):
            return []
        df = hist if isinstance(hist, pd.DataFrame) else pd.DataFrame(hist)
        df = df.sort_index(ascending=False).head(4)
        rows = []
        for idx, row in df.iterrows():
            eps_est    = row.get("epsEstimate")    or row.get("EPS Estimate")
            eps_actual = row.get("epsActual")      or row.get("Reported EPS")
            surprise   = row.get("epsDifference")  or row.get("Surprise(%)")
            date_str   = str(idx)[:10] if idx else "N/A"
            rows.append({
                "date":       date_str,
                "eps_est":    float(eps_est)    if eps_est    is not None and np.isfinite(float(eps_est))    else None,
                "eps_actual": float(eps_actual) if eps_actual is not None and np.isfinite(float(eps_actual)) else None,
                "surprise":   float(surprise)   if surprise   is not None and np.isfinite(float(surprise))   else None,
            })
        return [r for r in rows if r["eps_actual"] is not None or r["eps_est"] is not None]
    except Exception:
        return []


# ── 섹터 동종업종 대비 성과 ───────────────────
def get_sector_relative(symbol: str, market: str, listing_df: pd.DataFrame) -> dict:
    """
    같은 시장(KOSPI/KOSDAQ) + 같은 섹터 내 시가총액 상위 5개 종목과 수익률 비교
    """
    try:
        # 현재 종목 섹터
        info = yf.Ticker(f"{symbol}.KS").info or {}
        sector = info.get("sector") or info.get("industry") or "N/A"
        if sector == "N/A":
            return {"available": False, "reason": "섹터 정보 없음"}

        # 같은 시장 상위 종목 필터
        sub = listing_df.copy()
        if "Market" in sub.columns:
            sub = sub[sub["Market"].str.upper() == market.upper()]
        if "Marcap" in sub.columns:
            sub = sub.sort_values("Marcap", ascending=False).head(50)

        peers = []
        for sym in sub["Symbol"].astype(str).tolist():
            if sym == symbol:
                continue
            try:
                _info = yf.Ticker(f"{sym}.KS").info or {}
                _sec  = _info.get("sector") or _info.get("industry") or ""
                if _sec == sector:
                    peers.append(sym)
                if len(peers) >= 5:
                    break
            except Exception:
                continue

        if not peers:
            return {"available": False, "reason": "동종업종 비교 종목 없음"}

        import FinanceDataReader as _fdr

        def _ret(sym_, days):
            try:
                df_ = _fdr.DataReader(sym_)["Close"].dropna()
                if len(df_) > days:
                    return (float(df_.iloc[-1]) / float(df_.iloc[-days]) - 1) * 100
            except Exception:
                pass
            return None

        stock_r = {d: _ret(symbol, d) for d in [21, 63, 126]}

        peer_rets = {}
        for d in [21, 63, 126]:
            vals = [_ret(p, d) for p in peers]
            vals = [v for v in vals if v is not None]
            peer_rets[d] = sum(vals) / len(vals) if vals else None

        return {
            "available": True,
            "sector": sector,
            "peer_count": len(peers),
            "stock_1m":  stock_r[21],  "peer_1m":  peer_rets[21],
            "stock_3m":  stock_r[63],  "peer_3m":  peer_rets[63],
            "stock_6m":  stock_r[126], "peer_6m":  peer_rets[126],
            "rel_1m": (stock_r[21]  - peer_rets[21])  if stock_r[21]  is not None and peer_rets[21]  is not None else None,
            "rel_3m": (stock_r[63]  - peer_rets[63])  if stock_r[63]  is not None and peer_rets[63]  is not None else None,
            "rel_6m": (stock_r[126] - peer_rets[126]) if stock_r[126] is not None and peer_rets[126] is not None else None,
        }
    except Exception as e:
        return {"available": False, "reason": str(e)}


def build_analysis_payload(
    symbol, name, market, price_df,
    pbr_stats, funda_snapshot, quality_result, score_result,
    momentum_result=None, risk_result=None, shareholder_result=None,
):
    last = price_df.iloc[-1]
    prev = price_df.iloc[-2] if len(price_df) >= 2 else last

    current_price = float(last["Close"])
    prev_price    = float(prev["Close"])
    pct_change    = ((current_price - prev_price) / prev_price * 100) if prev_price != 0 else 0

    ma20  = last["MA20"]
    ma60  = last["MA60"]
    ma120 = last["MA120"]
    rsi   = last["RSI"]
    macd  = last["MACD"]
    macd_signal = last["MACD_SIGNAL"]
    vol20  = last["VOL20"]
    volume = last["Volume"]
    atr    = last["ATR"]

    mdd     = float(price_df["DRAWDOWN"].min() * 100) if "DRAWDOWN" in price_df.columns else None
    high_52 = float(price_df["High"].tail(252).max()) if len(price_df) >= 20 else float(price_df["High"].max())
    low_52  = float(price_df["Low"].tail(252).min())  if len(price_df) >= 20 else float(price_df["Low"].min())

    atr_val  = atr  if is_valid(atr)  and atr  > 0 else current_price * 0.03
    ma20_val = ma20 if is_valid(ma20) else current_price * 0.97
    ma60_val = ma60 if is_valid(ma60) else current_price * 0.92

    support_1    = min(ma20_val, current_price - atr_val)
    support_2    = min(ma60_val, current_price - 2 * atr_val)
    resistance_1 = current_price + atr_val
    resistance_2 = current_price + 2 * atr_val

    zone1_low  = max(ma20_val, current_price - 1.5 * atr_val)
    zone1_high = current_price
    zone2_low  = max(ma60_val, current_price - 3 * atr_val)
    zone2_high = zone1_low

    vol_ratio = float(volume / vol20) if is_valid(vol20) and vol20 > 0 else None

    if vol_ratio is None:
        volume_comment = "거래량 데이터가 충분하지 않아 강도 판단은 제한됩니다."
    elif vol_ratio >= 1.5:
        volume_comment = "최근 거래량이 20일 평균을 뚜렷하게 상회해 수급 반응이 강한 편입니다."
    elif vol_ratio >= 1.0:
        volume_comment = "거래량이 최근 평균 수준 이상으로 유지되고 있습니다."
    else:
        volume_comment = "거래량이 20일 평균보다 낮아 움직임의 신뢰도는 다소 약할 수 있습니다."

    if is_valid(macd) and is_valid(macd_signal):
        macd_comment = (
            "MACD가 시그널선 위에 있어 단기 모멘텀이 상대적으로 우위입니다."
            if macd > macd_signal
            else "MACD가 시그널선 아래에 있어 단기 모멘텀은 아직 약한 편입니다."
        )
    else:
        macd_comment = "MACD 해석을 위한 데이터가 충분하지 않습니다."

    short_strategy = (
        "단기적으로는 과매도 인근 구간이라 기술적 반등 시도를 관찰할 수 있으나, 추격 매수보다 지지 확인이 우선입니다."
        if is_valid(rsi) and rsi < 35
        else "단기적으로는 현재가 추격보다 1차 지지 구간에서 눌림목 형성 여부를 확인하는 접근이 더 보수적입니다."
    )

    mid_strategy = (
        "중기적으로는 장기 추세선 위에 있어 조정 시 분할 관찰 전략이 유효할 수 있습니다."
        if is_valid(ma120) and current_price > ma120
        else "중기적으로는 장기 추세선 회복 여부를 먼저 확인하는 접근이 적절합니다."
    )

    bull_scenario = (
        "현재 PBR이 역사 평균 대비 낮은 구간에 있어, 기술적 반등과 함께 재평가 시도가 나올 가능성을 열어둘 수 있습니다."
        if pbr_stats.get("available") and pbr_stats.get("zscore") is not None and pbr_stats["zscore"] <= -1.0
        else "추세가 개선되고 거래량이 동반되면 단기 저항선 테스트 이후 추가 상승 시도를 기대할 수 있습니다."
    )
    bear_scenario = "지지선 이탈 시에는 단기 조정 폭이 확대될 수 있으며, 장기선 회복 전까지는 보수적 접근이 필요합니다."

    flags = []
    z = pbr_stats.get("zscore")
    roe_pct = quality_result.get("roe_percentile")
    if is_valid(z) and is_valid(roe_pct):
        if z <= -1.5 and roe_pct >= 80:
            flags.append("★STRONG VALUE-UP★")
        elif z <= -1.0 and roe_pct >= 70:
            flags.append("★VALUE-UP★")

    # 볼린저밴드 최신값 추출
    bb_pct   = float(price_df["BB_PCT"].iloc[-1])   if "BB_PCT"   in price_df.columns else None
    bb_upper = float(price_df["BB_UPPER"].iloc[-1]) if "BB_UPPER" in price_df.columns else None
    bb_lower = float(price_df["BB_LOWER"].iloc[-1]) if "BB_LOWER" in price_df.columns else None
    bb_mid   = float(price_df["BB_MID"].iloc[-1])   if "BB_MID"   in price_df.columns else None
    bb_width = float(price_df["BB_WIDTH"].iloc[-1]) if "BB_WIDTH" in price_df.columns else None

    return {
        "symbol": symbol, "name": name, "market": market,
        "current_price": current_price, "pct_change": pct_change,
        "bb_pct": bb_pct, "bb_upper": bb_upper, "bb_lower": bb_lower,
        "bb_mid": bb_mid, "bb_width": bb_width,
        "score": score_result["score"], "grade": score_result["grade"],
        "score_reasons": score_result["reasons"],
        "pbr_stats": pbr_stats, "funda_snapshot": funda_snapshot,
        "quality_result": quality_result,
        "momentum_result": momentum_result or {},
        "risk_result": risk_result or {},
        "shareholder_result": shareholder_result or {},
        "flags": flags,
        "ma20": ma20, "ma60": ma60, "ma120": ma120,
        "rsi": rsi, "macd": macd, "macd_signal": macd_signal,
        "mdd": mdd, "vol_ratio": vol_ratio,
        "volume_comment": volume_comment, "macd_comment": macd_comment,
        "support_1": support_1, "support_2": support_2,
        "resistance_1": resistance_1, "resistance_2": resistance_2,
        "high_52": high_52, "low_52": low_52,
        "zone1_low": zone1_low, "zone1_high": zone1_high,
        "zone2_low": zone2_low, "zone2_high": zone2_high,
        "short_strategy": short_strategy, "mid_strategy": mid_strategy,
        "bull_scenario": bull_scenario, "bear_scenario": bear_scenario,
    }
