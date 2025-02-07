import asyncio
import logging

import aiohttp
from fastapi import APIRouter, HTTPException, Query

from app.core.config import load_strategy, save_strategy, settings
from app.tasks.tasks import (analyze_candlestick_patterns, analyze_trend,
                             backtest_strategy, generate_trade_signal,
                             manage_risk)

logger = logging.getLogger(__name__)
router = APIRouter()

async def call_api_async(url, params=None, timeout=10):
    conn = aiohttp.TCPConnector(limit=100)  # 최대 100개의 연결을 재사용
    async with aiohttp.ClientSession(connector=conn) as session:
        logger.info(f"Calling API: {url} with params: {params}")
        try:
            async with session.get(url, params=params, timeout=timeout) as response:
                response.raise_for_status()
                data = await response.json()
                logger.info(f"API call successful: {url}")
                logger.info(f"API call data: {data}")
                return data
        except aiohttp.ClientError as e:
            logger.error(f"API call failed: {url} - {e}")
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/sectors")
async def fetch_sectors():
    logger.info("Fetching sectors performance data")
    url = f"https://financialmodelingprep.com/api/v3/sectors-performance"
    data = await call_api_async(url, params={"apikey": settings.API_KEY})
    logger.info(f"Sectors data retrieved: {len(data)} items")
    return data

@router.get("/stocks")
async def fetch_financial_screened_stocks(
    market_cap_more_than: float = Query(None),
    market_cap_less_than: float = Query(None),
    price_more_than: float = Query(None),
    price_less_than: float = Query(None),
    beta_more_than: float = Query(None),
    beta_less_than: float = Query(None),
    volume_more_than: float = Query(None),
    volume_less_than: float = Query(None),
    dividend_more_than: float = Query(None),
    dividend_less_than: float = Query(None),
    is_etf: bool = Query(None),
    is_fund: bool = Query(None),
    is_actively_trading: bool = Query(None),
    sector: str = Query(None),
    industry: str = Query(None),
    country: str = Query(None),
    exchange: str = Query(None),
    limit: int = Query(None)
):
    logger.info("Fetching financial screened stocks with provided criteria")
    url = f"https://financialmodelingprep.com/api/v3/stock-screener"
    params = {
        'apikey': settings.API_KEY,
        'marketCapMoreThan': market_cap_more_than,
        'marketCapLessThan': market_cap_less_than,
        'priceMoreThan': price_more_than,
        'priceLessThan': price_less_than,
        'betaMoreThan': beta_more_than,
        'betaLessThan': beta_less_than,
        'volumeMoreThan': volume_more_than,
        'volumeLessThan': volume_less_than,
        'dividendMoreThan': dividend_more_than,
        'dividendLessThan': dividend_less_than,
        'isEtf': is_etf,
        'isFund': is_fund,
        'isActivelyTrading': is_actively_trading,
        'sector': sector,
        'industry': industry,
        'country': country,
        'exchange': exchange,
        'limit': limit
    }

    filtered_params = {k: v for k, v in params.items() if v is not None}
    data = await call_api_async(url, filtered_params)
    logger.info(f"Financial screened stocks retrieved: {len(data)} items")
    return data

@router.get("/fluctuations")
async def calculate_fluctuations(ticker: str, period: str = '6mo'):
    logger.info(f"Calculating fluctuations for {ticker} over {period} period")
    try:
        loop = asyncio.get_event_loop()
        stock_data = await loop.run_in_executor(None, yf.download, ticker, period)
        stock_data.reset_index(inplace=True)
        stock_data['Date'] = stock_data['Date'].dt.strftime('%Y-%m-%d')
        fluctuations = {
            'dates': stock_data['Date'].tolist(),
            'open': stock_data['Open'].tolist(),
            'high': stock_data['High'].tolist(),
            'low': stock_data['Low'].tolist(),
            'prices': stock_data['Close'].tolist(),
            'volumes': stock_data['Volume'].tolist()
        }
        logger.info(f"Fluctuations calculated for {ticker}")
        return fluctuations
    except Exception as e:
        logger.error(f"Error calculating fluctuations for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def fetch_quote_data_async(symbol, session):
    logger.info(f"Fetching quote data asynchronously for {symbol}")
    url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={settings.API_KEY}"
    async with session.get(url) as response:
        data = await response.json()
        logger.info(f"Retrieved quote data for {symbol}")
        return data

@router.get("/quotes")
async def fetch_all_quotes(symbols: list):
    logger.info(f"Fetching quotes for symbols: {symbols}")
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_quote_data_async(symbol, session) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        logger.info(f"Retrieved quotes for {len(results)} symbols")
        return results

@router.get("/price_eps")
async def fetch_price_and_eps(symbol: str):
    logger.info(f"Fetching price and EPS for {symbol}")
    url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}"
    data = await call_api_async(url, params={"apikey": settings.API_KEY})
    logger.info(f"Retrieved price and EPS for {symbol}")
    return data

@router.get("/patterns/{symbol}")
async def get_candlestick_patterns(symbol: str):
    logger.info(f"Starting candlestick pattern analysis for {symbol}")
    task = analyze_candlestick_patterns.delay(symbol)  # 이 부분이 핵심입니다.
    logger.info(f"Candlestick pattern analysis task ID: {task.id}")
    return {"task_id": task.id, "message": "Pattern analysis started"}

@router.get("/trend/{symbol}")
async def get_trend_analysis(symbol: str):
    task = analyze_trend.delay(symbol)
    return {"task_id": task.id, "message": "Trend analysis started"}

@router.get("/signal/{symbol}")
async def get_trade_signal(symbol: str):
    task = generate_trade_signal.delay(symbol)
    return {"task_id": task.id, "message": "Trade signal generation started"}

@router.post("/backtest/{symbol}")
async def run_backtest(symbol: str, strategy_params: dict):
    task = backtest_strategy.delay(symbol, strategy_params)
    return {"task_id": task.id, "message": "Backtest started"}

router.post("/strategy/{user_id}")
async def save_user_strategy(user_id: str, strategy: dict):
    save_strategy(user_id, strategy)
    return {"message": "Strategy saved successfully"}

@router.get("/strategy/{user_id}")
async def get_user_strategy(user_id: str):
    strategy = load_strategy(user_id)
    return {"strategy": strategy}

@router.post("/risk/{symbol}")
async def manage_risk_for_symbol(symbol: str, risk_params: dict):
    task = manage_risk.delay(symbol, risk_params)
    return {"task_id": task.id, "message": "Risk management started"}