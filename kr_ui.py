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


def card(title, value, desc="", tooltip=""):
    tooltip_html = ""
    if tooltip:
        tooltip_html = f"""
        <div style="
            background-color:#eff6ff;
            border-left:3px solid #3b82f6;
            border-radius:0 6px 6px 0;
            padding:8px 14px;
            margin-top:6px;
            font-size:12px;
            color:#1e40af;
            line-height:1.5;
        ">💡 {tooltip}</div>
        """
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
            {tooltip_html}
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
            card(
                "Valuation",
                fmt_mul(a["pbr_stats"].get("current_pbr")),
                desc,
                tooltip=(
                    "PBR(주가순자산비율)이 과거 평균 대비 얼마나 높거나 낮은지를 Z-score로 나타냅니다. "
                    "Z-score가 -1 이하면 역사적으로 저평가 구간, +1 이상이면 고평가 구간입니다. "
                    "백분위가 낮을수록 과거보다 싸게 거래되고 있다는 의미입니다."
                ),
            )
        else:
            card("Valuation", "N/A", f"PBR 분석 불가: {a['pbr_stats'].get('reason', 'N/A')}",
                 tooltip="PBR(주가순자산비율) = 주가 ÷ 주당순자산. 1배 미만이면 장부가치보다 싸게 거래 중임을 의미합니다.")

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
            tooltip=(
                "ROE(자기자본이익률) = 당기순이익 ÷ 자기자본. 기업이 자본을 얼마나 효율적으로 활용해 이익을 내는지 나타냅니다. "
                "동일 시장 내 동종 기업들과 비교한 백분위로 평가하며, 상위 30%(70백분위↑)면 우량 기업으로 분류됩니다."
            ),
        )

    r2c1, = st.columns(1)

    with r2c1:
        card(
            "리스크(MDD)",
            fmt_pct(a["mdd"]),
            "최근 1년 구간 기준 최대 낙폭입니다. 장기 보유 시 감내 가능한 변동성 수준인지 점검할 필요가 있습니다.",
            tooltip=(
                "MDD(최대낙폭) = 고점 대비 최저점까지의 하락률. "
                "-30% 이하면 고변동성 종목으로, 손절 기준과 포지션 크기를 보수적으로 설정해야 합니다. "
                "수익률이 좋아도 MDD가 크면 심리적으로 버티기 어렵습니다."
            ),
        )

    r3c1, r3c2 = st.columns(2)

    with r3c1:
        trend_state = "정배열" if (a["ma20"] > a["ma60"] > a["ma120"]) else "혼조/역배열"
        trend_desc = (
            f"MA20 {fmt_krw(a['ma20'])} / "
            f"MA60 {fmt_krw(a['ma60'])} / "
            f"MA120 {fmt_krw(a['ma120'])}"
        )
        card(
            "추세",
            trend_state,
            trend_desc,
            tooltip=(
                "이동평균선 정배열(MA20 > MA60 > MA120)은 단기·중기·장기 추세가 모두 상승 방향임을 의미합니다. "
                "정배열 구간에서는 눌림목 매수 전략이 유리하고, 역배열에서는 반등 시 매도 압력이 강합니다."
            ),
        )

    with r3c2:
        card(
            "모멘텀",
            f"RSI {fmt_num(a['rsi'])}",
            a["macd_comment"],
            tooltip=(
                "RSI(상대강도지수): 0~100 범위로 70 이상이면 과매수(단기 조정 가능성), "
                "30 이하면 과매도(반등 가능성)를 나타냅니다. "
                "MACD가 시그널선 위에 있으면 단기 상승 모멘텀이 살아있다는 신호입니다."
            ),
        )

    r4c1, r4c2 = st.columns(2)

    with r4c1:
        vol_text = fmt_num(a["vol_ratio"], 2) + "배" if a["vol_ratio"] is not None else "N/A"
        card(
            "거래량 평가",
            vol_text,
            a["volume_comment"],
            tooltip=(
                "현재 거래량을 20일 평균 거래량으로 나눈 값입니다. "
                "1.5배 이상이면 강한 수급 신호, 0.7배 미만이면 관망세로 해석합니다. "
                "주가 움직임은 거래량 증가를 수반할 때 신뢰도가 높아집니다."
            ),
        )

    with r4c2:
        score_reason = " / ".join(a["score_reasons"]) if a["score_reasons"] else "가산/감산 요인 없음"
        card(
            "점수 근거",
            str(a["score"]),
            score_reason,
            tooltip=(
                "Valuation(최대 ±40점) + Quality(최대 30점) + Supply(최대 20점) + 기술적 지표(최대 10점)로 구성됩니다. "
                "80점↑ Strong Buy / 65점↑ Buy / 50점↑ Hold / 35점↑ Caution / 35점 미만 Avoid. "
                "펀더멘털 데이터가 없으면 Buy 이상 등급은 Hold로 자동 하향됩니다."
            ),
        )

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
