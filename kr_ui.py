import streamlit as st


def fmt_krw(v):
    if v is None:
        return "N/A"
    try:
        return f"{int(round(v)):,}원"
    except Exception:
        return "N/A"


def fmt_mul(v):
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.2f}배"
    except Exception:
        return "N/A"


def fmt_num(v):
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.3f}"
    except Exception:
        return "N/A"


def render_result(symbol, name, market, pbr, score, price_df):
    st.subheader("📊 핵심 지표")

    current_price = None
    if "Close" in price_df.columns and len(price_df) > 0:
        current_price = price_df["Close"].iloc[-1]

    col1, col2 = st.columns(2)

    with col1:
        st.metric("현재 주가", fmt_krw(current_price))
        st.metric("점수", score["score"])

    with col2:
        st.metric("등급", score["grade"])
        st.metric("시장", market)

    st.subheader("📚 PBR 분석")

    if pbr.get("available"):
        st.write("현재 PBR:", fmt_mul(pbr.get("current_pbr")))
        st.write("평균 PBR:", fmt_mul(pbr.get("mean_pbr")))
        st.write("표준편차:", fmt_num(pbr.get("std_pbr")))
        st.write("Z-score:", fmt_num(pbr.get("zscore")))
    else:
        st.info(f"PBR 분석: {pbr.get('reason', 'N/A')}")

    st.subheader("📈 기술 지표")

    if "MA20" in price_df.columns:
        st.write("MA20:", fmt_krw(price_df["MA20"].iloc[-1]) if price_df["MA20"].iloc[-1] == price_df["MA20"].iloc[-1] else "N/A")
    if "MA60" in price_df.columns:
        st.write("MA60:", fmt_krw(price_df["MA60"].iloc[-1]) if price_df["MA60"].iloc[-1] == price_df["MA60"].iloc[-1] else "N/A")
    if "MA120" in price_df.columns:
        st.write("MA120:", fmt_krw(price_df["MA120"].iloc[-1]) if price_df["MA120"].iloc[-1] == price_df["MA120"].iloc[-1] else "N/A")
    if "RSI" in price_df.columns:
        rsi = price_df["RSI"].iloc[-1]
        st.write("RSI:", f"{rsi:.2f}" if rsi == rsi else "N/A")
