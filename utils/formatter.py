# utils/formatter.py

def format_telegram_message(data: dict) -> str:
    symbol = data.get("symbol", "N/A")
    profile = data.get("profile", {})
    ratios = data.get("ratios_ttm", {})
    dcf = data.get("dcf", {})

    name = profile.get("companyName", symbol)
    price = profile.get("price", "N/A")
    dcf_value = dcf.get("equityValuePerShare", "N/A")

    # 주요 재무 비율
    roe = round(ratios.get("returnOnEquityTTM", 0) * 100, 2)
    roic = round(ratios.get("returnOnInvestedCapitalTTM", 0) * 100, 2)
    net_margin = round(ratios.get("netProfitMarginTTM", 0) * 100, 2)
    current_ratio = round(ratios.get("currentRatioTTM", 0), 2)
    debt_to_equity = round(ratios.get("debtToEquityRatioTTM", 0), 2)
    dividend_yield = round(ratios.get("dividendYieldTTM", 0) * 100, 2)
    per = round(ratios.get("priceToEarningsRatioTTM", 0), 2)
    pbr = round(ratios.get("priceToBookRatioTTM", 0), 2)
    ev_ebitda = round(ratios.get("enterpriseValueMultipleTTM", 0), 2)

    # DCF 저평가율
    try:
        dcf_gap = ((dcf_value - price) / price) * 100
        dcf_gap = round(dcf_gap, 2)
    except:
        dcf_gap = "N/A"

    # 📦 메시지 포맷
    message = f"""
📈 *{name}* ({symbol})

💵 *현재가*: ${price}
📉 *DCF 가치*: ${dcf_value} ({'저평가' if isinstance(dcf_gap, float) and dcf_gap > 0 else '고평가'})

📊 *수익성 지표*:
- ROE: {roe}%
- ROIC: {roic}%
- 순이익률: {net_margin}%

🧾 *재무 안정성*:
- 유동비율: {current_ratio}
- 부채비율: {debt_to_equity}

📈 *밸류에이션*:
- PER: {per}
- PBR: {pbr}
- EV/EBITDA: {ev_ebitda}

💸 *주주환원*:
- 배당수익률: {dividend_yield}%

📝 *DCF 분석*:
- DCF 가치 대비 차이: {dcf_gap}%
    """.strip()

    return message

def format_dividend_growth_message(stocks: list) -> str:
    if not stocks:
        return "💸 최근 1년간 안정적 배당 기록을 가진 종목이 없습니다."

    message = "💸 *최근 1년간 안정적 배당 성장주*\n\n"
    for stock in stocks:
        message += (f"🔹 *{stock['symbol']}*\n"
                    f" - 배당수익률: {stock['yield']}%\n"
                    f" - 지급주기: {stock['frequency'].capitalize()}\n"
                    f" - 최근 공시일: {stock['declaration_date']}\n"
                    f" - 배당금: ${stock['dividend']}\n\n")
    return message.strip()