import FinanceDataReader as fdr
import pandas as pd
import streamlit as st


@st.cache_data(ttl=3600)
def load_krx_listing() -> pd.DataFrame:
    """
    KRX 상장 종목 목록 로드.
    FDR 실패 시 pykrx → 직접 KRX API 순으로 fallback.
    """
    # 1차: FinanceDataReader
    try:
        df = fdr.StockListing("KRX")
        if df is not None and not df.empty:
            if "Code" in df.columns and "Symbol" not in df.columns:
                df = df.rename(columns={"Code": "Symbol"})
            return df
    except Exception:
        pass

    # 2차: pykrx
    try:
        from pykrx import stock as pkstock
        from datetime import datetime
        today = datetime.today().strftime("%Y%m%d")
        rows = []
        for market in ["KOSPI", "KOSDAQ"]:
            tickers = pkstock.get_market_ticker_list(today, market=market)
            for t in tickers:
                name = pkstock.get_market_ticker_name(t)
                rows.append({"Symbol": t, "Name": name, "Market": market})
        if rows:
            return pd.DataFrame(rows)
    except Exception:
        pass

    # 3차: KRX 공식 API 직접 호출
    try:
        import requests
        url = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://data.krx.co.kr/",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        rows = []
        for market_id, market_name in [("STK", "KOSPI"), ("KSQ", "KOSDAQ")]:
            payload = {
                "bld": "dbms/MDC/STAT/standard/MDCSTAT01901",
                "locale": "ko_KR",
                "mktId": market_id,
                "segMktId": "",
                "csvxls_isNo": "false",
            }
            resp = requests.post(url, headers=headers, data=payload, timeout=15)
            data = resp.json()
            for item in data.get("OutBlock_1", []):
                rows.append({
                    "Symbol": item.get("ISU_SRT_CD", ""),
                    "ISU_CD": item.get("ISU_CD", ""),
                    "Name":   item.get("ISU_ABBRV", ""),
                    "Market": market_name,
                    "Marcap": item.get("MKTCAP", 0),
                })
        if rows:
            return pd.DataFrame(rows)
    except Exception:
        pass

    # 최후 수단: 빈 DataFrame (앱이 최소한 실행은 되도록)
    return pd.DataFrame(columns=["Symbol", "Name", "Market"])


def resolve_kr_symbol(user_input):
    df = load_krx_listing()
    raw = (user_input or "").strip()

    if not raw:
        return None, None, None

    if df.empty:
        # 종목 목록 없이도 6자리 코드는 직접 처리
        if raw.isdigit() and len(raw) == 6:
            return raw, raw, "N/A"
        return None, None, None

    if raw.isdigit() and len(raw) == 6:
        row = df[df["Symbol"].astype(str) == raw]
    else:
        row = df[df["Name"].astype(str).str.contains(raw, case=False, na=False)]

    if len(row) == 0:
        # 종목명 검색 실패 시 yfinance로 직접 시도
        try:
            import yfinance as yf
            ticker_ks = f"{raw}.KS"
            info = yf.Ticker(ticker_ks).info or {}
            name = info.get("shortName") or info.get("longName") or raw
            if name and name != raw:
                return raw, name, "KOSPI"
        except Exception:
            pass
        return None, None, None

    r = row.iloc[0]
    symbol = str(r["Symbol"]) if "Symbol" in r.index else None
    name   = str(r["Name"])   if "Name"   in r.index else raw
    market = str(r["Market"]) if "Market" in r.index else "N/A"

    return symbol, name, market
