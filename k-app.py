import streamlit as st

from kr_data_resolver import resolve_kr_symbol, load_krx_listing
from kr_data_price import get_price_data
from kr_data_fundamental import build_pbr_statistics, get_basic_fundamental_snapshot
from kr_indicators import add_technical_indicators, add_bollinger_bands
from kr_scoring import (
    calculate_quality_score,
    calculate_momentum_result,
    calculate_risk_result,
    calculate_shareholder_result,
    calculate_scores,
    build_analysis_payload,
)
from kr_ui import render_full_report


st.set_page_config(page_title="뀨의 한국주식 분석", layout="centered")

st.title("📊 뀨의 한국주식 분석")

# ── session_state 초기화 ──
if "favorites" not in st.session_state:
    st.session_state.favorites = []
if "history" not in st.session_state:
    st.session_state.history = []

# ── 즐겨찾기 / 최근 검색 UI ──
fav_col, hist_col = st.columns(2)

with fav_col:
    if st.session_state.favorites:
        st.markdown("⭐ **즐겨찾기**")
        for fav in st.session_state.favorites:
            if st.button(fav, key=f"fav_{fav}", use_container_width=True):
                st.session_state["input_val"] = fav
                st.rerun()

with hist_col:
    if st.session_state.history:
        st.markdown("🕐 **최근 검색**")
        for h in st.session_state.history[-5:][::-1]:
            if st.button(h, key=f"hist_{h}", use_container_width=True):
                st.session_state["input_val"] = h
                st.rerun()

# ── 검색 입력 ──
default_val = st.session_state.pop("input_val", "삼성전자")
user_input = st.text_input("회사명 또는 종목코드 입력", value=default_val)

if user_input:
    # ── 단계별 프로그레스바 ──
    progress = st.progress(0)
    status   = st.empty()

    status.text("🔍 종목 검색 중...")
    progress.progress(10)

    symbol, name, market = resolve_kr_symbol(user_input)
    if symbol is None:
        st.error("종목을 찾지 못했습니다.")
        st.stop()

    # 최근 검색 히스토리 저장 (중복 제거)
    display_name = name or user_input
    if display_name not in st.session_state.history:
        st.session_state.history.append(display_name)
    if len(st.session_state.history) > 10:
        st.session_state.history = st.session_state.history[-10:]

    # 즐겨찾기 버튼
    is_fav = display_name in st.session_state.favorites
    fav_label = "⭐ 즐겨찾기 해제" if is_fav else "☆ 즐겨찾기 추가"
    if st.button(fav_label, key="toggle_fav"):
        if is_fav:
            st.session_state.favorites.remove(display_name)
        else:
            st.session_state.favorites.append(display_name)
        st.rerun()

    status.text("📈 가격 데이터 로드 중...")
    progress.progress(25)
    listing_df = load_krx_listing()
    price_df   = get_price_data(symbol)

    if price_df.empty:
        st.error("가격 데이터가 부족합니다.")
        st.stop()

    status.text("📐 기술적 지표 계산 중...")
    progress.progress(40)
    price_df = add_technical_indicators(price_df)
    price_df = add_bollinger_bands(price_df)

    status.text("📊 펀더멘털 분석 중...")
    progress.progress(55)
    pbr_stats      = build_pbr_statistics(symbol, price_df)
    funda_snapshot = get_basic_fundamental_snapshot(symbol)

    status.text("🏅 품질 / 모멘텀 분석 중...")
    progress.progress(70)
    quality_result     = calculate_quality_score(symbol, market, listing_df)
    momentum_result    = calculate_momentum_result(price_df)
    risk_result        = calculate_risk_result(symbol, price_df)
    shareholder_result = calculate_shareholder_result(symbol, funda_snapshot)

    status.text("🧮 종합 점수 산출 중...")
    progress.progress(88)
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

    progress.progress(100)
    status.empty()
    progress.empty()

    render_full_report(analysis)

    with st.expander("🔍 디버그 데이터"):
        st.write("pbr_stats", pbr_stats)
        st.write("quality_result", quality_result)
        st.write("momentum_result", momentum_result)
        st.write("risk_result", risk_result)
        st.write("shareholder_result", shareholder_result)
        st.write("funda_snapshot", funda_snapshot)
        bb_cols = [c for c in price_df.columns if c.startswith("BB_")]
        if bb_cols:
            st.write("볼린저밴드 최신값", {c: round(float(price_df[c].iloc[-1]), 2) for c in bb_cols})
