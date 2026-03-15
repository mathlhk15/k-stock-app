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
    """desc는 순수 텍스트만 사용 (HTML 태그 없이)"""
    tooltip_html = ""
    if tooltip:
        tooltip_html = f'<div style="background:#eff6ff;border-left:3px solid #3b82f6;border-radius:0 6px 6px 0;padding:10px 14px;margin-top:10px;font-size:13px;color:#1e40af;line-height:1.7;">💡 {tooltip}</div>'
    value_html = f'<div style="font-weight:800;font-size:20px;color:#0f172a;line-height:1.3;margin-bottom:8px;">{value}</div>' if value else ""
    st.markdown(
        f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:16px;margin-bottom:12px;box-shadow:0 1px 6px rgba(15,23,42,0.05);">'
        f'<div style="color:#64748b;font-size:12px;font-weight:700;margin-bottom:6px;">{title}</div>'
        f'{value_html}'
        f'<div style="font-size:13px;color:#475569;line-height:1.7;white-space:pre-wrap;">{desc}</div>'
        f'{tooltip_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _grid2(items):
    """2열 그리드 HTML 생성 — items는 (label, value, sub, bg, border, color) 튜플 리스트"""
    cells = ""
    for label, value, sub, bg, border, color in items:
        cells += (
            f'<div style="background:{bg};border:1px solid {border};border-radius:12px;padding:13px 11px;min-height:76px;">'
            f'<div style="font-size:11px;color:#64748b;font-weight:700;margin-bottom:4px;">{label}</div>'
            f'<div style="font-size:16px;font-weight:900;color:{color};word-break:keep-all;line-height:1.3;">{value}</div>'
            f'<div style="font-size:12px;color:#94a3b8;margin-top:3px;">{sub}</div>'
            f'</div>'
        )
    return f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:18px;">{cells}</div>'


def _single_box(label, value, sub="", bg="#f8fafc", border="#e2e8f0", color="#0f172a"):
    return (
        f'<div style="background:{bg};border:1px solid {border};border-radius:12px;padding:13px 11px;margin-bottom:10px;">'
        f'<div style="font-size:11px;color:#64748b;font-weight:700;margin-bottom:4px;">{label}</div>'
        f'<div style="font-size:16px;font-weight:900;color:{color};word-break:keep-all;">{value}</div>'
        f'<div style="font-size:12px;color:#94a3b8;margin-top:3px;">{sub}</div>'
        f'</div>'
    )


def render_full_report(a):

    # ── 헤더 ──
    st.markdown(
        f'<div style="padding:4px 0 14px 0;">'
        f'<div style="font-size:20px;font-weight:900;color:#0f172a;line-height:1.3;">{a["name"]}</div>'
        f'<div style="font-size:13px;color:#94a3b8;margin-top:3px;">{a["symbol"]} · {a["market"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── 등급 배너 ──
    bg, fg, border = _grade_color(a["grade"])
    score = a["score"]
    score_reason = " · ".join(a["score_reasons"]) if a["score_reasons"] else "가산/감산 없음"
    st.markdown(
        f'<div style="background:{bg};border:2px solid {border};border-radius:16px;padding:18px;margin-bottom:18px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;">'
        f'<div><div style="font-size:11px;font-weight:700;color:{fg};letter-spacing:1px;margin-bottom:2px;">종합 등급</div>'
        f'<div style="font-size:30px;font-weight:900;color:{fg};line-height:1.1;">{a["grade"]}</div></div>'
        f'<div style="text-align:right;"><div style="font-size:11px;font-weight:700;color:{fg};letter-spacing:1px;margin-bottom:2px;">종합 점수</div>'
        f'<div style="font-size:30px;font-weight:900;color:{fg};line-height:1.1;">{score}점</div></div>'
        f'</div>'
        f'<div style="font-size:12px;color:{fg};opacity:0.85;border-top:1px solid {border};padding-top:10px;line-height:1.6;">{score_reason}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if a["flags"]:
        st.success(" | ".join(a["flags"]))

    # ── 핵심 수치 2×2 ──
    st.markdown("### 📌 핵심 수치")
    pct = a["pct_change"]
    pct_arrow = "▲" if pct >= 0 else "▼"
    pct_color = "#16a34a" if pct >= 0 else "#dc2626"
    roe = a["quality_result"].get("roe")
    roe_str = f"{roe*100:.2f}%" if roe is not None else "N/A"
    pbr_str = fmt_mul(a["pbr_stats"].get("current_pbr")) if a["pbr_stats"].get("available") else "N/A"

    st.markdown(
        _grid2([
            ("현재 주가", fmt_krw(a["current_price"]),
             f'<span style="color:{pct_color};font-weight:700;">{pct_arrow} {abs(pct):.2f}%</span>',
             "#fff", "#e2e8f0", "#0f172a"),
            ("현재 PBR", pbr_str,
             f"백분위 {fmt_pct(a['pbr_stats'].get('percentile'))}",
             "#fff", "#e2e8f0", "#0f172a"),
            ("ROE", roe_str,
             f"시장 백분위 {fmt_pct(a['quality_result'].get('roe_percentile'))}",
             "#fff", "#e2e8f0", "#0f172a"),
            ("MDD (1년)", fmt_pct(a["mdd"]),
             "고점 대비 최대 낙폭",
             "#fff5f5", "#fecaca", "#dc2626"),
        ]),
        unsafe_allow_html=True,
    )

    # ── 분석 카드 ──
    st.markdown("### 📚 분석 카드")

    if a["pbr_stats"].get("available"):
        val_desc = (
            f"평균 PBR {fmt_mul(a['pbr_stats'].get('mean_pbr'))}  ·  "
            f"Z-score {fmt_num(a['pbr_stats'].get('zscore'), 2)}  ·  "
            f"백분위 {fmt_pct(a['pbr_stats'].get('percentile'))}\n"
            f"표본 {a['pbr_stats'].get('sample_months')}개월 ({a['pbr_stats'].get('sample_grade')})"
        )
        zscore = a["pbr_stats"].get("zscore")
        zscore_str = fmt_num(zscore, 2) if zscore is not None else "N/A"
        card("📊 Valuation",
             f"PBR {fmt_mul(a['pbr_stats'].get('current_pbr'))}  ·  Z {zscore_str}",
             val_desc,
             tooltip="Z-score ≤ −1 : 역사적 저평가 / ≥ +1 : 고평가. 백분위 낮을수록 과거 대비 저렴.")
    else:
        card("📊 Valuation", "N/A", f"분석 불가: {a['pbr_stats'].get('reason', '')}")

    card(
        "🏅 Quality (ROE)", roe_str,
        (
            f"시장 내 ROE 백분위 {fmt_pct(a['quality_result'].get('roe_percentile'))}  ·  "
            f"점수 {a['quality_result'].get('score', 0)}점"
            if a["quality_result"].get("available")
            else f"분석 불가: {a['quality_result'].get('reason', '')}"
        ),
        tooltip="ROE = 당기순이익 ÷ 자기자본. 70백분위↑ 우량 / 90백분위↑ 최우량.",
    )

    trend_state = "정배열 📈" if (a["ma20"] > a["ma60"] > a["ma120"]) else "혼조 / 역배열 📉"
    trend_desc = (
        f"MA20  {fmt_krw(a['ma20'])}\n"
        f"MA60  {fmt_krw(a['ma60'])}\n"
        f"MA120 {fmt_krw(a['ma120'])}"
    )
    card("📐 추세", trend_state, trend_desc,
         tooltip="MA20 > MA60 > MA120 정배열 → 단·중·장기 추세 모두 상승 방향.")

    card("⚡ 모멘텀", f"RSI {fmt_num(a['rsi'])}", a["macd_comment"],
         tooltip="RSI 70↑ 과매수 / 30↓ 과매도. MACD > 시그널선이면 단기 모멘텀 유효.")

    vol_text = fmt_num(a["vol_ratio"], 2) + "배" if a["vol_ratio"] is not None else "N/A"
    card("📦 거래량", vol_text, a["volume_comment"],
         tooltip="현재 거래량 ÷ 20일 평균. 1.5배↑ 강한 수급 / 0.7배↓ 관망세.")

    # ── 지지/저항 ──
    st.markdown("### 📍 지지 / 저항")
    st.markdown(
        _grid2([
            ("1차 지지", fmt_krw(a["support_1"]), "", "#f0fdf4", "#86efac", "#166534"),
            ("2차 지지", fmt_krw(a["support_2"]), "", "#f0fdf4", "#86efac", "#166534"),
            ("1차 저항", fmt_krw(a["resistance_1"]), "", "#fef2f2", "#fca5a5", "#991b1b"),
            ("2차 저항", fmt_krw(a["resistance_2"]), "", "#fef2f2", "#fca5a5", "#991b1b"),
        ]) +
        _single_box("52주 고가", fmt_krw(a["high_52"])),
        unsafe_allow_html=True,
    )

    # ── 관심 구간 ──
    st.markdown("### 🎯 관심 구간")
    st.markdown(
        _grid2([
            ("1차 관심\nMA20 단기 눌림목",
             f"{fmt_krw(a['zone1_low'])} ~ {fmt_krw(a['zone1_high'])}",
             "", "#eff6ff", "#93c5fd", "#1e40af"),
            ("2차 보수\nMA60 보수적 재확인",
             f"{fmt_krw(a['zone2_low'])} ~ {fmt_krw(a['zone2_high'])}",
             "", "#f5f3ff", "#c4b5fd", "#5b21b6"),
        ]),
        unsafe_allow_html=True,
    )

    # ── 투자 전략 ──
    st.markdown("### 🧭 투자 전략")
    card("단기 (1~2주)", "", a["short_strategy"])
    card("중기 (1~3개월)", "", a["mid_strategy"])

    # ── 시나리오 ──
    st.markdown("### ⚖️ 시나리오")
    st.markdown(
        f'<div style="background:#ecfdf5;border:1px solid #6ee7b7;border-radius:14px;padding:16px;margin-bottom:12px;">'
        f'<div style="font-weight:900;font-size:14px;color:#065f46;margin-bottom:8px;">🟢 강세 시나리오</div>'
        f'<div style="font-size:14px;color:#065f46;line-height:1.8;">{a["bull_scenario"]}</div>'
        f'</div>'
        f'<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:14px;padding:16px;margin-bottom:20px;">'
        f'<div style="font-weight:900;font-size:14px;color:#991b1b;margin-bottom:8px;">🔴 약세 시나리오</div>'
        f'<div style="font-size:14px;color:#991b1b;line-height:1.8;">{a["bear_scenario"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
