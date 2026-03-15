import streamlit as st


def render_result(symbol, name, market, pbr, score):

    st.subheader("📊 핵심 지표")

    st.write("현재 PBR:", pbr.get("current_pbr"))

    st.write("평균 PBR:", pbr.get("mean_pbr"))

    st.write("표준편차:", pbr.get("std_pbr"))

    st.write("Z-score:", pbr.get("zscore"))

    st.subheader("🎯 점수")

    st.metric("Score", score["score"])

    st.metric("Grade", score["grade"])