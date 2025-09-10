# utils/scoring.py

def score_stock(data: dict) -> int:
    score = 0

    profile = data.get("profile", {})
    ratios = data.get("ratios_ttm", {})
    key_metrics = data.get("key_metrics_ttm", {})
    dcf = data.get("dcf", {})
    scores_data = data.get("scores", {})
    income = data.get("income_statement", {})
    cash = data.get("cash_flow", {})

    price = profile.get("price", 0)
    dcf_value = dcf.get("equityValuePerShare", 0)
    dcf_gap = ((dcf_value - price) / price) if price else 0

    roe = key_metrics.get("returnOnEquityTTM", 0)
    roic = key_metrics.get("returnOnInvestedCapitalTTM", 0)
    fcf = cash.get("freeCashFlow", 0)
    ocf = cash.get("operatingCashFlow", 0)
    capex = abs(cash.get("capitalExpenditure", 0))
    capex_ratio = (capex / ocf) if ocf else 0

    current_ratio = ratios.get("currentRatioTTM", 0)
    debt_to_equity = ratios.get("debtToEquityRatioTTM", 0)
    net_margin = ratios.get("netProfitMarginTTM", 0)
    dividend_yield = ratios.get("dividendYieldTTM", 0)
    per = ratios.get("priceToEarningsRatioTTM", 0)

    piotroski = scores_data.get("piotroskiScore", 0)
    altman_z = scores_data.get("altmanZScore", 0)

    # ✅ 1. 수익성 (최대 4점)
    if roe >= 0.2:
        score += 2
    elif roe >= 0.1:
        score += 1

    if roic >= 0.15:
        score += 2
    elif roic >= 0.1:
        score += 1

    # ✅ 2. 현금흐름과 재투자 (최대 3점)
    if fcf > 0:
        score += 1
    if capex_ratio <= 0.3:
        score += 1
    if ocf > 0 and fcf / ocf >= 0.7:
        score += 1

    # ✅ 3. 안정성 (최대 3점)
    if current_ratio >= 1.5:
        score += 1
    if debt_to_equity <= 1.0:
        score += 1
    if altman_z >= 3:
        score += 1

    # ✅ 4. 수익성 지표 (최대 2점)
    if net_margin >= 0.15:
        score += 2
    elif net_margin >= 0.08:
        score += 1

    # ✅ 5. 밸류에이션 (최대 2점)
    if dcf_gap >= 0.2:
        score += 2
    elif dcf_gap >= 0.1:
        score += 1

    # ✅ 6. 주주환원 (최대 2점)
    if dividend_yield >= 0.03:
        score += 2
    elif dividend_yield >= 0.015:
        score += 1

    # ✅ 7. 종합 스코어 (최대 1점)
    if piotroski >= 8:
        score += 1

    return score
