def calculate_scores(price_df, pbr_stats):
    score = 0

    # PBR 모듈
    if pbr_stats.get("available"):
        z = pbr_stats.get("zscore")
        if z is not None:
            if z <= -1.5:
                score += 40
            elif z <= -1.0:
                score += 30
            elif z <= -0.5:
                score += 20
            elif z >= 1.5:
                score -= 40
            elif z >= 1.0:
                score -= 20

    # 기술 점수
    ma20 = price_df["MA20"].iloc[-1] if "MA20" in price_df.columns else None
    ma60 = price_df["MA60"].iloc[-1] if "MA60" in price_df.columns else None
    ma120 = price_df["MA120"].iloc[-1] if "MA120" in price_df.columns else None

    if ma20 is not None and ma60 is not None and ma120 is not None:
        if not any(map(lambda x: x != x, [ma20, ma60, ma120])):
            if ma20 > ma60 > ma120:
                score += 10

    rsi = price_df["RSI"].iloc[-1] if "RSI" in price_df.columns else None
    if rsi is not None and rsi == rsi:
        if rsi >= 50:
            score += 10

    if score >= 80:
        grade = "Strong Buy"
    elif score >= 65:
        grade = "Buy"
    elif score >= 50:
        grade = "Hold"
    elif score >= 35:
        grade = "Caution"
    else:
        grade = "Avoid"

    return {"score": score, "grade": grade}
