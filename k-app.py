import streamlit as st
import pandas as pd

from kr_data_resolver import resolve_kr_symbol
from kr_data_price import get_price_data
from kr_data_fundamental import build_pbr_statistics
from kr_indicators import add_technical_indicators
from kr_scoring import calculate_scores
from kr_ui import render_result


st.set_page_config(page_title="한국형 퀀트 엔진", layout="wide")

st.title("📊 한국형 퀀트 주식 분석 엔진")

user_input = st.text_input("회사명 또는 종목코드 입력", "삼성전자")

if user_input:

    symbol, name, market = resolve_kr_symbol(user_input)

    if symbol is None:
        st.error("종목을 찾지 못했습니다.")
        st.stop()

    st.subheader(f"{name} ({symbol}) / {market}")

    price_df = get_price_data(symbol)

    if price_df.empty:
        st.error("가격 데이터 부족")
        st.stop()

    price_df = add_technical_indicators(price_df)

    pbr_stats = build_pbr_statistics(symbol, price_df)

    scores = calculate_scores(price_df, pbr_stats)

    render_result(symbol, name, market, pbr_stats, scores)