from utils.fmp_api import get_company_screener


async def fetch_candidates(filters: dict) -> list:
    response = await get_company_screener(filters)
    symbols = [item['symbol'] for item in response if "symbol" in item]
    return symbols