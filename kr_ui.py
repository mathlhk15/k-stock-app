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


def fmt_pct(v):
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.2f}%"
    except Exception:
        return "N/A"


def fmt_num(v, digits=2):
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return "N/A"


def card(title, value, desc=""):
    st.markdown(
        f"""
        <div style="
            background-color:#ffffff;
            border:1px solid #e2e8f0;
            border-radius:12px;
            padding:16px;
            margin-bottom:14px;
            box-shadow:0 2px 6px rgba(15,23,42,0.04);
        ">
            <div style="color:#64748b;font-size:12px;font-weight:700;margin-bottom:4px;">{title}</div>
            <div style="font-weight:800;font-size:20px;color:#0f172a;">{value}</div>
            <div style="background-color:#f1f5f9;border-left:3px solid #64748b;padding:10px 14px;margin-top:10px;border-radius:0 6px 6px 0;font-size:13px;color:#475569;line-height:1.5;">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_full_report(a):
    st.markdown(f"## {a['name']} ({a['symbol']}) / {a['market']}")

    # 상단 요약
    st.markdown("### 📌 핵심 요약")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("현재 주가", fmt_krw(a["current_price"]), fmt_pct(a["pct_change"]))

    with c2:
        st.metric(
            "현재 PBR",
            fmt_mul(a["pbr_stats"].get("current_pbr")) if a["pbr_stats"].get("available") else "N/A",
        )

    with c3:
        roe = a["quality_result"].get("roe")
        st.metric("ROE", fmt_pct(roe * 100 if roe is not None else None) if False else (f"{roe*100:.2f}%" if roe is not None else "N/A"))

    with c4:
        st.metric("등급", a["grade"])

    # 플래그
    if a["flags"]:
        st.success(" | ".join(a["flags"]))

    # 핵심 분석 카드
    st.markdown("### 📚 핵심 분석 카드")
    r1c1, r1c2 = st.columns(2)

    with r1c1:
        if a["pbr_stats"].get("available"):
            desc = (
                f"평균 PBR {fmt_mul(a['pbr_stats'].get('mean_pbr'))}, "
                f"표준편차 {fmt_num(a['pbr_stats'].get('std_pbr'), 3)}, "
                f"Z-score {fmt_num(a['pbr_stats'].get('zscore'), 3)}, "
                f"PBR 백분위 {fmt_pct(a['pbr_stats'].get('percentile'))}, "
                f"표본 {a['pbr_stats'].get('sample_months')}개월 "
                f"({a['pbr_stats'].get('sample_grade')})"
            )
            card("Valuation", fmt_mul(a["pbr_stats"].get("current_pbr")), desc)
        else:
            card("Valuation", "N/A", f"PBR 분석 불가: {a['pbr_stats'].get('reason', 'N/A')}")

    with r1c2:
        card(
            "Quality",
            f"ROE {a['quality_result']['roe']*100:.2f}%" if a["quality_result"].get("roe") is not None else "N/A",
            (
                f"시장 내 ROE 백분위 {fmt_pct(a['quality_result'].get('roe_percentile'))}, "
                f"점수 {a['quality_result'].get('score', 0)}점"
                if a["quality_result"].get("available")
                else f"Quality 분석 불가: {a['quality_result'].get('reason', 'N/A')}"
            ),
        )

    r2c1, r2c2 = st.columns(2)

    with r2c1:
        card(
            "Supply",
            fmt_num(a["supply_result"].get("supply_strength"), 0) if a["supply_result"].get("available") else "N/A",
            (
                f"최근 20일 수급 백분위 {fmt_pct(a['supply_result'].get('supply_percentile'))}, "
                f"점수 {a['supply_result'].get('score', 0)}점"
                if a["supply_result"].get("available")
                else f"Supply 분석 불가: {a['supply_result'].get('reason', 'N/A')}"
            ),
        )

    with r2c2:
        card(
            "리스크(MDD)",
            fmt_pct(a["mdd"]),
            "최근 1년 구간 기준 최대 낙폭입니다. 장기 보유 시 감내 가능한 변동성 수준인지 점검할 필요가 있습니다.",
        )

    r3c1, r3c2 = st.columns(2)

    with r3c1:
        trend_state = "정배열" if (a["ma20"] > a["ma60"] > a["ma120"]) else "혼조/역배열"
        trend_desc = (
            f"MA20 {fmt_krw(a['ma20'])} / "
            f"MA60 {fmt_krw(a['ma60'])} / "
            f"MA120 {fmt_krw(a['ma120'])}"
        )
        card("추세", trend_state, trend_desc)

    with r3c2:
        card("모멘텀", f"RSI {fmt_num(a['rsi'])}", a["macd_comment"])

    r4c1, r4c2 = st.columns(2)

    with r4c1:
        vol_text = fmt_num(a["vol_ratio"], 2) + "배" if a["vol_ratio"] is not None else "N/A"
        card("거래량 평가", vol_text, a["volume_comment"])

    with r4c2:
        score_reason = " / ".join(a["score_reasons"]) if a["score_reasons"] else "가산/감산 요인 없음"
        card("점수 근거", str(a["score"]), score_reason)

    # 지지/저항
    st.markdown("### 📍 주요 지지 / 저항 레벨")
    s1, s2, r1, r2, h52 = st.columns(5)

    with s1:
        st.metric("1차 지지", fmt_krw(a["support_1"]))
    with s2:
        st.metric("2차 지지", fmt_krw(a["support_2"]))
    with r1:
        st.metric("1차 저항", fmt_krw(a["resistance_1"]))
    with r2:
        st.metric("2차 저항", fmt_krw(a["resistance_2"]))
    with h52:
        st.metric("52주 고가", fmt_krw(a["high_52"]))

    # 관심 구간
    st.markdown("### 🎯 기계적 관심 구간")
    z1, z2 = st.columns(2)

    with z1:
        card(
            "1차 관심 구간",
            f"{fmt_krw(a['zone1_low'])} ~ {fmt_krw(a['zone1_high'])}",
            "MA20과 ATR을 기준으로 산출한 단기 눌림목 관찰 구간입니다.",
        )

    with z2:
        card(
            "2차 보수 구간",
            f"{fmt_krw(a['zone2_low'])} ~ {fmt_krw(a['zone2_high'])}",
            "MA60과 ATR을 기준으로 산출한 보다 보수적인 재확인 구간입니다.",
        )

    # 전략
    st.markdown("### 🧭 투자 전략")
    card("단기 전략", "1~2주", a["short_strategy"])
    card("중기 전략", "1~3개월", a["mid_strategy"])

    # 시나리오
    st.markdown("### ⚖️ 시나리오 분석")
    b1, b2 = st.columns(2)

    with b1:
        st.markdown(
            f"""
            <div style="background:#ecfdf5;border:1px solid #6ee7b7;border-radius:12px;padding:16px;color:#065f46;height:100%;">
                <div style="font-weight:900;font-size:16px;margin-bottom:10px;">강세 시나리오</div>
                <div style="line-height:1.7;">{a['bull_scenario']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with b2:
        st.markdown(
            f"""
            <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:12px;padding:16px;color:#991b1b;height:100%;">
                <div style="font-weight:900;font-size:16px;margin-bottom:10px;">약세 시나리오</div>
                <div style="line-height:1.7;">{a['bear_scenario']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 수급 차트
    _render_investor_flow_chart(a.get("investor_df"))


def _render_investor_flow_chart(investor_df):
    """외국인 & 기관 매수금액 차트"""
    import streamlit as st

    st.markdown("### 📈 외국인 & 기관 수급")

    if investor_df is None or (hasattr(investor_df, "empty") and investor_df.empty):
        st.info("수급 데이터를 불러오지 못했습니다. KRX 서버 응답을 확인하세요.")
        return

    # 외국인 / 기관 컬럼 탐색
    foreign_candidates = ["외국인합계", "외국인", "외국인계"]
    inst_candidates    = ["기관합계", "기관", "기관계"]

    foreign_col = next((c for c in foreign_candidates if c in investor_df.columns), None)
    inst_col    = next((c for c in inst_candidates    if c in investor_df.columns), None)

    if foreign_col is None or inst_col is None:
        st.info(f"외국인/기관 컬럼을 찾을 수 없습니다. 컬럼: {list(investor_df.columns)}")
        return

    # 최근 100거래일만 표시
    df = investor_df[[foreign_col, inst_col]].tail(100).copy()
    df.columns = ["외국인", "기관"]

    # 단위: 백만원
    df = df / 1_000_000

    import pandas as pd
    # 20일 롤링 합계
    df["외국인_20일"] = df["외국인"].rolling(20).sum()
    df["기관_20일"]   = df["기관"].rolling(20).sum()

    # 일별 Bar + 20일 Rolling Line 차트
    import streamlit as st
    import plotly.graph_objects as go

    fig = go.Figure()

    # 외국인 일별 막대
    colors_foreign = ["#3b82f6" if v >= 0 else "#ef4444" for v in df["외국인"]]
    fig.add_trace(go.Bar(
        x=df.index, y=df["외국인"],
        name="외국인 (일별)",
        marker_color=colors_foreign,
        opacity=0.5,
        yaxis="y1",
    ))

    # 기관 일별 막대
    colors_inst = ["#f97316" if v >= 0 else "#a855f7" for v in df["기관"]]
    fig.add_trace(go.Bar(
        x=df.index, y=df["기관"],
        name="기관 (일별)",
        marker_color=colors_inst,
        opacity=0.5,
        yaxis="y1",
    ))

    # 20일 누적 라인
    fig.add_trace(go.Scatter(
        x=df.index, y=df["외국인_20일"],
        name="외국인 20일 누적",
        line=dict(color="#1d4ed8", width=2),
        yaxis="y1",
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["기관_20일"],
        name="기관 20일 누적",
        line=dict(color="#c2410c", width=2),
        yaxis="y1",
    ))

    fig.update_layout(
        title="외국인 & 기관 매수금액 (단위: 백만원)",
        barmode="group",
        xaxis=dict(title="날짜"),
        yaxis=dict(title="매수금액 (백만원)", zeroline=True, zerolinecolor="#94a3b8"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=420,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
    )

    st.plotly_chart(fig, use_container_width=True)
