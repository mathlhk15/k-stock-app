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


def _reliability_badge(level):
    """신뢰도 배지 HTML 반환. level: 'high'|'mid'|'low'|None"""
    cfg = {
        "high": ("#dcfce7", "#166534", "높음"),
        "mid":  ("#fef9c3", "#713f12", "보통"),
        "low":  ("#fee2e2", "#7f1d1d", "낮음"),
    }.get(level)
    if not cfg:
        return ""
    bg, fg, label = cfg
    return (
        f'<span style="background:{bg};color:{fg};font-size:11px;font-weight:700;'
        f'border-radius:6px;padding:2px 8px;margin-left:6px;">신뢰도: {label}</span>'
    )


def card(title, value, desc="", tooltip="", reliability=None):
    tooltip_html = ""
    if tooltip:
        tooltip_html = (
            f'<div style="background:#eff6ff;border-left:3px solid #3b82f6;border-radius:0 6px 6px 0;'
            f'padding:10px 14px;margin-top:10px;font-size:13px;color:#1e40af;line-height:1.7;">💡 {tooltip}</div>'
        )
    value_html = (
        f'<div style="font-weight:800;font-size:20px;color:#0f172a;line-height:1.3;margin-bottom:8px;">{value}</div>'
        if value else ""
    )
    badge = _reliability_badge(reliability)
    st.markdown(
        f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:16px;'
        f'margin-bottom:12px;box-shadow:0 1px 6px rgba(15,23,42,0.05);">'
        f'<div style="color:#64748b;font-size:12px;font-weight:700;margin-bottom:6px;">{title}{badge}</div>'
        f'{value_html}'
        f'<div style="font-size:13px;color:#475569;line-height:1.7;white-space:pre-wrap;">{desc}</div>'
        f'{tooltip_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _grid2(items):
    cells = ""
    for label, value, sub, bg, border, color in items:
        cells += (
            f'<div style="background:{bg};border:1px solid {border};border-radius:12px;'
            f'padding:13px 11px;min-height:76px;">'
            f'<div style="font-size:11px;color:#64748b;font-weight:700;margin-bottom:4px;">{label}</div>'
            f'<div style="font-size:16px;font-weight:900;color:{color};word-break:keep-all;line-height:1.3;">{value}</div>'
            f'<div style="font-size:12px;color:#94a3b8;margin-top:3px;">{sub}</div>'
            f'</div>'
        )
    return f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:18px;">{cells}</div>'


def _single_box(label, value, sub="", bg="#f8fafc", border="#e2e8f0", color="#0f172a"):
    return (
        f'<div style="background:{bg};border:1px solid {border};border-radius:12px;'
        f'padding:13px 11px;margin-bottom:10px;">'
        f'<div style="font-size:11px;color:#64748b;font-weight:700;margin-bottom:4px;">{label}</div>'
        f'<div style="font-size:16px;font-weight:900;color:{color};word-break:keep-all;">{value}</div>'
        f'<div style="font-size:12px;color:#94a3b8;margin-top:3px;">{sub}</div>'
        f'</div>'
    )


def _pct_colored(v):
    """수익률 값을 색상 포함 문자열로 반환"""
    if v is None:
        return "N/A"
    color = "#16a34a" if v >= 0 else "#dc2626"
    arrow = "▲" if v >= 0 else "▼"
    return f'<span style="color:{color};font-weight:700;">{arrow} {abs(v):.2f}%</span>'


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
    pbr_str = fmt_mul(a["pbr_stats"].get("current_pbr")) if a["pbr_stats"].get("current_pbr") is not None else "N/A"

    # PEG
    sh = a.get("shareholder_result", {})
    peg = sh.get("peg")
    peg_str = f"PEG {fmt_num(peg, 2)}" if peg is not None else ""
    per = sh.get("per")
    per_str = f"PER {fmt_num(per, 1)}" if per is not None else "N/A"

    st.markdown(
        _grid2([
            ("현재 주가", fmt_krw(a["current_price"]),
             f'<span style="color:{pct_color};font-weight:700;">{pct_arrow} {abs(pct):.2f}%</span>',
             "#fff", "#e2e8f0", "#0f172a"),
            ("PBR  /  PER", f"{pbr_str}  /  {per_str}",
             f"PBR 백분위 {fmt_pct(a['pbr_stats'].get('percentile'))}",
             "#fff", "#e2e8f0", "#0f172a"),
            ("BPS  /  DPS",
             f"{fmt_krw(sh.get('bps'))}  /  {fmt_krw(sh.get('dps'))}",
             "주당순자산 / 주당배당금",
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

    # 1. Valuation
    pbr_stats = a["pbr_stats"]
    if pbr_stats.get("available"):
        zscore = pbr_stats.get("zscore")
        zscore_str = fmt_num(zscore, 2) if zscore is not None else "N/A"
        val_desc = (
            f"평균 PBR {fmt_mul(pbr_stats.get('mean_pbr'))}  ·  "
            f"Z-score {zscore_str}  ·  "
            f"백분위 {fmt_pct(pbr_stats.get('percentile'))}\n"
            f"표본 {pbr_stats.get('sample_months')}개월 ({pbr_stats.get('sample_grade')})"
        )
        pbr_source = pbr_stats.get("source", "")
        pbr_rel = "high" if "dart" in pbr_source else ("mid" if pbr_source else "low")
        card("📊 Valuation", f"PBR {pbr_str}  ·  Z {zscore_str}", val_desc,
             tooltip="Z-score ≤ −1 : 역사적 저평가 / ≥ +1 : 고평가. 백분위 낮을수록 과거 대비 저렴.",
             reliability=pbr_rel)
    elif pbr_stats.get("current_pbr") is not None:
        # Partial: 시계열 부족이지만 현재 PBR은 있음
        sample_months = pbr_stats.get("sample_months", 0)
        funda = a.get("funda_snapshot", {})
        bps_str = fmt_krw(funda.get("BPS")) if funda.get("BPS") else "N/A"
        val_desc = (
            f"시계열 데이터 부족 ({sample_months}개월) — Z-score 비교 불가\n"
            f"현재 PBR만 제공됩니다. BPS {bps_str}  ·  출처: {pbr_stats.get('source','N/A')}"
        )
        card("📊 Valuation", f"PBR {pbr_str}", val_desc,
             tooltip="시계열이 충분하지 않아 과거 평균 대비 비교는 불가합니다. 현재 PBR 수치만 참고하세요.",
             reliability="low")
    else:
        card("📊 Valuation", "N/A", f"분석 불가: {pbr_stats.get('reason', '')}")

    # 2. Quality
    q_source = a["quality_result"].get("reason", "")
    q_rel = "high" if "dart" in q_source else ("mid" if a["quality_result"].get("available") else "low")
    card(
        "🏅 Quality (ROE)", roe_str,
        (
            f"시장 내 ROE 백분위 {fmt_pct(a['quality_result'].get('roe_percentile'))}  ·  "
            f"점수 {a['quality_result'].get('score', 0)}점"
            if a["quality_result"].get("available")
            else f"분석 불가: {a['quality_result'].get('reason', '')}"
        ),
        tooltip="ROE = 당기순이익 ÷ 자기자본. 70백분위↑ 우량 / 90백분위↑ 최우량.",
        reliability=q_rel,
    )

    # 3. 주주환원
    if sh.get("available"):
        div_yield = sh.get("div_yield")
        dps = sh.get("dps")
        sh_lines = []
        if div_yield is not None:
            sh_lines.append(f"배당수익률  {fmt_pct(div_yield)}")
        if dps is not None:
            sh_lines.append(f"주당배당금  {fmt_krw(dps)}")
        if per is not None:
            sh_lines.append(f"PER  {fmt_num(per, 1)}배")
        if peg is not None:
            sh_lines.append(f"PEG  {fmt_num(peg, 2)}  (PER ÷ EPS성장률)")
        sh_rel = "high" if peg is not None else ("mid" if div_yield is not None else "low")
        card("💰 주주환원", fmt_pct(div_yield) if div_yield else "N/A",
             "\n".join(sh_lines),
             tooltip="PEG < 1이면 성장 대비 저평가. 배당수익률 3%↑이면 주주환원 우수.",
             reliability=sh_rel)

    # 4. 모멘텀
    mo = a.get("momentum_result", {})
    if mo.get("available"):
        from_high = mo.get("from_high")
        from_low = mo.get("from_low")
        ma200_gap = mo.get("ma200_gap")
        mo_lines = []
        if mo.get("r1m") is not None:  mo_lines.append(f"1개월  {_pct_colored(mo['r1m'])}")
        if mo.get("r3m") is not None:  mo_lines.append(f"3개월  {_pct_colored(mo['r3m'])}")
        if mo.get("r6m") is not None:  mo_lines.append(f"6개월  {_pct_colored(mo['r6m'])}")
        if mo.get("r12m") is not None: mo_lines.append(f"12개월  {_pct_colored(mo['r12m'])}")
        if ma200_gap is not None:      mo_lines.append(f"200MA 괴리  {_pct_colored(ma200_gap)}")
        if from_high is not None:      mo_lines.append(f"52주 고가 대비  {_pct_colored(from_high)}")
        if from_low is not None:       mo_lines.append(f"52주 저가 대비  {_pct_colored(from_low)}")
        r6m_val = f"{mo['r6m']:+.1f}%" if mo.get("r6m") is not None else "N/A"
        st.markdown(
            f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:16px;'
            f'margin-bottom:12px;box-shadow:0 1px 6px rgba(15,23,42,0.05);">'
            f'<div style="color:#64748b;font-size:12px;font-weight:700;margin-bottom:6px;">📈 Momentum</div>'
            f'<div style="font-weight:800;font-size:20px;color:#0f172a;margin-bottom:10px;">6M {r6m_val}</div>'
            f'<div style="font-size:13px;color:#475569;line-height:2.0;">{"<br>".join(mo_lines)}</div>'
            f'<div style="background:#eff6ff;border-left:3px solid #3b82f6;border-radius:0 6px 6px 0;'
            f'padding:10px 14px;margin-top:10px;font-size:13px;color:#1e40af;line-height:1.7;">'
            f'💡 6M↑ 강한 추세 확인 / 200MA 위이면 중장기 상승 국면</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # 5. 리스크
    ri = a.get("risk_result", {})
    if ri.get("available"):
        beta = ri.get("beta")
        vol = ri.get("vol_1y")
        sharpe = ri.get("sharpe")
        ri_lines = []
        if beta is not None:   ri_lines.append(f"Beta  {fmt_num(beta, 2)}  (시장 민감도)")
        if vol is not None:    ri_lines.append(f"연간 변동성  {fmt_num(vol, 1)}%")
        if sharpe is not None: ri_lines.append(f"Sharpe  {fmt_num(sharpe, 2)}  (위험 대비 수익)")
        if ri_lines:
            beta_str = fmt_num(beta, 2) if beta is not None else "N/A"
            ri_rel = "high" if beta is not None and sharpe is not None else "mid"
            card("⚠️ Risk", f"Beta {beta_str}", "\n".join(ri_lines),
                 tooltip="Beta > 1 : 시장보다 변동 큼 / Sharpe > 1 : 양호한 위험 대비 수익.",
                 reliability=ri_rel)

    # 볼린저밴드
    bb_pct  = a.get("bb_pct")
    bb_upper = a.get("bb_upper")
    bb_lower = a.get("bb_lower")
    bb_mid   = a.get("bb_mid")
    bb_width = a.get("bb_width")
    if bb_pct is not None:
        if bb_pct >= 100:
            bb_pos = "상단 돌파 🔴"
        elif bb_pct >= 80:
            bb_pos = "상단 근접 ⚠️"
        elif bb_pct <= 0:
            bb_pos = "하단 이탈 🟢"
        elif bb_pct <= 20:
            bb_pos = "하단 근접 👀"
        else:
            bb_pos = "밴드 내 중립"
        bb_desc = (
            f"상단  {fmt_krw(bb_upper)}\n"
            f"중간  {fmt_krw(bb_mid)}\n"
            f"하단  {fmt_krw(bb_lower)}\n"
            f"밴드폭  {fmt_num(bb_width, 1)}%  ·  위치  {fmt_num(bb_pct, 1)}%"
        )
        card("🎯 볼린저밴드", f"{bb_pos}  ({fmt_num(bb_pct,1)}%)",
             bb_desc,
             tooltip="밴드 위치 0~100%. 80%↑ 과매수 주의 / 20%↓ 과매도 반등 가능. 밴드폭 축소 후 확장 시 큰 움직임 예고.",
             reliability="high")

    # 6. 추세
    trend_state = "정배열 📈" if (a["ma20"] > a["ma60"] > a["ma120"]) else "혼조 / 역배열 📉"
    trend_desc = (
        f"MA20  {fmt_krw(a['ma20'])}\n"
        f"MA60  {fmt_krw(a['ma60'])}\n"
        f"MA120 {fmt_krw(a['ma120'])}"
    )
    card("📐 추세", trend_state, trend_desc,
         tooltip="MA20 > MA60 > MA120 정배열 → 단·중·장기 추세 모두 상승 방향.",
         reliability="high")

    # 7. 모멘텀 기술
    card("⚡ 모멘텀 (기술적)", f"RSI {fmt_num(a['rsi'])}", a["macd_comment"],
         tooltip="RSI 70↑ 과매수 / 30↓ 과매도. MACD > 시그널선이면 단기 모멘텀 유효.",
         reliability="high")

    # 8. 거래량
    vol_text = fmt_num(a["vol_ratio"], 2) + "배" if a["vol_ratio"] is not None else "N/A"
    card("📦 거래량", vol_text, a["volume_comment"],
         tooltip="현재 거래량 ÷ 20일 평균. 1.5배↑ 강한 수급 / 0.7배↓ 관망세.",
         reliability="high")

    # ── 지지/저항 ──
    st.markdown("### 📍 지지 / 저항")
    st.markdown(
        _grid2([
            ("1차 지지", fmt_krw(a["support_1"]), "", "#f0fdf4", "#86efac", "#166534"),
            ("2차 지지", fmt_krw(a["support_2"]), "", "#f0fdf4", "#86efac", "#166534"),
            ("1차 저항", fmt_krw(a["resistance_1"]), "", "#fef2f2", "#fca5a5", "#991b1b"),
            ("2차 저항", fmt_krw(a["resistance_2"]), "", "#fef2f2", "#fca5a5", "#991b1b"),
        ]) +
        _single_box("52주 고가", fmt_krw(a["high_52"]),
                    f"저가 {fmt_krw(a['low_52'])}  ·  현재가 위치 고가 대비 "
                    f"{fmt_pct(((a['current_price']/a['high_52'])-1)*100) if a['high_52'] else 'N/A'}"),
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
        f'<div style="background:#ecfdf5;border:1px solid #6ee7b7;border-radius:14px;'
        f'padding:16px;margin-bottom:12px;">'
        f'<div style="font-weight:900;font-size:14px;color:#065f46;margin-bottom:8px;">🟢 강세 시나리오</div>'
        f'<div style="font-size:14px;color:#065f46;line-height:1.8;">{a["bull_scenario"]}</div>'
        f'</div>'
        f'<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:14px;'
        f'padding:16px;margin-bottom:20px;">'
        f'<div style="font-weight:900;font-size:14px;color:#991b1b;margin-bottom:8px;">🔴 약세 시나리오</div>'
        f'<div style="font-size:14px;color:#991b1b;line-height:1.8;">{a["bear_scenario"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── 하단 출처 / 면책 고지 ──
    pbr_src = a["pbr_stats"].get("source", "N/A")
    q_src   = a["quality_result"].get("reason", "N/A")
    today   = __import__("datetime").date.today().strftime("%Y.%m.%d")
    st.markdown(
        f'''<div style="margin-top:24px;padding:14px 16px;background:#f8fafc;
                   border-top:1px solid #e2e8f0;border-radius:10px;
                   font-size:12px;color:#94a3b8;line-height:1.8;">
            <div style="font-weight:700;color:#64748b;margin-bottom:4px;">
                📋 데이터 출처 및 면책 고지
            </div>
            가격 데이터: FinanceDataReader (KRX 상장 종목)<br>
            PBR 시계열: {pbr_src} · ROE: {q_src}<br>
            배당/재무: DART OpenAPI (키 설정 시) → yfinance fallback<br>
            기술적 지표: 자체 계산 (MA·RSI·MACD·ATR·볼린저밴드)<br>
            기준일: {today}<br><br>
            <span style="color:#cbd5e1;">
            ⚠️ 본 화면은 정보 제공용이며, 투자 권유가 아닙니다.
            모든 투자 판단과 책임은 본인에게 있습니다.
            데이터는 지연되거나 부정확할 수 있습니다.
            </span>
        </div>''',
        unsafe_allow_html=True,
    )
