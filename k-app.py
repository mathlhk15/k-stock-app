import streamlit as st

from kr_data_resolver import resolve_kr_symbol, load_krx_listing
from kr_data_price import get_price_data
from kr_data_fundamental import build_pbr_statistics, get_basic_fundamental_snapshot
from kr_indicators import add_technical_indicators
from kr_scoring import (
    calculate_quality_score,
    calculate_momentum_result,
    calculate_risk_result,
    calculate_shareholder_result,
    calculate_scores,
    build_analysis_payload,
)
from kr_ui import render_full_report


st.set_page_config(page_title="꾀의 주식 분석", layout="centered")

st.title("📊 꾀의 주식 분석")

user_input = st.text_input("회사명 또는 종목코드 입력", "삼성전자")

if user_input:
    with st.spinner("분석 중..."):
        symbol, name, market = resolve_kr_symbol(user_input)

        if symbol is None:
            st.error("종목을 찾지 못했습니다.")
            st.stop()

        listing_df     = load_krx_listing()
        price_df       = get_price_data(symbol)

        if price_df.empty:
            st.error("가격 데이터가 부족합니다.")
            st.stop()

        price_df       = add_technical_indicators(price_df)
        pbr_stats      = build_pbr_statistics(symbol, price_df)
        funda_snapshot = get_basic_fundamental_snapshot(symbol)
        quality_result = calculate_quality_score(symbol, market, listing_df)

        momentum_result    = calculate_momentum_result(price_df)
        risk_result        = calculate_risk_result(symbol, price_df)
        shareholder_result = calculate_shareholder_result(symbol, funda_snapshot)

        score_result = calculate_scores(
            price_df, pbr_stats, quality_result,
            momentum_result, risk_result, shareholder_result,
        )

        analysis = build_analysis_payload(
            symbol=symbol, name=name, market=market,
            price_df=price_df,
            pbr_stats=pbr_stats, funda_snapshot=funda_snapshot,
            quality_result=quality_result, score_result=score_result,
            momentum_result=momentum_result,
            risk_result=risk_result,
            shareholder_result=shareholder_result,
        )

    render_full_report(analysis)

    with st.expander("🔍 디버그 데이터"):
        st.write("pbr_stats", pbr_stats)
        st.write("quality_result", quality_result)
        st.write("momentum_result", momentum_result)
        st.write("risk_result", risk_result)
        st.write("shareholder_result", shareholder_result)
        st.write("funda_snapshot", funda_snapshot)
