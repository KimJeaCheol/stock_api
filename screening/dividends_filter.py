
import datetime

from utils.fmp_api import get_dividends_calendar


async def fetch_dividend_growth_stocks(min_yield: float = 3.0, days: int = 365):
    today = datetime.date.today()
    from_date = (today - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    data = await get_dividends_calendar(from_date, to_date)
    if not data:
        return []

    filtered = []
    for item in data:
        yield_rate = item.get('yield', 0)
        frequency = item.get('frequency', '').lower()

        # 배당 수익률, 지급 빈도 필터링
        if yield_rate >= min_yield and frequency in ('quarterly', 'annual', 'semi-annual'):
            filtered.append({
                "symbol": item['symbol'],
                "yield": yield_rate,
                "frequency": frequency,
                "dividend": item.get('dividend', 0),
                "declaration_date": item.get('date')
            })

    return filtered
