# utils/fmp_api.py
import logging

import aiohttp

from app.core.config import settings

logger = logging.getLogger(__name__)


async def call_fmp_api(url: str, params: dict = None, timeout: int = 10):
    logger.info(f"📡 API 요청 시작: {url}")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, timeout=timeout) as response:
                response.raise_for_status()
                logger.info(f"✅ API 요청상태 코드: {response.status}")
                return await response.json()
        except Exception as e:
            raise RuntimeError(f"API 호출 실패: {url} - {e}")

async def get_company_profile(symbol: str):
    url = f"{settings.FMP_BASE_URL}/stable/profile"
    params = {"symbol": symbol, "apikey": settings.API_KEY}
    return await call_fmp_api(url, params)

async def get_ratios_ttm(symbol: str):
    url = f"{settings.FMP_BASE_URL}/stable/ratios-ttm"
    params = {"symbol": symbol, "apikey": settings.API_KEY}
    return await call_fmp_api(url, params)

async def get_ratios(symbol: str):
    url = f"{settings.FMP_BASE_URL}/stable/ratios"
    params = {"symbol": symbol, "apikey": settings.API_KEY}
    return await call_fmp_api(url, params)

async def get_key_metrics_ttm(symbol: str):
    url = f"{settings.FMP_BASE_URL}/stable/key-metrics-ttm"
    params = {"symbol": symbol, "apikey": settings.API_KEY}
    return await call_fmp_api(url, params)

async def get_custom_dcf_valuation(symbol: str):
    url = f"{settings.FMP_BASE_URL}/stable/custom-discounted-cash-flow"
    params = {"symbol": symbol, "apikey": settings.API_KEY}
    return await call_fmp_api(url, params)

async def get_ratings_snapshot(symbol: str):
    url = f"{settings.FMP_BASE_URL}/stable/ratings-snapshot"
    params = {"symbol": symbol, "apikey": settings.API_KEY}
    return await call_fmp_api(url, params)

async def get_financial_scores(symbol: str):
    url = f"{settings.FMP_BASE_URL}/stable/financial-scores"
    params = {"symbol": symbol, "apikey": settings.API_KEY}
    return await call_fmp_api(url, params)

async def get_income_statement(symbol: str):
    url = f"{settings.FMP_BASE_URL}/stable/income-statement"
    params = {"symbol": symbol, "apikey": settings.API_KEY}
    return await call_fmp_api(url, params)

async def get_balance_sheet_statement(symbol: str):
    url = f"{settings.FMP_BASE_URL}/stable/balance-sheet-statement"
    params = {"symbol": symbol, "apikey": settings.API_KEY}
    return await call_fmp_api(url, params)

async def get_cash_flow_statement(symbol: str):
    url = f"{settings.FMP_BASE_URL}/stable/cash-flow-statement"
    params = {"symbol": symbol, "apikey": settings.API_KEY}
    return await call_fmp_api(url, params)

async def get_company_screener(filters: dict):
    url = f"{settings.FMP_BASE_URL}/stable/company-screener"
    params = filters.copy()
    params["apikey"] = settings.API_KEY
    return await call_fmp_api(url, params)

async def get_dividends_calendar(from_date: str, to_date: str):
    url = f"{settings.FMP_BASE_URL}/stable/dividends-calendar"
    params = {
        "from": from_date,
        "to": to_date,
        "apikey": settings.API_KEY
    }
    return await call_fmp_api(url, params)

async def get_treasury_rates(from_date: str, to_date: str):
    url = f"{settings.FMP_BASE_URL}/stable/treasury-rates"
    params = {
        "from": from_date,
        "to": to_date,
        "apikey": settings.API_KEY
    }
    return await call_fmp_api(url, params)

async def get_economic_indicator(indicator_name: str, from_date: str = None, to_date: str = None):
    url = f"{settings.FMP_BASE_URL}/stable/economic-indicators"
    params = {
        "name": indicator_name,
        "apikey": settings.API_KEY
    }
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    return await call_fmp_api(url, params)

async def get_stock_quote(symbol: str):
    logger.info(f"📡 포트폴리오 심볼정보: {symbol}")
    url = f"{settings.FMP_BASE_URL}/stable/quote"
    params = {
        "symbol": symbol,
        "apikey": settings.API_KEY
    }
    try:
        data = await call_fmp_api(url, params)
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        else:
            return {}  # 안전하게 빈 dict 리턴
    except Exception as e:
        # 로깅 추가
        logger.error(f"get_stock_quote 실패: {symbol} → {e}")
        return {}
