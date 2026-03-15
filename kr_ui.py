import streamlit as st
import math


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

    # 상단 핵심 요약
    st.markdown("### 📌 핵심 요약")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("현재 주가", fmt_krw(a["current_price"]), fmt_pct(a["pct_change"]))

    with c2:
        pbr_val = a["pbr_stats"].get("current_pbr")
        st.metric("현재 PBR", fmt_mul(pbr_val) if a["pbr_stats"].get("available") else "N/A")

    with c3:
        st.metric("점수", str(a["score"]))

    with c4:
        st.metric("등급", a["grade"])

    # 1행 카드
    st.markdown("### 📚 핵심 분석 카드")
    r1c1, r1c2 = st.columns(2)

    with r1c1:
        if a["pbr_stats"].get("available"):
            desc = (
                f"평균 PBR {fmt_mul(a['pbr_stats'].get('mean_pbr'))}, "
                f"표준편차 {fmt_num(a['pbr_stats'].get('std_pbr'), 3)}, "
                f"Z-score {fmt_num(a['pbr_stats'].get('zscore'), 3)}, "
                f"표본 {a['pbr_stats'].get('sample_months')}개월 "
                f"({a['pbr_stats'].get('sample_grade')})"
            )
            card("Valuation", fmt_mul(a["pbr_stats"].get("current_pbr")), desc)
        else:
            card("Valuation", "N/A", f"PBR 분석 불가: {a['pbr_stats'].get('reason', 'N/A')}")

    with r1c2:
        card(
            "리스크(MDD)",
            fmt_pct(a["mdd"]),
            "최근 1년 구간 기준 최대 낙폭입니다. 장기 보유 시 감내 가능한 변동성 수준인지 점검할 필요가 있습니다.",
        )

    # 2행 카드
    r2c1, r2c2 = st.columns(2)

    with r2c1:
        trend_desc = (
            f"MA20 {fmt_krw(a['ma20'])} / "
            f"MA60 {fmt_krw(a['ma60'])} / "
            f"MA120 {fmt_krw(a['ma120'])}"
        )
        card("추세", "정배열" if (a["ma20"] > a["ma60"] > a["ma120"]) else "혼조/역배열", trend_desc)

    with r2c2:
        card("모멘텀", f"RSI {fmt_num(a['rsi'])}", a["macd_comment"])

    # 3행 카드
    r3c1, r3c2 = st.columns(2)

    with r3c1:
        vol_text = fmt_num(a["vol_ratio"], 2) + "배" if a["vol_ratio"] is not None else "N/A"
        card("거래량 평가", vol_text, a["volume_comment"])

    with r3c2:
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
    st.markdown(
        f"""
        <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin-bottom:14px;">
            <div style="font-weight:800;font-size:18px;margin-bottom:8px;">단기 전략</div>
            <div style="color:#475569;line-height:1.7;">{a['short_strategy']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin-bottom:14px;">
            <div style="font-weight:800;font-size:18px;margin-bottom:8px;">중기 전략</div>
            <div style="color:#475569;line-height:1.7;">{a['mid_strategy']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
