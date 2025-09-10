import datetime
import logging

from utils.fmp_api import get_economic_indicator, get_treasury_rates
from utils.notifier import notify_telegram

logger = logging.getLogger(__name__)

async def run_treasury_monitor_pipeline():
    today = datetime.date.today()
    from_date = (today - datetime.timedelta(days=90)).strftime("%Y-%m-%d")  # 90일 (3개월)
    to_date = today.strftime("%Y-%m-%d")

    treasury_data = await get_treasury_rates(from_date, to_date)

    if not treasury_data:
        await notify_telegram("⚠️ Treasury Rates 데이터 수집 실패.")
        return

    # 가장 최근 데이터
    latest = treasury_data[-1]
    message = (
        "💰 *미국 국채 금리 모니터링*\n\n"
        f"📅 날짜: {latest['date']}\n"
        f"• 1Y: {latest.get('year1', 'N/A')}%\n"
        f"• 2Y: {latest.get('year2', 'N/A')}%\n"
        f"• 5Y: {latest.get('year5', 'N/A')}%\n"
        f"• 10Y: {latest.get('year10', 'N/A')}%\n"
        f"• 30Y: {latest.get('year30', 'N/A')}%"
    )

    await notify_telegram(message)

async def run_economic_monitor_pipeline():
    today = datetime.date.today()
    from_date = (today - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    indicators = {
        "GDPreal": "📊 *GDP 성장률*",
        "unemploymentRate": "👥 *실업률*",
        "CPIinflationRate": "🔥 *인플레이션율*",
        "federalFunds": "🏦 *연방기금금리*",
        "smoothedUSRecessionProbabilities": "📉 *경기 침체 확률*",
        "retailSales": "🛍️ *소매 판매*",
        "initialClaims": "🧾 *신규 실업수당 청구 건수*",
    }

    message = "🌍 *주요 경제지표 모니터링*\n\n"

    for name, label in indicators.items():
        try:
            data = await get_economic_indicator(name, from_date, to_date)
            if not data:
                message += f"{label}: 데이터 없음\n"
                continue

            latest = data[-1]  # 가장 최근 데이터
            value = latest.get("value", "N/A")
            date = latest.get("date", "N/A")

            # 포맷: 실업률, GDP, 인플레이션은 % 표시
            if name in ["GDPreal", "unemploymentRate", "CPIinflationRate", "smoothedUSRecessionProbabilities"]:
                value = f"{value}%"

            message += f"{label}: {value} (발표일: {date})\n"

        except Exception as e:
            message += f"{label}: 데이터 조회 실패 ({str(e)})\n"

    await notify_telegram(message)
    
async def get_latest_economic_indicators():
    indicators = {
        "GDP": "GDP Growth",
        "unemploymentRate": "Unemployment Rate",
        "inflationRate": "Inflation Rate",
        "federalFunds": "Federal Funds Rate",
        "smoothedUSRecessionProbabilities": "Recession Probability",
    }
    summary = {}
    today = datetime.date.today()
    from_date = (today - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    for name, label in indicators.items():
        data = await get_economic_indicator(name, from_date, to_date)
        if data:
            latest = data[-1]
            value = latest.get("value", "N/A")
            if name in ["GDPreal", "unemploymentRate", "CPIinflationRate", "smoothedUSRecessionProbabilities"]:
                value = f"{value}%"
            summary[label] = f"{value} (발표일: {latest.get('date', 'N/A')})"
        else:
            summary[label] = "데이터 없음"

    return summary
    