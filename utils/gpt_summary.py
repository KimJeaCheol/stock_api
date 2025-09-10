# utils/gpt_summary.py
from openai import OpenAI

from app.core.config import settings

# OpenAI Client 초기화
client = OpenAI(api_key=settings.OPENAI_API_KEY)

def generate_prompt(data: dict) -> str:
    profile = data.get("profile", {})
    ratios = data.get("ratios", {})
    ratios_ttm = data.get("ratios_ttm", {})
    dcf = data.get("dcf", {})
    key_metrics = data.get("key_metrics_ttm", {})
    income = data.get("income_statement", {})
    cash = data.get("cash_flow", {})
    balance = data.get("balance_sheet", {})

    name = profile.get("companyName", "기업명 미확인")
    price = profile.get("price", 0)

    # 📊 실적 정보
    revenue = income.get("revenue", 0)
    net_income = income.get("netIncome", 0)
    eps = income.get("eps", 0)

    # 📈 수익성
    gross_margin = round(ratios_ttm.get("grossProfitMarginTTM", 0) * 100, 2)
    op_margin = round(ratios_ttm.get("operatingProfitMarginTTM", 0) * 100, 2)
    net_margin = round(ratios_ttm.get("netProfitMarginTTM", 0) * 100, 2)

    roe = round(key_metrics.get("returnOnEquityTTM", 0) * 100, 2)
    roic = round(key_metrics.get("returnOnInvestedCapitalTTM", 0) * 100, 2)

    # 📉 재무 건전성
    debt_equity = round(ratios_ttm.get("debtToEquityRatioTTM", 0), 2)
    current_ratio = round(ratios_ttm.get("currentRatioTTM", 0), 2)

    # 💵 현금흐름
    fcf = cash.get("freeCashFlow", 0)
    ocf = cash.get("operatingCashFlow", 0)
    capex = abs(cash.get("capitalExpenditure", 0))
    capex_ratio = round((capex / ocf) * 100, 2) if ocf else 0

    # 💰 주주환원
    dividend_yield = round(ratios_ttm.get("dividendYieldTTM", 0) * 100, 2)
    dividend_payout = round(ratios_ttm.get("dividendPayoutRatioTTM", 0) * 100, 2)

    # 🧮 가치 평가
    per = round(ratios_ttm.get("priceToEarningsRatioTTM", 0), 2)
    pbr = round(ratios_ttm.get("priceToBookRatioTTM", 0), 2)
    ev_ebitda = round(ratios_ttm.get("enterpriseValueMultipleTTM", 0), 2)

    dcf_value = dcf.get("equityValuePerShare", 0)
    dcf_gap = round((dcf_value - price) / price * 100, 2) if price else 0
    wacc = dcf.get("wacc", None)
    terminal = dcf.get("terminalValue", None)

    # 📝 프롬프트 구성
    prompt = f"""
📊 [{name}]의 재무 요약:

- 현재 주가: ${price} / EPS: ${eps}
- 매출: ${revenue:,} / 순이익: ${net_income:,} / 순이익률: {net_margin}%
- PER: {per} / PBR: {pbr} / EV/EBITDA: {ev_ebitda}
- ROE: {roe}%, ROIC: {roic}% / 영업이익률: {op_margin}%, 매출총이익률: {gross_margin}%
- 유동비율: {current_ratio}, 부채비율: {debt_equity}
- OCF: ${ocf:,} / FCF: ${fcf:,} / CapEx 비율: {capex_ratio}%
- 배당수익률: {dividend_yield}%, 배당성향: {dividend_payout}%
- DCF 가치: ${dcf_value} → 현재 주가 대비 {'저평가' if dcf_gap > 0 else '고평가'}
- 할인율(WACC): {wacc}%, Terminal Value: ${terminal:,}

이 정보를 바탕으로 [전문가의 시각으로 투자 매력도를 요약]해 주세요.
""".strip()

    return prompt

async def gpt_analyze(data: dict) -> str:
    prompt = generate_prompt(data)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # 최신 모델
            messages=[
                {"role": "system", "content": "당신은 뛰어난 금융 전문가이며, 주식 투자 매력도를 심도있게 분석합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"GPT 분석에 실패했습니다: {e}"
