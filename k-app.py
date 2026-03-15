import streamlit as st

from kr_data_resolver import resolve_kr_symbol, load_krx_listing
from kr_data_price import get_price_data, get_investor_flow_data
from kr_data_fundamental import build_pbr_statistics, get_basic_fundamental_snapshot
from kr_indicators import add_technical_indicators
from kr_scoring import (
    calculate_quality_score,
    calculate_supply_score,
    calculate_scores,
    build_analysis_payload,
)
from kr_ui import render_full_report


st.set_page_config(page_title="한국형 퀀트 주식 분석 엔진 v4.1", layout="wide")

st.title("📊 한국형 퀀트 주식 분석 엔진 v4.1")

user_input = st.text_input("회사명 또는 종목코드 입력", "삼성전자")

if user_input:
    symbol, name, market = resolve_kr_symbol(user_input)

    if symbol is None:
        st.error("종목을 찾지 못했습니다.")
        st.stop()

    listing_df = load_krx_listing()

    # ISU_CD 추출 (KRX API용 — 예: KR7005930003)
    isu_cd = None
    if "ISU_CD" in listing_df.columns:
        row = listing_df[listing_df["Symbol"].astype(str) == symbol]
        if len(row) > 0:
            isu_cd = str(row.iloc[0]["ISU_CD"])

    price_df = get_price_data(symbol)
    if price_df.empty:
        st.error("가격 데이터가 부족합니다.")
        st.stop()

    price_df = add_technical_indicators(price_df)

    investor_df = get_investor_flow_data(symbol, isu_cd=isu_cd)
    pbr_stats = build_pbr_statistics(symbol, price_df)
    funda_snapshot = get_basic_fundamental_snapshot(symbol)
    quality_result = calculate_quality_score(symbol, market, listing_df)
    supply_result = calculate_supply_score(investor_df)

    score_result = calculate_scores(price_df, pbr_stats, quality_result, supply_result)

    analysis = build_analysis_payload(
        symbol=symbol,
        name=name,
        market=market,
        price_df=price_df,
        investor_df=investor_df,
        pbr_stats=pbr_stats,
        funda_snapshot=funda_snapshot,
        quality_result=quality_result,
        supply_result=supply_result,
        score_result=score_result,
    )

    render_full_report(analysis)

    with st.expander("디버그 데이터 확인"):
        st.write("pbr_stats", pbr_stats)
        st.write("quality_result", quality_result)
        st.write("supply_result", supply_result)
        st.write("funda_snapshot", funda_snapshot)
        st.write("investor_df columns", list(investor_df.columns) if investor_df is not None and not investor_df.empty else "N/A")
        st.write("listing_df columns", list(listing_df.columns) if listing_df is not None and not listing_df.empty else "N/A")

        st.markdown("---")
        st.markdown("#### yfinance raw info (주요 필드)")
        try:
            import yfinance as yf
            _info = yf.Ticker(f"{symbol}.KS").info or {}
            _keys = [
                "priceToBook", "bookValue", "trailingEps", "forwardEps",
                "trailingPE", "dividendYield", "lastDividendValue",
                "currentPrice", "regularMarketPrice", "returnOnEquity",
                "sharesOutstanding", "impliedSharesOutstanding",
            ]
            st.write({k: _info.get(k) for k in _keys})
            st.markdown("#### quarterly_balance_sheet index")
            _bs = yf.Ticker(f"{symbol}.KS").quarterly_balance_sheet
            st.write(list(_bs.index) if _bs is not None and not _bs.empty else "없음")

            st.markdown("#### annual Stockholders Equity 시계열")
            _t2 = yf.Ticker(f"{symbol}.KS")
            _ann = _t2.balance_sheet
            if _ann is not None and not _ann.empty and "Stockholders Equity" in _ann.index:
                _eq = _ann.loc["Stockholders Equity"]
                st.write({str(k): v for k, v in _eq.items()})
            else:
                st.write("없음")

            st.markdown("#### quarterly Stockholders Equity 시계열")
            _qtr = _t2.quarterly_balance_sheet
            if _qtr is not None and not _qtr.empty and "Stockholders Equity" in _qtr.index:
                _eq2 = _qtr.loc["Stockholders Equity"]
                st.write({str(k): v for k, v in _eq2.items()})
            else:
                st.write("없음")
        except Exception as _e:
            st.write(f"yfinance raw 조회 실패: {_e}")

        st.markdown("---")
        st.markdown("#### FDR DataReader 컬럼 및 최신 펀더멘털")
        try:
            import FinanceDataReader as _fdr
            _fdr_df = _fdr.DataReader(symbol)
            st.write("FDR 컬럼:", list(_fdr_df.columns) if _fdr_df is not None and not _fdr_df.empty else "없음")
            if _fdr_df is not None and not _fdr_df.empty:
                st.write("FDR 최신 행:", {str(k): float(v) if hasattr(v, 'item') else v for k, v in _fdr_df.iloc[-1].items()})
                pbr_col_exists = "PBR" in _fdr_df.columns
                st.write("PBR 컬럼 존재:", pbr_col_exists)
                if pbr_col_exists:
                    _pbr_s = _fdr_df["PBR"].dropna()
                    st.write(f"PBR 유효 행수: {len(_pbr_s)}, 최신값: {float(_pbr_s.iloc[-1]) if len(_pbr_s)>0 else 'N/A'}")
        except Exception as _e2:
            st.write(f"FDR 조회 실패: {_e2}")
