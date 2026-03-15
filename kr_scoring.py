def calculate_scores(price_df, pbr_stats):

    score = 0

    if pbr_stats.get("available"):

        z = pbr_stats["zscore"]

        if z <= -1.5:
            score += 40
        elif z <= -1.0:
            score += 30
        elif z <= -0.5:
            score += 20

    ma20 = price_df["MA20"].iloc[-1]
    ma60 = price_df["MA60"].iloc[-1]
    ma120 = price_df["MA120"].iloc[-1]

    if ma20 > ma60 > ma120:
        score += 10

    rsi = price_df["RSI"].iloc[-1]

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