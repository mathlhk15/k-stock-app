import numpy as np
import pandas as pd
from pykrx import stock
from datetime import datetime


def is_valid(v):
    return v is not None and not pd.isna(v) and np.isfinite(v)


def percentile_rank(series: pd.Series, x: float) -> float:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0:
        return np.nan
    return float((s <= x).mean() * 100)


def _rename_fundamental_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame()

    temp = df.copy()
    rename_map = {
        "티커": "Symbol",
        "배당수익률": "DIV",
        "주당배당금": "DPS",
    }
    temp = temp.rename(columns=rename_map)
    return temp


def calculate_quality_score(symbol, market, listing_df):
    """
    v4.2
    - 동일 시장 + 동일 섹터 우선
    - 실패 시 시장 전체 fallback
    - 컬럼명 방어
    """
    try:
        today = datetime.today().strftime("%Y%m%d")
        df = stock.get_market_fundamental_by_ticker(today, market=market)

        if df is None or len(df) == 0:
            return {
                "available": False,
                "score": 0,
                "roe": None,
                "roe_percentile": None,
                "sector": None,
                "reason": "ROE 데이터 없음",
            }

        temp = _rename_fundamental_columns(df).reset_index()

        # 첫 컬럼이 티커일 가능성 방어
        if "Symbol" not in temp.columns:
            temp = temp.rename(columns={temp.columns[0]: "Symbol"})

        temp["Symbol"] = temp["Symbol"].astype(str)

        required_cols = ["BPS", "EPS"]
        for col in required_cols:
            if col not in temp.columns:
                return {
                    "available": False,
                    "score": 0,
                    "roe": None,
                    "roe_percentile": None,
                    "sector": None,
                    "reason": f"필수 컬럼 없음: {list(temp.columns)}",
                }

        temp["BPS"] = pd.to_numeric(temp["BPS"], errors="coerce")
        temp["EPS"] = pd.to_numeric(temp["EPS"], errors="coerce")
        temp["ROE"] = np.where(
            (temp["BPS"] > 0) & temp["EPS"].notna(),
            temp["EPS"] / temp["BPS"],
            np.nan,
        )

        listing = listing_df.copy()
        listing["Symbol"] = listing["Symbol"].astype(str)

        # FDR listing에는 Sector가 없을 수 있으므로 산업 대체 필드 준비
        sector_col = None
        for c in ["Sector", "Industry", "Dept", "Market"]:
            if c in listing.columns:
                sector_col = c
                break

        if sector_col is None:
            listing["SectorProxy"] = "N/A"
            sector_col = "SectorProxy"

        merged = temp.merge(listing[["Symbol", sector_col]], on="Symbol", how="left")
        merged = merged.rename(columns={sector_col: "SectorProxy"})

        row = merged[merged["Symbol"] == str(symbol)]
        if row.empty:
            return {
                "available": False,
                "score": 0,
                "roe": None,
                "roe_percentile": None,
                "sector": None,
                "reason": "종목 매칭 실패",
            }

        row = row.iloc[0]
        sector = row.get("SectorProxy", None)
        current_roe = row.get("ROE", np.nan)

        if not is_valid(current_roe):
            return {
                "available": False,
                "score": 0,
                "roe": None,
                "roe_percentile": None,
                "sector": sector,
                "reason": "ROE 계산 불가",
            }

        # 업종 peer 우선, 부족하면 시장 전체 fallback
        peer = merged.copy()
        if sector is not None and pd.notna(sector) and str(sector).strip() != "":
            peer_sector = peer[peer["SectorProxy"] == sector]
            peer_sector = peer_sector[pd.to_numeric(peer_sector["ROE"], errors="coerce").notna()]
            if len(peer_sector) >= 5:
                peer = peer_sector
            else:
                peer = merged[pd.to_numeric(merged["ROE"], errors="coerce").notna()]
        else:
            peer = merged[pd.to_numeric(merged["ROE"], errors="coerce").notna()]

        if len(peer) < 5:
            return {
                "available": False,
                "score": 0,
                "roe": None,
                "roe_percentile": None,
                "sector": sector,
                "reason": "ROE 비교 표본 부족",
            }

        pct = percentile_rank(peer["ROE"], float(current_roe))

        if pct >= 90:
            score = 30
        elif pct >= 70:
            score = 20
        else:
            score = 0

        return {
            "available": True,
            "score": score,
            "roe": float(current_roe),
            "roe_percentile": pct,
            "sector": sector,
            "reason": "",
        }

    except Exception as e:
        return {
            "available": False,
            "score": 0,
            "roe": None,
            "roe_percentile": None,
            "sector": None,
            "reason": f"Quality 계산 실패: {e}",
        }


def calculate_supply_score(investor_df):
    """
    v4.2
    - 컬럼 후보 확장
    - 데이터 부족 시 reason 표시
    """
    try:
        if investor_df is None or len(investor_df) < 30:
            return {
                "available": False,
                "score": 0,
                "supply_strength": None,
                "supply_percentile": None,
                "reason": "수급 데이터 부족",
            }

        flow = investor_df.copy()

        foreign_candidates = [
            "외국인합계", "외국인", "외국인계", "외국인투자자", "외국인투자자계"
        ]
        inst_candidates = [
            "기관합계", "기관", "기관계", "기관투자자", "기관투자자계"
        ]

        foreign_col = next((c for c in foreign_candidates if c in flow.columns), None)
        inst_col = next((c for c in inst_candidates if c in flow.columns), None)

        if foreign_col is None or inst_col is None:
            return {
                "available": False,
                "score": 0,
                "supply_strength": None,
                "supply_percentile": None,
                "reason": f"외국인/기관 컬럼 없음: {list(flow.columns)}",
            }

        flow["foreign"] = pd.to_numeric(flow[foreign_col], errors="coerce")
        flow["inst"] = pd.to_numeric(flow[inst_col], errors="coerce")
        flow["combined"] = flow["foreign"].fillna(0) + flow["inst"].fillna(0)

        flow["rolling20"] = flow["combined"].rolling(20).sum()
        dist = flow["rolling20"].dropna()

        if len(dist) < 30:
            return {
                "available": False,
                "score": 0,
                "supply_strength": None,
                "supply_percentile": None,
                "reason": "20일 수급 표본 부족",
            }

        current_strength = float(dist.iloc[-1])
        pct = percentile_rank(dist, current_strength)

        if pct >= 80:
            score = 20
        elif pct >= 50:
            score = 10
        else:
            score = 0

        return {
            "available": True,
            "score": score,
            "supply_strength": current_strength,
            "supply_percentile": pct,
            "reason": "",
        }

    except Exception as e:
        return {
            "available": False,
            "score": 0,
            "supply_strength": None,
            "supply_percentile": None,
            "reason": f"Supply 계산 실패: {e}",
        }


def calculate_scores(price_df, pbr_stats, quality_result, supply_result):
    score = 0
    reasons = []

    if pbr_stats.get("available"):
        z = pbr_stats.get("zscore")

        if z <= -1.5:
            score += 40
            reasons.append("Valuation +40")
        elif z <= -1.0:
            score += 30
            reasons.append("Valuation +30")
        elif z <= -0.5:
            score += 20
            reasons.append("Valuation +20")
        elif z >= 1.5:
            score -= 40
            reasons.append("Valuation -40")
        elif z >= 1.0:
            score -= 20
            reasons.append("Valuation -20")

    if quality_result.get("available"):
        qscore = quality_result.get("score", 0)
        score += qscore
        reasons.append(f"Quality +{qscore}")

    if supply_result.get("available"):
        sscore = supply_result.get("score", 0)
        score += sscore
        reasons.append(f"Supply +{sscore}")

    ma20 = price_df["MA20"].iloc[-1]
    ma60 = price_df["MA60"].iloc[-1]
    ma120 = price_df["MA120"].iloc[-1]

    if is_valid(ma20) and is_valid(ma60) and is_valid(ma120):
        if ma20 > ma60 > ma120:
            score += 5
            reasons.append("정배열 +5")

    rsi = price_df["RSI"].iloc[-1]
    if is_valid(rsi) and rsi >= 50:
        score += 5
        reasons.append("RSI>=50 +5")

    if score >= 80:
        grade = "Strong Buy"
    elif score >= 65:
        grade = "Buy"
    elif score >= 50:
        grade = "Hold"
    elif score >= 35:
        grade = "Caution"
    else:
        grade = "Avoid"

    if not pbr_stats.get("available") and grade in ["Strong Buy", "Buy"]:
        grade = "Hold"

    if pbr_stats.get("sample_grade") == "Limited" and grade == "Strong Buy":
        grade = "Buy"

    return {
        "score": score,
        "grade": grade,
        "reasons": reasons,
    }


# 아래 build_analysis_payload는 기존 그대로 사용
def build_analysis_payload(
    symbol,
    name,
    market,
    price_df,
    investor_df,
    pbr_stats,
    funda_snapshot,
    quality_result,
    supply_result,
    score_result,
):
    last = price_df.iloc[-1]
    prev = price_df.iloc[-2] if len(price_df) >= 2 else last

    current_price = float(last["Close"])
    prev_price = float(prev["Close"])
    pct_change = ((current_price - prev_price) / prev_price * 100) if prev_price != 0 else 0

    ma20 = last["MA20"]
    ma60 = last["MA60"]
    ma120 = last["MA120"]
    rsi = last["RSI"]
    macd = last["MACD"]
    macd_signal = last["MACD_SIGNAL"]
    vol20 = last["VOL20"]
    volume = last["Volume"]
    atr = last["ATR"]

    mdd = float(price_df["DRAWDOWN"].min() * 100) if "DRAWDOWN" in price_df.columns else None

    high_52 = float(price_df["High"].tail(252).max()) if len(price_df) >= 20 else float(price_df["High"].max())
    low_52 = float(price_df["Low"].tail(252).min()) if len(price_df) >= 20 else float(price_df["Low"].min())

    atr_val = atr if is_valid(atr) and atr > 0 else current_price * 0.03
    ma20_val = ma20 if is_valid(ma20) else current_price * 0.97
    ma60_val = ma60 if is_valid(ma60) else current_price * 0.92

    support_1 = min(ma20_val, current_price - atr_val)
    support_2 = min(ma60_val, current_price - 2 * atr_val)
    resistance_1 = current_price + atr_val
    resistance_2 = current_price + 2 * atr_val

    zone1_low = max(ma20_val, current_price - 1.5 * atr_val)
    zone1_high = current_price
    zone2_low = max(ma60_val, current_price - 3 * atr_val)
    zone2_high = zone1_low

    vol_ratio = None
    if is_valid(vol20) and vol20 > 0:
        vol_ratio = float(volume / vol20)

    if vol_ratio is None:
        volume_comment = "거래량 데이터가 충분하지 않아 강도 판단은 제한됩니다."
    elif vol_ratio >= 1.5:
        volume_comment = "최근 거래량이 20일 평균을 뚜렷하게 상회해 수급 반응이 강한 편입니다."
    elif vol_ratio >= 1.0:
        volume_comment = "거래량이 최근 평균 수준 이상으로 유지되고 있습니다."
    else:
        volume_comment = "거래량이 20일 평균보다 낮아 움직임의 신뢰도는 다소 약할 수 있습니다."

    if is_valid(macd) and is_valid(macd_signal):
        if macd > macd_signal:
            macd_comment = "MACD가 시그널선 위에 있어 단기 모멘텀이 상대적으로 우위입니다."
        else:
            macd_comment = "MACD가 시그널선 아래에 있어 단기 모멘텀은 아직 약한 편입니다."
    else:
        macd_comment = "MACD 해석을 위한 데이터가 충분하지 않습니다."

    if is_valid(rsi) and rsi < 35:
        short_strategy = "단기적으로는 과매도 인근 구간이라 기술적 반등 시도를 관찰할 수 있으나, 추격 매수보다 지지 확인이 우선입니다."
    else:
        short_strategy = "단기적으로는 현재가 추격보다 1차 지지 구간에서 눌림목 형성 여부를 확인하는 접근이 더 보수적입니다."

    if is_valid(ma120) and current_price > ma120:
        mid_strategy = "중기적으로는 장기 추세선 위에 있어 조정 시 분할 관찰 전략이 유효할 수 있습니다."
    else:
        mid_strategy = "중기적으로는 장기 추세선 회복 여부를 먼저 확인하는 접근이 적절합니다."

    if pbr_stats.get("available") and pbr_stats.get("zscore") is not None and pbr_stats["zscore"] <= -1.0:
        bull_scenario = "현재 PBR이 역사 평균 대비 낮은 구간에 있어, 기술적 반등과 함께 재평가 시도가 나올 가능성을 열어둘 수 있습니다."
    else:
        bull_scenario = "추세가 개선되고 거래량이 동반되면 단기 저항선 테스트 이후 추가 상승 시도를 기대할 수 있습니다."

    bear_scenario = "지지선 이탈 시에는 단기 조정 폭이 확대될 수 있으며, 장기선 회복 전까지는 보수적 접근이 필요합니다."

    flags = []
    z = pbr_stats.get("zscore")
    roe_pct = quality_result.get("roe_percentile")

    if is_valid(z) and is_valid(roe_pct):
        if z <= -1.5 and roe_pct >= 80:
            flags.append("★STRONG VALUE-UP★")
        elif z <= -1.0 and roe_pct >= 70:
            flags.append("★VALUE-UP★")

    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "current_price": current_price,
        "pct_change": pct_change,
        "score": score_result["score"],
        "grade": score_result["grade"],
        "score_reasons": score_result["reasons"],
        "pbr_stats": pbr_stats,
        "funda_snapshot": funda_snapshot,
        "quality_result": quality_result,
        "supply_result": supply_result,
        "flags": flags,
        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,
        "rsi": rsi,
        "macd": macd,
        "macd_signal": macd_signal,
        "mdd": mdd,
        "vol_ratio": vol_ratio,
        "volume_comment": volume_comment,
        "macd_comment": macd_comment,
        "support_1": support_1,
        "support_2": support_2,
        "resistance_1": resistance_1,
        "resistance_2": resistance_2,
        "high_52": high_52,
        "low_52": low_52,
        "zone1_low": zone1_low,
        "zone1_high": zone1_high,
        "zone2_low": zone2_low,
        "zone2_high": zone2_high,
        "short_strategy": short_strategy,
        "mid_strategy": mid_strategy,
        "bull_scenario": bull_scenario,
        "bear_scenario": bear_scenario,
    }
