import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pykrx import stock

try:
    import streamlit as st
except Exception:
    st = None

try:
    import OpenDartReader
except Exception:
    OpenDartReader = None


def is_valid(v):
    return v is not None and not pd.isna(v) and np.isfinite(v)


def get_dart_reader():
    api_key = None

    if st is not None:
        try:
            api_key = st.secrets.get("DART_API_KEY", None)
        except Exception:
            pass

    if not api_key:
        api_key = os.environ.get("DART_API_KEY")

    if api_key and OpenDartReader is not None:
        try:
            return OpenDartReader(api_key)
        except Exception:
            return None
    return None


def _normalize_text(v):
    if v is None:
        return ""
    return str(v).replace(" ", "").replace("\u3000", "").strip()


def _safe_float(v):
    try:
        if v is None or pd.isna(v):
            return np.nan
        if isinstance(v, str):
            v = v.replace(",", "").strip()
            if v == "":
                return np.nan
        return float(v)
    except Exception:
        return np.nan


def _build_monthly_shares_series(symbol):
    try:
        end = datetime.today()
        start = end - timedelta(days=365 * 10 + 30)

        df = stock.get_market_cap_by_date(
            start.strftime("%Y%m%d"),
            end.strftime("%Y%m%d"),
            symbol,
            freq="m",
        )

        if df is None or len(df) == 0:
            return pd.Series(dtype=float)

        shares_col = None
        for c in ["상장주식수", "상장주식 수", "ListedShares"]:
            if c in df.columns:
                shares_col = c
                break

        if shares_col is None:
            return pd.Series(dtype=float)

        s = pd.to_numeric(df[shares_col], errors="coerce").dropna()
        s.index = pd.to_datetime(df.index)
        s = s.sort_index()
        return s
    except Exception:
        return pd.Series(dtype=float)


def _extract_equity_from_finstate(fs: pd.DataFrame):
    if fs is None or len(fs) == 0:
        return np.nan

    temp = fs.copy()

    for c in ["account_nm", "fs_nm", "sj_nm", "thstrm_amount"]:
        if c not in temp.columns:
            temp[c] = ""

    temp["account_nm_norm"] = temp["account_nm"].apply(_normalize_text)
    temp["fs_nm_norm"] = temp["fs_nm"].apply(_normalize_text)

    # 연결재무 우선
    conn = temp[temp["fs_nm_norm"].str.contains("연결", na=False)].copy()
    sep = temp[~temp["fs_nm_norm"].str.contains("연결", na=False)].copy()

    equity_candidates = [
        "자본총계",
        "지배기업의소유주지분",
        "지배기업소유주지분",
        "지배기업의소유주에게귀속되는자본",
    ]

    def _pick(df):
        if len(df) == 0:
            return np.nan

        for nm in equity_candidates:
            hit = df[df["account_nm_norm"] == nm]
            if len(hit) > 0:
                vals = pd.to_numeric(hit["thstrm_amount"].astype(str).str.replace(",", ""), errors="coerce").dropna()
                if len(vals) > 0:
                    return float(vals.iloc[0])

        hit = df[df["account_nm_norm"].str.contains("자본총계", na=False)]
        if len(hit) > 0:
            vals = pd.to_numeric(hit["thstrm_amount"].astype(str).str.replace(",", ""), errors="coerce").dropna()
            if len(vals) > 0:
                return float(vals.iloc[0])

        return np.nan

    val = _pick(conn)
    if is_valid(val):
        return val

    return _pick(sep)


def _quarter_targets():
    now_year = datetime.today().year
    out = []
    for y in range(max(2010, now_year - 12), now_year + 1):
        out.extend([
            (y, "11013", pd.Timestamp(y, 3, 31)),   # Q1
            (y, "11012", pd.Timestamp(y, 6, 30)),   # H1
            (y, "11014", pd.Timestamp(y, 9, 30)),   # Q3
            (y, "11011", pd.Timestamp(y, 12, 31)),  # Y
        ])
    return out


def _build_quarterly_bps_from_dart(dart, symbol):
    if dart is None:
        return pd.DataFrame()

    shares_series = _build_monthly_shares_series(symbol)
    if len(shares_series) == 0:
        return pd.DataFrame()

    rows = []

    for year, reprt_code, q_end in _quarter_targets():
        try:
            fs = dart.finstate_all(symbol, year, reprt_code=reprt_code)
        except Exception:
            fs = pd.DataFrame()

        equity = _extract_equity_from_finstate(fs)
        if not is_valid(equity):
            continue

        eligible = shares_series[shares_series.index <= q_end]
        if len(eligible) == 0:
            continue

        shares = float(eligible.iloc[-1])
        if not is_valid(shares) or shares <= 0:
            continue

        bps = equity / shares

        if is_valid(bps) and bps > 0:
            rows.append(
                {
                    "quarter_end": q_end,
                    "equity": equity,
                    "shares": shares,
                    "bps": bps,
                    "source": "DART+KRX_SHARES",
                }
            )

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows).sort_values("quarter_end").drop_duplicates("quarter_end", keep="last")
    return out.reset_index(drop=True)


def _build_monthly_pbr_from_quarterly_bps(price_df, quarterly_bps_df):
    if price_df is None or len(price_df) == 0:
        return pd.DataFrame()
    if quarterly_bps_df is None or len(quarterly_bps_df) == 0:
        return pd.DataFrame()

    monthly_close = price_df["Close"].resample("ME").last().dropna()
    if len(monthly_close) == 0:
        return pd.DataFrame()

    q = quarterly_bps_df.copy()
    q["quarter_end"] = pd.to_datetime(q["quarter_end"])
    q = q.sort_values("quarter_end")

    rows = []
    for dt, close in monthly_close.items():
        eligible = q[q["quarter_end"] <= dt]
        if len(eligible) == 0:
            continue

        qrow = eligible.iloc[-1]
        bps = qrow["bps"]
        if not is_valid(bps) or bps <= 0:
            continue

        pbr = float(close) / float(bps)
        rows.append(
            {
                "date": dt,
                "close": float(close),
                "bps": float(bps),
                "pbr": pbr,
                "quarter_end_used": qrow["quarter_end"],
                "source": qrow.get("source", "N/A"),
            }
        )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def _calc_pbr_stats_from_series(pbr_series, source_name):
    pbr = pd.to_numeric(pbr_series, errors="coerce").dropna()
    pbr = pbr[pbr > 0]

    if len(pbr) < 36:
        return {
            "available": False,
            "reason": "데이터 부족(3년 미만)",
            "current_pbr": None,
            "mean_pbr": None,
            "std_pbr": None,
            "zscore": None,
            "sample_months": len(pbr),
            "sample_grade": "Abort",
            "percentile": None,
            "source": source_name,
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
            "source": source_name,
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
        "source": source_name,
    }


def build_pbr_statistics(symbol, price_df):
    """
    우선순위
    1) DART 분기 BPS + 상장주식수 fallback
    2) pykrx 월별 PBR
    """
    # 1) DART 시도
    try:
        dart = get_dart_reader()
        if dart is not None:
            quarterly_bps_df = _build_quarterly_bps_from_dart(dart, symbol)
            monthly_pbr_df = _build_monthly_pbr_from_quarterly_bps(price_df, quarterly_bps_df)

            if len(monthly_pbr_df) > 0 and "pbr" in monthly_pbr_df.columns:
                stats = _calc_pbr_stats_from_series(monthly_pbr_df["pbr"], "DART")
                stats["quarterly_bps_df"] = quarterly_bps_df
                stats["monthly_pbr_df"] = monthly_pbr_df
                return stats
    except Exception:
        pass

    # 2) pykrx fallback
    try:
        end = datetime.today()
        start = end - timedelta(days=365 * 10 + 30)

        funda = stock.get_market_fundamental_by_date(
            start.strftime("%Y%m%d"),
            end.strftime("%Y%m%d"),
            symbol,
            freq="m",
        )

        if funda is None or len(funda) == 0 or "PBR" not in funda.columns:
            return {
                "available": False,
                "reason": "월별 PBR 데이터 없음",
                "current_pbr": None,
                "mean_pbr": None,
                "std_pbr": None,
                "zscore": None,
                "sample_months": 0,
                "sample_grade": "N/A",
                "percentile": None,
                "source": "NONE",
            }

        stats = _calc_pbr_stats_from_series(funda["PBR"], "pykrx")
        stats["quarterly_bps_df"] = pd.DataFrame()
        stats["monthly_pbr_df"] = pd.DataFrame()
        return stats

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

        if symbol not in df.index:
            return {}

        row = df.loc[symbol]

        return {
            "BPS": row.get("BPS", None),
            "PER": row.get("PER", None),
            "PBR": row.get("PBR", None),
            "EPS": row.get("EPS", None),
            "DIV": row.get("DIV", None),
        }

    except Exception:
        return {}
