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


def _grade_color(grade):
    return {
        "Strong Buy": ("#dcfce7", "#166534", "#16a34a"),
        "Buy":        ("#dbeafe", "#1e3a8a", "#2563eb"),
        "Hold":       ("#fef9c3", "#713f12", "#ca8a04"),
        "Caution":    ("#ffedd5", "#7c2d12", "#ea580c"),
        "Avoid":      ("#fee2e2", "#7f1d1d", "#dc2626"),
    }.get(grade, ("#f1f5f9", "#334155", "#64748b"))


def card(title, value, desc="", tooltip=""):
    tooltip_html = ""
    if tooltip:
        tooltip_html = f"""
        <div style="
            background:#eff6ff;
            border-left:3px solid #3b82f6;
            border-radius:0 6px 6px 0;
            padding:10px 14px;
            margin-top:8px;
            font-size:13px;
            color:#1e40af;
            line-height:1.6;
        ">💡 {tooltip}</div>
        """
    st.markdown(
        f"""
        <div style="
            background:#ffffff;
            border:1px solid #e2e8f0;
            border-radius:14px;
            padding:18px 16px;
            margin-bottom:12px;
            box-shadow:0 2px 8px rgba(15,23,42,0.06);
        ">
            <div style="color:#64748b;font-size:13px;font-weight:700;margin-bottom:6px;letter-spacing:0.3px;">{title}</div>
            <div style="font-weight:800;font-size:22px;color:#0f172a;line-height:1.2;">{value}</div>
            <div style="background:#f8fafc;border-left:3px solid #94a3b8;padding:10px 14px;margin-top:10px;
                        border-radius:0 6px 6px 0;font-size:13px;color:#475569;line-height:1.6;">{desc}</div>
            {tooltip_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_full_report(a):
    # ── 헤더 ──
    st.markdown(
        f"""
        <div style="padding:4px 0 12px 0;">
            <div style="font-size:22px;font-weight:900;color:#0f172a;line-height:1.3;">
                {a['name']}
            </div>
            <div style="font-size:14px;color:#64748b;margin-top:2px;">
                {a['symbol']} · {a['market']}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 등급 배너 ──
    bg, fg, border = _grade_color(a["grade"])
    score = a["score"]
    st.markdown(
        f"""
        <div style="
            background:{bg};border:2px solid {border};border-radius:14px;
            padding:16px 18px;margin-bottom:16px;
            display:flex;justify-content:space-between;align-items:center;
        ">
            <div>
                <div style="font-size:12px;font-weight:700;color:{fg};letter-spacing:1px;">종합 등급</div>
                <div style="font-size:28px;font-weight:900;color:{fg};line-height:1.1;">{a['grade']}</div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:12px;font-weight:700;color:{fg};">종합 점수</div>
                <div style="font-size:28px;font-weight:900;color:{fg};">{score}점</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if a["flags"]:
        st.success(" | ".join(a["flags"]))

    # ── 핵심 수치 2×2 그리드 ──
    st.markdown("### 📌 핵심 수치")

    pct = a["pct_change"]
    pct_color = "#16a34a" if pct >= 0 else "#dc2626"
    pct_arrow = "▲" if pct >= 0 else "▼"
    roe = a["quality_result"].get("roe")
    roe_str = f"{roe*100:.2f}%" if roe is not None else "N/A"
    pbr_str = fmt_mul(a["pbr_stats"].get("current_pbr")) if a["pbr_stats"].get("available") else "N/A"
    mdd_str = fmt_pct(a["mdd"])

    st.markdown(
        f"""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px;">
            <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px;">
                <div style="font-size:12px;color:#64748b;font-weight:700;">현재 주가</div>
                <div style="font-size:20px;font-weight:900;color:#0f172a;">{fmt_krw(a['current_price'])}</div>
                <div style="font-size:13px;color:{pct_color};font-weight:700;">{pct_arrow} {abs(pct):.2f}%</div>
            </div>
            <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px;">
                <div style="font-size:12px;color:#64748b;font-weight:700;">현재 PBR</div>
                <div style="font-size:20px;font-weight:900;color:#0f172a;">{pbr_str}</div>
                <div style="font-size:13px;color:#64748b;">백분위 {fmt_pct(a['pbr_stats'].get('percentile'))}</div>
            </div>
            <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px;">
                <div style="font-size:12px;color:#64748b;font-weight:700;">ROE</div>
                <div style="font-size:20px;font-weight:900;color:#0f172a;">{roe_str}</div>
                <div style="font-size:13px;color:#64748b;">시장 백분위 {fmt_pct(a['quality_result'].get('roe_percentile'))}</div>
            </div>
            <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px;">
                <div style="font-size:12px;color:#64748b;font-weight:700;">MDD (1년)</div>
                <div style="font-size:20px;font-weight:900;color:#dc2626;">{mdd_str}</div>
                <div style="font-size:13px;color:#64748b;">고점 대비 최대 낙폭</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 분석 카드 ──
    st.markdown("### 📚 분석 카드")

    # Valuation
    if a["pbr_stats"].get("available"):
        val_desc = (
            f"평균 PBR {fmt_mul(a['pbr_stats'].get('mean_pbr'))} / "
            f"Z-score {fmt_num(a['pbr_stats'].get('zscore'), 2)} / "
            f"백분위 {fmt_pct(a['pbr_stats'].get('percentile'))} / "
            f"표본 {a['pbr_stats'].get('sample_months')}개월 ({a['pbr_stats'].get('sample_grade')})"
        )
        card("📊 Valuation (PBR)", fmt_mul(a["pbr_stats"].get("current_pbr")), val_desc,
             tooltip="Z-score ≤ -1이면 역사적 저평가, ≥ +1이면 고평가 구간입니다.")
    else:
        card("📊 Valuation (PBR)", "N/A", f"분석 불가: {a['pbr_stats'].get('reason', '')}")

    # Quality
    card(
        "🏅 Quality (ROE)",
        f"ROE {roe_str}",
        (
            f"시장 내 ROE 백분위 {fmt_pct(a['quality_result'].get('roe_percentile'))} / "
            f"점수 {a['quality_result'].get('score', 0)}점"
            if a["quality_result"].get("available")
            else f"분석 불가: {a['quality_result'].get('reason', '')}"
        ),
        tooltip="ROE = 당기순이익 ÷ 자기자본. 70백분위↑면 우량 기업입니다.",
    )

    # 추세
    trend_state = "📈 정배열" if (a["ma20"] > a["ma60"] > a["ma120"]) else "📉 혼조/역배열"
    trend_desc = f"MA20 {fmt_krw(a['ma20'])} / MA60 {fmt_krw(a['ma60'])} / MA120 {fmt_krw(a['ma120'])}"
    card("📐 추세", trend_state, trend_desc,
         tooltip="MA20 > MA60 > MA120 정배열이면 단·중·장기 추세가 모두 상승 방향입니다.")

    # 모멘텀
    card("⚡ 모멘텀", f"RSI {fmt_num(a['rsi'])}", a["macd_comment"],
         tooltip="RSI 70↑ 과매수, 30↓ 과매도. MACD가 시그널선 위면 단기 상승 모멘텀.")

    # 거래량
    vol_text = fmt_num(a["vol_ratio"], 2) + "배" if a["vol_ratio"] is not None else "N/A"
    card("📦 거래량", vol_text, a["volume_comment"],
         tooltip="현재 거래량 ÷ 20일 평균. 1.5배↑면 강한 수급 신호입니다.")

    # 점수 근거
    score_reason = " / ".join(a["score_reasons"]) if a["score_reasons"] else "가산/감산 요인 없음"
    card("🔢 점수 근거", f"{score}점", score_reason,
         tooltip="Valuation(±40) + Quality(30) + 기술(10). 80↑ Strong Buy / 65↑ Buy / 50↑ Hold / 35↑ Caution / 35↓ Avoid")

    # ── 지지/저항 ──
    st.markdown("### 📍 지지 / 저항")
    st.markdown(
        f"""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px;">
            <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:12px;padding:14px;">
                <div style="font-size:12px;color:#166534;font-weight:700;">1차 지지</div>
                <div style="font-size:18px;font-weight:900;color:#166534;">{fmt_krw(a['support_1'])}</div>
            </div>
            <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:12px;padding:14px;">
                <div style="font-size:12px;color:#166534;font-weight:700;">2차 지지</div>
                <div style="font-size:18px;font-weight:900;color:#166534;">{fmt_krw(a['support_2'])}</div>
            </div>
            <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:12px;padding:14px;">
                <div style="font-size:12px;color:#991b1b;font-weight:700;">1차 저항</div>
                <div style="font-size:18px;font-weight:900;color:#991b1b;">{fmt_krw(a['resistance_1'])}</div>
            </div>
            <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:12px;padding:14px;">
                <div style="font-size:12px;color:#991b1b;font-weight:700;">2차 저항</div>
                <div style="font-size:18px;font-weight:900;color:#991b1b;">{fmt_krw(a['resistance_2'])}</div>
            </div>
        </div>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px;margin-bottom:16px;">
            <div style="font-size:12px;color:#64748b;font-weight:700;">52주 고가</div>
            <div style="font-size:18px;font-weight:900;color:#0f172a;">{fmt_krw(a['high_52'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 관심 구간 ──
    st.markdown("### 🎯 관심 구간")
    st.markdown(
        f"""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px;">
            <div style="background:#eff6ff;border:1px solid #93c5fd;border-radius:12px;padding:14px;">
                <div style="font-size:12px;color:#1e40af;font-weight:700;">1차 관심 구간</div>
                <div style="font-size:15px;font-weight:800;color:#1e40af;">{fmt_krw(a['zone1_low'])}</div>
                <div style="font-size:13px;color:#3b82f6;">~ {fmt_krw(a['zone1_high'])}</div>
                <div style="font-size:12px;color:#64748b;margin-top:4px;">MA20 기준 단기 눌림목</div>
            </div>
            <div style="background:#f5f3ff;border:1px solid #c4b5fd;border-radius:12px;padding:14px;">
                <div style="font-size:12px;color:#5b21b6;font-weight:700;">2차 보수 구간</div>
                <div style="font-size:15px;font-weight:800;color:#5b21b6;">{fmt_krw(a['zone2_low'])}</div>
                <div style="font-size:13px;color:#7c3aed;">~ {fmt_krw(a['zone2_high'])}</div>
                <div style="font-size:12px;color:#64748b;margin-top:4px;">MA60 기준 보수적 재확인</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 투자 전략 ──
    st.markdown("### 🧭 투자 전략")
    card("단기 전략 (1~2주)", "", a["short_strategy"])
    card("중기 전략 (1~3개월)", "", a["mid_strategy"])

    # ── 시나리오 ──
    st.markdown("### ⚖️ 시나리오")
    st.markdown(
        f"""
        <div style="background:#ecfdf5;border:1px solid #6ee7b7;border-radius:14px;
                    padding:16px 18px;margin-bottom:12px;">
            <div style="font-weight:900;font-size:15px;color:#065f46;margin-bottom:8px;">🟢 강세 시나리오</div>
            <div style="font-size:14px;color:#065f46;line-height:1.7;">{a['bull_scenario']}</div>
        </div>
        <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:14px;
                    padding:16px 18px;margin-bottom:16px;">
            <div style="font-weight:900;font-size:15px;color:#991b1b;margin-bottom:8px;">🔴 약세 시나리오</div>
            <div style="font-size:14px;color:#991b1b;line-height:1.7;">{a['bear_scenario']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
