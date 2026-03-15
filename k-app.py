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


st.set_page_config(page_title="한국형 퀀트 주식 분석 엔진 v4", layout="wide")

st.title("📊 한국형 퀀트 주식 분석 엔진 v4")

user_input = st.text_input("회사명 또는 종목코드 입력", "삼성전자")

if user_input:
    symbol, name, market = resolve_kr_symbol(user_input)

    if symbol is None:
        st.error("종목을 찾지 못했습니다.")
        st.stop()

    listing_df = load_krx_listing()

    price_df = get_price_data(symbol)
    if price_df.empty:
        st.error("가격 데이터가 부족합니다.")
        st.stop()

    price_df = add_technical_indicators(price_df)

    investor_df = get_investor_flow_data(symbol)
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
