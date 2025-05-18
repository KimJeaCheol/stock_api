# app/api/stocks.py

import asyncio
import json
import os
from typing import Any, List, Optional, Union

import aiohttp
import matplotlib.pyplot as plt
import numpy as np
import valinvest
import yfinance as yf
from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, Query
from openai import OpenAI

from app.core.config import load_strategy, save_strategy, settings
from app.core.logging import logger  # 이미 설정된 logger import
from app.tasks.tasks import (analyze_candlestick_patterns, analyze_trend,
                             backtest_strategy, generate_trade_signal,
                             manage_risk)

router = APIRouter()

async def call_api_async(url: str, params: dict = {}, method: str = "GET", json_data: dict = None , timeout: int = 10):
    logger.info(f"📡 API 요청 시작: {method} {url}")
    logger.info(f"📦 PARAMS: {params}")
    if json_data:
        logger.info(f"📤 JSON BODY: {json_data}")

    try:
        async with aiohttp.ClientSession() as session:
            if method == "POST":
                async with session.post(url, params=params, json=json_data, timeout=timeout) as response:
                    logger.info(f"📬 응답 상태: {response.status}")
                    response.raise_for_status()
                    data = await response.json()
                    logger.info(f"📨 응답 데이터 요약: {str(data)[:300]}")  # 길이 제한
                    return data
            else:
                async with session.get(url, params=params, timeout=timeout) as response:
                    logger.info(f"📬 응답 상태: {response.status}")
                    response.raise_for_status()
                    data = await response.json()
                    logger.info(f"📨 응답 데이터 요약: {str(data)[:300]}")
                    return data
    except Exception as e:
        logger.error(f"[call_api_async] 호출 실패: {url} → {e}")
        return []


@router.get("/sectors")
async def fetch_sectors():
    logger.info("Fetching sectors performance data")
    url = f"{settings.FMP_BASE_URL}/api/v4/sectors-performance"
    data = await call_api_async(url, params={"apikey": settings.API_KEY})
    logger.info(f"Sectors data retrieved: {len(data)} items")
    return data

@router.get("/stocks")
async def fetch_financial_screened_stocks(
    market_cap_more_than: float = Query(None),
    market_cap_less_than: float = Query(None),
    sector: str = Query(None),
    industry: str = Query(None),
    beta_more_than: float = Query(None),
    beta_less_than: float = Query(None),
    price_more_than: float = Query(None),
    price_less_than: float = Query(None),
    dividend_more_than: float = Query(None),
    dividend_less_than: float = Query(None),
    volume_more_than: float = Query(None),
    volume_less_than: float = Query(None),
    exchange: str = Query(None),
    country: str = Query(None),
    is_etf: bool = Query(None),
    is_fund: bool = Query(None),
    is_actively_trading: bool = Query(None),
    limit: int = Query(None),
):
    logger.info("Fetching financial screened stocks with provided criteria")
    url = f"{settings.FMP_BASE_URL}/api/v3/stock-screener"
    params = {
        'apikey': settings.API_KEY,
        'marketCapMoreThan': market_cap_more_than,
        'marketCapLessThan': market_cap_less_than,
        'sector': sector,
        'industry': industry,
        'betaMoreThan': beta_more_than,
        'betaLessThan': beta_less_than,
        'priceMoreThan': price_more_than,
        'priceLessThan': price_less_than,
        'dividendMoreThan': dividend_more_than,
        'dividendLessThan': dividend_less_than,
        'volumeMoreThan': volume_more_than,
        'volumeLessThan': volume_less_than,
        'exchange': exchange,
        'country': country,
        'isEtf': is_etf,
        'isFund': is_fund,
        'isActivelyTrading': is_actively_trading,
        'limit': limit,
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
    url = f"{settings.FMP_BASE_URL}/api/v3/quote/{symbol}?apikey={settings.API_KEY}"
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
    url = f"{settings.FMP_BASE_URL}/stable/"
    params = {
    "apikey": settings.API_KEY,
    "symbol": symbol
            }
    data = await call_api_async(url, params)
    logger.info(f"Retrieved price and EPS for {symbol}")
    return data


@router.get("/tasks/result/{task_id}")
async def get_task_result(task_id: str):
    """Celery 작업 상태 조회"""
    result = AsyncResult(task_id)

    if result.status == "FAILURE":
        return {"task_id": task_id, "status": "FAILED", "error": result.result}

    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else "Processing...",
    }

@router.get("/patterns/{symbol}")
async def get_candlestick_patterns(symbol: str):
    task = analyze_candlestick_patterns.delay(symbol)
    return {"task_id": task.id, "message": "캔들 패턴 분석 시작"}

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

@router.post("/strategy/{user_id}")
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


@router.get("/stocks/top_gainers")
async def get_top_gainers():
    """
    당일 가장 많이 상승한 주식 목록을 조회합니다.
    
    :return: 상위 상승 주식 데이터
    """
    url = f"{settings.FMP_BASE_URL}/stable/biggest-gainers"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="상위 상승 주식 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Top Gainers 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Top Gainers 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/stocks/biggest_losers")
async def get_biggest_losers():
    """
    당일 가장 많이 하락한 주식 목록을 조회합니다.
    
    :return: 상위 하락 주식 데이터
    """
    url = f"{settings.FMP_BASE_URL}/stable/biggest-losers"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="상위 하락 주식 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Biggest Losers 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Biggest Losers 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/stocks/highest_volume")
async def get_highest_volume():
    """
    당일 거래량이 가장 높은 주식 목록을 조회합니다.
    
    :return: 거래량 상위 주식 데이터
    """
    url = f"{settings.FMP_BASE_URL}/stable/most-actives"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="거래량 상위 주식 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Highest Volume 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Highest Volume 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/stocks/quote/{symbol}")
async def get_stock_quote(symbol: str):
    """
    특정 주식의 실시간 시세 정보를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :return: 주식 시세 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/quote/{symbol}"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 주식 시세 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Stock Quote 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Stock Quote 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/stocks/sectors")
async def get_sectors_performance():
    """
    각 섹터(Sector)의 성과 데이터를 조회합니다.
    
    :return: 섹터 성과 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/sectors-performance"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="섹터 성과 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Sectors Performance 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Sectors Performance 데이터를 불러오는 중 오류가 발생했습니다.")



@router.get("/technical/{interval}/{indicator}/{symbol}/{period}")
async def get_technical_indicator(interval: str, indicator: str, symbol: str, period: int):
    """
    특정 주식의 기술적 지표 데이터를 조회합니다.
    
    :param interval: 시간 간격 (예: 1min, 5min, 15min, 30min, 1hour, 4hour)
    :param indicator: 기술적 지표 유형 (예: sma, ema, wma, dema, tema, williams, rsi, adx, standardDeviation)
    :param symbol: 주식 심볼 (예: AAPL)
    :param period: 분석 기간 (예: 10)
    :return: 기술적 지표 데이터
    """
    valid_intervals = ["1min", "5min", "15min", "30min", "1hour", "4hour"]
    valid_indicators = ["sma", "ema", "wma", "dema", "tema", "williams", "rsi", "adx", "standardDeviation"]

    if interval not in valid_intervals:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 시간 간격입니다. 사용 가능: {valid_intervals}")

    if indicator not in valid_indicators:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 기술적 지표입니다. 사용 가능: {valid_indicators}")

    url = f"{settings.FMP_BASE_URL}/api/v3/technical_indicator/{interval}/{symbol}"
    params = {"type": indicator, "period": period, "apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 {indicator} 지표 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Technical Indicator 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Technical Indicator 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/chart/intraday/{symbol}/{interval}")
async def get_intraday_chart(symbol: str, interval: str, from_date: str, to_date: str):
    """
    Intraday 차트 데이터를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :param interval: 시간 간격 (1min, 5min, 15min, 30min, 1hour, 4hour)
    :param from_date: 조회 시작 날짜 (YYYY-MM-DD 형식)
    :param to_date: 조회 종료 날짜 (YYYY-MM-DD 형식)
    :return: Intraday 차트 데이터
    """
    valid_intervals = ["1min", "5min", "15min", "30min", "1hour", "4hour"]

    # 유효한 interval 값 검증
    if interval not in valid_intervals:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 시간 간격입니다. 사용 가능: {valid_intervals}")

    url = f"{settings.FMP_BASE_URL}/api/v3/historical-chart/{interval}/{symbol}"
    params = {
        "from": from_date,
        "to": to_date,
        "apikey": settings.API_KEY
    }

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 Intraday 차트 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Intraday 차트 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Intraday 차트 데이터를 불러오는 중 오류가 발생했습니다.")


### 📌 차트 데이터 관련 API
@router.get("/chart/daily/{symbol}")
async def get_daily_chart(symbol: str, from_date: Optional[str] = None, to_date: Optional[str] = None):
    """
    특정 주식의 일일 차트 데이터를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :param from_date: 조회 시작 날짜 (선택, YYYY-MM-DD 형식)
    :param to_date: 조회 종료 날짜 (선택, YYYY-MM-DD 형식)
    :return: 일일 차트 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/historical-price-full/{symbol}"
    params = {"apikey": settings.API_KEY}

    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    try:
        data = await call_api_async(url, params)
        if not data or "historical" not in data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 일일 차트 데이터를 찾을 수 없습니다.")
        return data["historical"]

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Daily Chart 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Daily Chart 데이터를 불러오는 중 오류가 발생했습니다.")


### 📌 뉴스 관련 API

@router.get("/news/press-releases/{symbol}")
async def get_press_releases(symbol: str):
    """
    특정 주식의 최신 보도 자료(Press Releases) 데이터를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :return: 보도 자료 데이터 리스트
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/press-releases/{symbol}"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 보도 자료 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Press Releases 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Press Releases 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/news/stock")
async def get_stock_news(tickers: str, from_date: Optional[str] = None, to_date: Optional[str] = None, page: int = 1):
    """
    최신 주식 뉴스를 조회합니다.
    
    :param tickers: 조회할 주식 심볼 목록 (쉼표로 구분, 예: AAPL,FB)
    :param from_date: 조회 시작 날짜 (선택, YYYY-MM-DD 형식)
    :param to_date: 조회 종료 날짜 (선택, YYYY-MM-DD 형식)
    :param page: 페이지 번호 (기본값: 1)
    :return: 주식 뉴스 데이터 리스트
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/stock_news"
    params = {"tickers": tickers, "page": page, "apikey": settings.API_KEY}

    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="주식 뉴스 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Stock News 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Stock News 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/quote/full/{symbol}")
async def get_full_quote(symbol: str):
    """
    특정 주식의 전체 시세 정보를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :return: 전체 시세 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/quote/{symbol}"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 Full Quote 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Full Quote 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Full Quote 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/quote/order/{symbol}")
async def get_quote_order(symbol: str):
    """
    특정 주식의 간단한 시세 정보를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :return: 현재 가격, 거래량, 마지막 거래 가격
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/quote-order/{symbol}"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 Quote Order 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Quote Order 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Quote Order 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/quote/simple/{symbol}")
async def get_simple_quote(symbol: str):
    """
    특정 주식의 간단한 시세 정보를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :return: 가격, 변화량, 거래량 등의 기본 시세 정보
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/quote-short/{symbol}"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 Simple Quote 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Simple Quote 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Simple Quote 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/quote/live-full/{symbol}")
async def get_live_full_price(symbol: str):
    """
    특정 주식의 실시간 전체 시세 정보를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :return: 실시간 입찰가, 매도가, 거래량, 마지막 거래 가격
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/stock/full/real-time-price/{symbol}"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 실시간 Full Price 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Live Full Price 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Live Full Price 데이터를 불러오는 중 오류가 발생했습니다.")


### 📌 기업 정보 관련 API
@router.get("/company/profile/{symbol}")
async def get_company_profile(symbol: str):
    url = f"{settings.FMP_BASE_URL}/stable/profile"
    params = {"symbol": symbol, "apikey": settings.API_KEY}
    return await call_api_async(url, params)

@router.get("/company/screener")
async def get_stock_screener(
    market_cap_more_than: float = Query(None),
    market_cap_less_than: float = Query(None),
    sector: str = Query(None),
    industry: str = Query(None),
    beta_more_than: float = Query(None),
    beta_less_than: float = Query(None),
    price_more_than: float = Query(None),
    price_less_than: float = Query(None),
    dividend_more_than: float = Query(None),
    dividend_less_than: float = Query(None),
    volume_more_than: float = Query(None),
    volume_less_than: float = Query(None),
    exchange: str = Query(None),
    country: str = Query(None),
    is_etf: bool = Query(None),
    is_fund: bool = Query(None),
    is_actively_trading: bool = Query(None),
    limit: int = Query(None),
    includeAllShareClasses: bool = Query(None),
):
    """
    주식 스크리너 API - 다양한 조건으로 주식을 필터링합니다.
    
    :return: 필터링된 주식 목록
    """
    url = f"{settings.FMP_BASE_URL}/stable/company-screener"
    params = {
        'apikey': settings.API_KEY,
        'marketCapMoreThan': market_cap_more_than,
        'marketCapLessThan': market_cap_less_than,
        'sector': sector,
        'industry': industry,
        'betaMoreThan': beta_more_than,
        'betaLessThan': beta_less_than,
        'priceMoreThan': price_more_than,
        'priceLessThan': price_less_than,
        'dividendMoreThan': dividend_more_than,
        'dividendLessThan': dividend_less_than,
        'volumeMoreThan': volume_more_than,
        'volumeLessThan': volume_less_than,
        'exchange': exchange,
        'country': country,
        'isEtf': is_etf,
        'isFund': is_fund,
        'isActivelyTrading': is_actively_trading,
        'limit': limit,
        'includeAllShareClasses': includeAllShareClasses
    }

    filtered_params = {k: v for k, v in params.items() if v is not None}

    try:
        data = await call_api_async(url, filtered_params)
        if not data:
            raise HTTPException(status_code=404, detail="필터링된 주식을 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Stock Screener 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Stock Screener 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/company/grade/{symbol}")
async def get_stock_grade(symbol: str):
    """
    특정 주식의 애널리스트 평가 정보를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :return: 애널리스트 평가 정보
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/grade/{symbol}?apikey=ywVLzlNZQUBe3anS60CetWk2P1JXK2pO"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 평가 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Stock Grade 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Stock Grade 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/company/market-cap/{symbol}")
async def get_market_cap(symbol: str):
    """
    특정 주식의 시가총액 정보를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :return: 시가총액 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/market-capitalization/{symbol}"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 시가총액 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Market Cap 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Market Cap 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/company/historical-market-cap/{symbol}")
async def get_historical_market_cap(symbol: str, from_date: str, to_date: str, limit: int = 100):
    """
    특정 주식의 과거 시가총액 정보를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :param from_date: 조회 시작 날짜 (YYYY-MM-DD 형식)
    :param to_date: 조회 종료 날짜 (YYYY-MM-DD 형식)
    :param limit: 최대 조회 개수 (기본값: 100)
    :return: 과거 시가총액 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/historical-market-capitalization/{symbol}"
    params = {
        "from": from_date,
        "to": to_date,
        "limit": limit,
        "apikey": settings.API_KEY
    }

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 과거 시가총액 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Historical Market Cap 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Historical Market Cap 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/company/analyst-estimates/{symbol}")
async def get_analyst_estimates(symbol: str):
    """
    특정 주식의 애널리스트 수익 및 예상 수익 정보를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :return: 애널리스트 평가 정보
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/analyst-estimates/{symbol}"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 애널리스트 평가 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Analyst Estimates 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Analyst Estimates 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/company/analyst-recommendations/{symbol}")
async def get_analyst_recommendations(symbol: str):
    """
    특정 주식의 애널리스트 매수, 매도, 보유 추천 정보를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :return: 애널리스트 추천 정보
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/analyst-stock-recommendations/{symbol}"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 애널리스트 추천 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Analyst Recommendations 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Analyst Recommendations 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/company/logo/{symbol}")
def get_company_logo(symbol: str):
    """
    회사의 로고 이미지를 조회합니다.
    :param symbol: 주식 심볼 (예: AAPL)
    :return: 회사 로고 URL
    """
    url = f"{settings.FMP_BASE_URL}/image-stock/{symbol}.png"
    return {"logo_url": url}

@router.get("/company/peers/{symbol}")
async def get_stock_peers(symbol: str):
    """
    특정 주식과 유사한 피어 그룹(동종업계 경쟁사) 정보를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :return: 피어 그룹 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v4/stock_peers"
    params = {"symbol": symbol, "apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 피어 그룹 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Stock Peers 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Stock Peers 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/company/sectors")
async def get_available_sectors():
    """
    Financial Modeling Prep (FMP) 데이터베이스에서 제공하는 모든 섹터 목록을 조회합니다.
    
    :return: 섹터 목록 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/sectors-list"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="섹터 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Sectors 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Sectors 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/company/industries")
async def get_available_industries():
    """
    Financial Modeling Prep (FMP) 데이터베이스에서 제공하는 모든 산업(Industry) 목록을 조회합니다.
    
    :return: 산업 목록 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/industries-list"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="산업 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Industries 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Industries 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/market/index")
async def get_market_index():
    """
    주요 주식 시장 지수 데이터를 조회합니다. (예: S&P 500, 다우 존스, 나스닥)
    
    :return: 시장 지수 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/quotes/index"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="시장 지수 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Market Index 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Market Index 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/market/sector-pe-ratio")
async def get_sector_pe_ratio(date: str, exchange: str = "NYSE"):
    """
    각 섹터의 주가수익비율(PE Ratio) 데이터를 조회합니다.
    
    :return: 섹터별 PE 비율 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v4/sector_price_earning_ratio"
    params = {"date": date, "exchange": exchange, "apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="섹터 PE 비율 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Sector PE Ratio 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Sector PE Ratio 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/market/industry-pe-ratio")
async def get_industry_pe_ratio(date: str, exchange: str = "NYSE"):
    """
    각 산업(Industry)의 주가수익비율(PE Ratio) 데이터를 조회합니다.
    
    :param date: 조회 날짜 (YYYY-MM-DD 형식)
    :param exchange: 거래소 (기본값: NYSE)
    :return: 산업별 PE 비율 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v4/industry_price_earning_ratio"
    params = {"date": date, "exchange": exchange, "apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="산업 PE 비율 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Industry PE Ratio 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Industry PE Ratio 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/market/sector-performance")
async def get_sector_performance():
    """
    각 섹터(Sector)의 성과 데이터를 조회합니다.
    
    :return: 섹터 성과 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/sectors-performance"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="섹터 성과 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Sector Performance 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Sector Performance 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/market/sector-historical")
async def get_sector_historical_performance(from_date: str, to_date: str):
    """
    각 섹터(Sector)의 역사적인 성과 데이터를 조회합니다.
    
    :param from_date: 조회 시작 날짜 (YYYY-MM-DD 형식)
    :param to_date: 조회 종료 날짜 (YYYY-MM-DD 형식)
    :return: 섹터의 역사적 성과 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/historical-sectors-performance"
    params = {"from": from_date, "to": to_date, "apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="역사적 섹터 성과 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Sector Historical Performance 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Sector Historical Performance 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/constituents/sp500")
async def get_sp500_constituents():
    """
    S&P 500 지수에 포함된 모든 회사 목록을 조회합니다.
    
    :return: S&P 500 회사 목록
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/sp500_constituent"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="S&P 500 회사 목록을 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"S&P 500 Constituents 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="S&P 500 Constituents 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/constituents/nasdaq")
async def get_nasdaq_constituents():
    """
    Nasdaq 지수에 포함된 모든 회사 목록을 조회합니다.
    
    :return: Nasdaq 회사 목록
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/nasdaq_constituent"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="Nasdaq 회사 목록을 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Nasdaq Constituents 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Nasdaq Constituents 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/constituents/dowjones")
async def get_dowjones_constituents():
    """
    Dow Jones 지수에 포함된 모든 회사 목록을 조회합니다.
    
    :return: Dow Jones 회사 목록
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/dowjones_constituent"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="Dow Jones 회사 목록을 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Dow Jones Constituents 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Dow Jones Constituents 데이터를 불러오는 중 오류가 발생했습니다.")



@router.get("/economics/treasury-rates")
async def get_treasury_rates(from_date: str, to_date: str):
    """
    미국 재무부 국채(Treasury) 금리를 조회합니다.
    
    :param from_date: 조회 시작 날짜 (YYYY-MM-DD 형식)
    :param to_date: 조회 종료 날짜 (YYYY-MM-DD 형식)
    :return: 국채 금리 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v4/treasury"
    params = {"from": from_date, "to": to_date, "apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="국채 금리 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Treasury Rates 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Treasury Rates 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/economics/indicators")
async def get_economic_indicators(indicator_name: str, from_date: Optional[str] = None, to_date: Optional[str] = None):
    """
    경제 지표 데이터를 조회합니다.
    
    :param indicator_name: 조회할 경제 지표 이름 (예: GDP, inflationRate 등)
    :param from_date: 조회 시작 날짜 (선택, YYYY-MM-DD 형식)
    :param to_date: 조회 종료 날짜 (선택, YYYY-MM-DD 형식)
    :return: 경제 지표 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v4/economic"
    params = {"name": indicator_name, "apikey": settings.API_KEY}

    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{indicator_name} 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Economic Indicators 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Economic Indicators 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/economics/calendar")
async def get_economic_calendar(from_date: str, to_date: str):
    """
    경제 지표 발표 일정(캘린더)을 조회합니다.
    
    :param from_date: 조회 시작 날짜 (YYYY-MM-DD 형식)
    :param to_date: 조회 종료 날짜 (YYYY-MM-DD 형식)
    :return: 경제 발표 일정 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/economic_calendar"
    params = {"from": from_date, "to": to_date, "apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="경제 발표 일정을 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Economic Calendar 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Economic Calendar 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/economics/market-risk-premium")
async def get_market_risk_premium():
    """
    시장 위험 프리미엄(Market Risk Premium) 데이터를 조회합니다.
    
    :return: 시장 위험 프리미엄 데이터
    """
    url = f"{settings.FMP_BASE_URL}/api/v4/market_risk_premium"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="시장 위험 프리미엄 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Market Risk Premium 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Market Risk Premium 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/search/general")
async def search_general(query: str):
    """
    주식, 암호화폐, 외환, ETF 등 금융 상품을 심볼 또는 회사 이름으로 검색합니다.
    
    :param query: 검색어 (심볼 또는 회사 이름)
    :return: 검색 결과 리스트
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/search"
    params = {"query": query, "apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="검색 결과를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Search General 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Search General 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/search/ticker")
async def search_ticker(query: str, limit: int = 10, exchange: Optional[str] = None):
    """
    주식 및 ETF 심볼과 거래소 정보를 검색합니다.
    
    :param query: 검색어 (회사 이름 또는 심볼)
    :param limit: 검색 결과 개수 (기본값: 10)
    :param exchange: 거래소 (예: NASDAQ, NYSE)
    :return: 검색 결과 리스트
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/search-ticker"
    params = {"query": query, "limit": limit, "apikey": settings.API_KEY}

    if exchange:
        params["exchange"] = exchange

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="티커 검색 결과를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Search Ticker 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Search Ticker 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/search/name")
async def search_name(query: str, limit: int = 10, exchange: Optional[str] = None):
    """
    회사 이름으로 주식 및 ETF 심볼과 거래소 정보를 검색합니다.
    
    :param query: 검색어 (회사 이름)
    :param limit: 검색 결과 개수 (기본값: 10)
    :param exchange: 거래소 (예: NASDAQ, NYSE)
    :return: 검색 결과 리스트
    """
    url = f"{settings.FMP_BASE_URL}/api/v3/search-name"
    params = {"query": query, "limit": limit, "apikey": settings.API_KEY}

    if exchange:
        params["exchange"] = exchange

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="회사명 검색 결과를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Search Name 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Search Name 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/fscore")
async def get_valinvest(symbol: str):
    """
    피오스트로스키 점수는 3개 그룹으로 나뉜 9가지 기준을 기반으로 계산됩니다.

    수익성
    자산 수익률(현재 연도에 양수이면 1점, 그렇지 않으면 0점)
    영업 현금 흐름(현재 연도에 양수이면 1점, 그렇지 않으면 0점)
    자산수익률(ROA) 변화량(ROA가 전년 대비 당해연도에 높으면 1점, 그렇지 않으면 0점)
    발생액(현재 연도 영업 현금 흐름/총 자산이 ROA보다 높으면 1점, 그렇지 않으면 0점)
    레버리지, 유동성 및 자금원
    레버리지(장기) 비율 변화(올해 비율이 전년 대비 낮으면 1점, 그렇지 않으면 0점)
    유동자산비율 변화량 (당해년도가 전년대비 높으면 1점, 높지 않으면 0점)
    주식수 변동 (지난 1년간 신주 발행이 없는 경우 1점)
    운영 효율성
    매출총이익률 변화 (당해년도가 전년도에 비해 높으면 1점, 그렇지 않으면 0점)
    자산 회전율 변화량 (전년도 대비 당해년도가 높으면 1점, 그렇지 않으면 0점)
    이 소프트웨어는 F-점수의 대체 버전을 다음과 같이 계산합니다.

    성장
    순수익
    EBITDA
    주당순이익(EPS)
    수익성
    크로익
    로이씨(ROIC)
    부채
    EBITDA 커버율
    부채 보장
    시장 감수성
    베타
    투자
    주식매수
    """
    try:
            logger.info(f"Calculating F-Score for {symbol}")
            stock = valinvest.Fundamental(symbol, settings.API_KEY)
            fscore = stock.fscore()
            return {"symbol": symbol, "fscore": fscore}
    except Exception as e:
        logger.error(f"Failed to calculate F-Score for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="F-Score 계산 중 오류 발생")
    
def convert_numpy_values(data):
    """ numpy.int64, numpy.float64 데이터를 Python 기본 타입(int, float)으로 변환 """
    if isinstance(data, dict):
        return {k: convert_numpy_values(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_numpy_values(v) for v in data]
    elif isinstance(data, (np.integer, np.floating)):
        return data.item()
    else:
        return data

@router.get("/short_interest")
async def get_short_interest(symbol: str):
    """
    특정 주식의 공매도 관련 데이터 및 옵션 체인 정보를 조회하는 API 엔드포인트.

    :param symbol: 주식 심볼 (예: TSLA)
    :return: 공매도 관련 데이터 및 옵션 정보
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        print(json.dumps(info, indent=2))
        expiration_dates = ticker.options  # 옵션 만기일 목록

        if not expiration_dates:
            raise HTTPException(status_code=404, detail=f"No options data available for {symbol}")

        # 첫 번째 만기일의 옵션 체인 데이터 가져오기
        opt = ticker.option_chain(expiration_dates[0])

        # DataFrame 변환 (NaN, inf 값 처리 후 JSON 변환 가능 형태로)
        calls = opt.calls.fillna(0).replace([np.inf, -np.inf], 0).to_dict(orient="records")
        puts = opt.puts.fillna(0).replace([np.inf, -np.inf], 0).to_dict(orient="records")

        # NumPy 값 변환
        option_chain_data = {
            "calls": convert_numpy_values(calls),
            "puts": convert_numpy_values(puts)
        }

        short_interest_data = {
            "symbol": symbol,
            "floatShares": info.get("floatShares", "N/A"),
            "sharesOutstanding": info.get("sharesOutstanding", "N/A"),
            "impliedSharesOutstanding": info.get("impliedSharesOutstanding", "N/A"),
            "bookValue": info.get("bookValue", "N/A"),
            "priceToBook": info.get("priceToBook", "N/A"),
            "earningsQuarterlyGrowth": info.get("earningsQuarterlyGrowth", "N/A"),
            "netIncomeToCommon": info.get("netIncomeToCommon", "N/A"),
            "lastFiscalYearEnd": info.get("lastFiscalYearEnd", "N/A"),
            "nextFiscalYearEnd": info.get("nextFiscalYearEnd", "N/A"),
            "mostRecentQuarter": info.get("mostRecentQuarter", "N/A"),
            "sharesShort": info.get("sharesShort", "N/A"),
            "sharesShortPriorMonth": info.get("sharesShortPriorMonth", "N/A"),
            "sharesShortPreviousMonthDate": info.get("sharesShortPreviousMonthDate", "N/A"),
            "dateShortInterest": info.get("dateShortInterest", "N/A"),
            "shortRatio": info.get("shortRatio", "N/A"),
            "shortPercentOfFloat": info.get("shortPercentOfFloat", "N/A"),
            "sharesPercentSharesOut": info.get("sharesPercentSharesOut", "N/A"),
            "options_expirations": expiration_dates,
            "option_chain": option_chain_data,
        }

        logger.info(f"Retrieved short interest data for {symbol}")
        return short_interest_data

    except Exception as e:
        logger.error(f"Error fetching short interest data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving short interest data: {str(e)}")

@router.get("/commodities/list")
async def get_commodities_list():
    """
    Financial Modeling Prep API를 사용하여 원자재(Commodities) 목록을 가져옵니다.
    
    :return: 원자재 목록
    """
    url = f"{settings.FMP_BASE_URL}/stable/commodities-list"
    params = {"apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="원자재 목록 데이터를 찾을 수 없습니다.")
        return data

    except Exception as e:
        logger.error(f"Commodities List 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Commodities 목록 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/commodities/price/light/{symbol}")
async def get_commodity_price_light(symbol: str):
    """
    Financial Modeling Prep API를 사용하여 특정 원자재의 가벼운 가격 데이터를 가져옵니다.
    
    :param symbol: 원자재 심볼 (예: GCUSD - 금, CLUSD - 원유)
    :return: 원자재 가격 데이터 (Light Version)
    """
    url = f"{settings.FMP_BASE_URL}/stable/historical-price-eod/light"
    params = {"symbol": symbol, "apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 가벼운 가격 데이터를 찾을 수 없습니다.")
        return data

    except Exception as e:
        logger.error(f"Commodity Light Price 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Commodity Light Price 데이터를 불러오는 중 오류가 발생했습니다.")


@router.get("/commodities/price/full/{symbol}")
async def get_commodity_price_full(symbol: str):
    """
    Financial Modeling Prep API를 사용하여 특정 원자재의 전체 가격 데이터를 가져옵니다.
    
    :param symbol: 원자재 심볼 (예: GCUSD - 금, CLUSD - 원유)
    :return: 원자재 가격 데이터 (Full Version)
    """
    url = f"{settings.FMP_BASE_URL}/stable/historical-price-eod/full"
    params = {"symbol": symbol, "apikey": settings.API_KEY}

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 전체 가격 데이터를 찾을 수 없습니다.")
        return data

    except Exception as e:
        logger.error(f"Commodity Full Price 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Commodity Full Price 데이터를 불러오는 중 오류가 발생했습니다.")
  
    
@router.get("/income-statement/{symbol}")    
async def get_income_statement(symbol: str, period: str = "annual"):
    """
    특정 주식의 손익계산서(Income Statement) 데이터를 조회합니다.

    :param symbol: 주식 심볼 (예: AAPL)
    :param period: 데이터 조회 기간 ("annual" 또는 "quarterly", 기본값: "annual")
    :return: 손익계산서 데이터
    """
    url = f"{settings.FMP_BASE_URL}/stable/income-statement"
    params = {
        "period": period,
        "symbol": symbol,
        "apikey": settings.API_KEY
    }

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 손익계산서 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e  # FastAPI에서 HTTPException을 처리하도록 전달
    except Exception as e:
        logger.error(f"Income Statement 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Income Statement 데이터를 불러오는 중 오류가 발생했습니다.")
    
@router.get("/ratings-snapshot/{symbol}")
async def get_ratings_snapshot(symbol: str, limit: int = 1):
    """
    특정 주식의 재무 상태 및 평가 지표를 조회합니다.

    :param symbol: 주식 심볼 (예: AAPL)
    :param limit: 조회할 데이터 개수 (기본값: 1)
    :return: 재무 평가 지표 데이터
    """
    url = f"{settings.FMP_BASE_URL}/stable/ratings-snapshot"
    params = {
        "symbol": symbol,
        "limit": 1,
        "apikey": settings.API_KEY
    }
    logger.info(f"📊 [get_ratings_snapshot] URL: {url}")
    logger.info(f"📊 [get_ratings_snapshot] PARAMS: {params}")

    data = await call_api_async(url, params=params, method="GET")
    logger.info(f"📊 [get_ratings_snapshot] RESPONSE: {symbol} → {data[0] if data else 'No data'}")
    return data

@router.get("/sector-pe-snapshot")
async def get_sector_pe_snapshot(date: str, exchange: Optional[str] = None, sector: Optional[str] = None):
    """
    특정 날짜의 섹터별 주가수익비율(P/E) 데이터를 조회합니다.

    :param date: 조회할 날짜 (예: "2024-02-01")
    :param exchange: 특정 거래소 필터링 (예: "NASDAQ")
    :param sector: 특정 섹터 필터링 (예: "Technology")
    :return: 섹터 P/E 데이터
    """
    url = f"{settings.FMP_BASE_URL}/stable/sector-pe-snapshot"
    params = {
        "date": date,
        "apikey": settings.API_KEY
    }
    if exchange:
        params["exchange"] = exchange
    if sector:
        params["sector"] = sector
    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="해당 날짜의 섹터 P/E 데이터를 찾을 수 없습니다.")
        return data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Sector P/E Snapshot 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Sector P/E 데이터를 불러오는 중 오류가 발생했습니다.")
    
    
@router.get("/industry-pe-snapshot")
async def get_industry_pe_snapshot(date: str, exchange: Optional[str] = None, industry: Optional[str] = None):
    """
    특정 날짜의 산업별 주가수익비율(P/E) 데이터를 조회합니다.

    :param date: 조회할 날짜 (예: "2024-02-01")
    :param exchange: 특정 거래소 필터링 (예: "NASDAQ")
    :param industry: 특정 산업 필터링 (예: "Technology")
    :return: 산업 P/E 데이터
    """
    url = f"{settings.FMP_BASE_URL}/stable/industry-pe-snapshot"
    params = {
        "date": date,
        "apikey": settings.API_KEY
    }
    if exchange:
        params["exchange"] = exchange
    if industry:
        params["industry"] = industry
    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="해당 날짜의 산업 P/E 데이터를 찾을 수 없습니다.")
        return data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Industry P/E Snapshot 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Industry P/E 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/sector-performance-snapshot")
async def get_sector_performance_snapshot(date: str, exchange: Optional[str] = None, sector: Optional[str] = None):
    """
    특정 날짜의 시장 섹터 성과 데이터를 조회합니다.

    :param date: 조회할 날짜 (예: "2024-02-01")
    :param exchange: 특정 거래소 필터링 (예: "NASDAQ")
    :param sector: 특정 섹터 필터링 (예: "Technology")
    :return: 섹터 성과 데이터
    """
    url = f"{settings.FMP_BASE_URL}/stable/sector-performance-snapshot"
    params = {
        "date": date,
        "apikey": settings.API_KEY
    }
    if exchange:
        params["exchange"] = exchange
    if sector:
        params["sector"] = sector
    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="해당 날짜의 섹터 성과 데이터를 찾을 수 없습니다.")
        return data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Sector Performance Snapshot 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Sector Performance 데이터를 불러오는 중 오류가 발생했습니다.")
    
@router.get("/industry-performance-snapshot")
async def get_industry_performance_snapshot(date: str, exchange: Optional[str] = None, industry: Optional[str] = None):
    """
    특정 날짜의 산업별 성과 데이터를 조회합니다.

    :param date: 조회할 날짜 (예: "2024-02-01")
    :param exchange: 특정 거래소 필터링 (예: "NASDAQ")
    :param industry: 특정 산업 필터링 (예: "Technology")
    :return: 산업 성과 데이터
    """
    url = f"{settings.FMP_BASE_URL}/stable/industry-performance-snapshot"
    params = {
        "date": date,
        "apikey": settings.API_KEY
    }
    if exchange:
        params["exchange"] = exchange
    if industry:
        params["industry"] = industry
    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail="해당 날짜의 산업 성과 데이터를 찾을 수 없습니다.")
        return data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Industry Performance Snapshot 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="Industry Performance 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/company/ratios/{symbol}")
async def get_ratios_ttm(symbol: str):
    """
    특정 주식의 TTM 기준 주요 재무 비율 지표를 조회합니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :return: TTM 기준 재무 비율 리스트
    """
    url = f"{settings.FMP_BASE_URL}/stable/ratios-ttm"
    params = {
        "symbol": symbol,
        "apikey": settings.API_KEY
    }
    logger.info(f"📊 [get_ratios_ttm] URL: {url}")
    logger.info(f"📊 [get_ratios_ttm] PARAMS: {params}")

    data = await call_api_async(url, params=params, method="GET")
    logger.info(f"📊 [get_ratios_ttm] RESPONSE: {symbol} → {data[0] if data else 'No data'}")
    return data

@router.get("/company/key-metrics-ttm/{symbol}")
async def get_key_metrics_ttm(symbol: str):
    """
    TTM Key Metrics API를 사용하여 포괄적인 후행 12개월(TTM) 핵심 성과 지표 세트를 검색합니다. 
    회사의 수익성, 자본 효율성 및 유동성과 관련된 데이터에 액세스하여 지난 한 해 동안의 재무 건전성을 자세히 분석할 수 있습니다.
    
    :param symbol: 주식 심볼 (예: AAPL)
    :return: TTM 기준 재무 비율 리스트
    """
    url = f"{settings.FMP_BASE_URL}/stable/key-metrics-ttm"
    params = {
        "symbol": symbol,
        "apikey": settings.API_KEY
    }
    logger.info(f"📊 [get_key_metrics_ttm] URL: {url}")
    logger.info(f"📊 [get_key_metrics_ttm] PARAMS: {params}")

    data = await call_api_async(url, params=params, method="GET")
    logger.info(f"📊 [get_key_metrics_ttm] RESPONSE: {symbol} → {data[0] if data else 'No data'}")
    return data
    
@router.get("/company/dcf/{symbol}")
async def get_dcf_valuation(symbol: str):
    """
    특정 주식의 DCF(Discounted Cash Flow) 평가 데이터를 조회합니다.

    :param symbol: 주식 심볼 (예: AAPL)
    :return: DCF 평가 결과 (예: 현재 주가 대비 이론 가치)
    """
    url = f"{settings.FMP_BASE_URL}/stable/discounted-cash-flow"
    params = {
        "symbol": symbol,
        "apikey": settings.API_KEY
    }

    try:
        data = await call_api_async(url, params)
        if not data:
            raise HTTPException(status_code=404, detail=f"{symbol}의 DCF 데이터를 찾을 수 없습니다.")
        return data

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"DCF 데이터 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="DCF 데이터를 불러오는 중 오류가 발생했습니다.")

@router.get("/company/custom_dcf/{symbol}")
async def get_custom_dcf_valuation(symbol: str) -> list[dict]:
    """
    대체 DCF API 호출 (사용자 정의 파라미터 기반)
    """
    url = f"{settings.FMP_BASE_URL}/stable/custom-discounted-cash-flow"
    params = {
        "symbol": symbol,
        "apikey": settings.API_KEY
    }
    
    data = await call_api_async(url, params)
    if isinstance(data, list) and data:
        logger.info(f"📊 [get_custom_dcf_valuation] RESPONSE: {symbol} → {data[-1]}")
    elif "error" in str(data):
        logger.warning(f"❌ [get_custom_dcf_valuation] ERROR for {symbol} → {data}")
    else:
        logger.warning(f"⚠️ [get_custom_dcf_valuation] No data for {symbol}")
    return data

@router.get("/company/FinancialScores/{symbol}")
async def get_financial_scores(symbol: str) -> dict:
    """
    대체 DCF API 호출 (사용자 정의 파라미터 기반)
    """
    url = f"{settings.FMP_BASE_URL}/stable/financial-scores"
    params = {
        "symbol": symbol,
        "apikey": settings.API_KEY
    }
    
    data = await call_api_async(url, params)
    if isinstance(data, list) and data:
        logger.info(f"📊 [get_financial_scores] RESPONSE: {symbol} → {data[-1]}")
    elif "error" in str(data):
        logger.warning(f"❌ [get_financial_scores] ERROR for {symbol} → {data}")
    else:
        logger.warning(f"⚠️ [get_financial_scores] No data for {symbol}")
    return data

async def fetch_fmp_data(symbol: str) -> dict:
    try:
        # ✅ 병렬로 API 호출
        profile, ratios, key_metrics_ttm , dcf_data, ratings, scores = await asyncio.gather(
            get_company_profile(symbol),
            get_ratios_ttm(symbol),
            get_key_metrics_ttm(symbol),
            get_custom_dcf_valuation(symbol),  # 새 API
            get_ratings_snapshot(symbol),
            get_financial_scores(symbol)
        )

        # ✅ dcf_data 가 연도별 리스트로 들어온 경우 가장 최신 연도 선택
        dcf_sorted = sorted(dcf_data, key=lambda x: str(x.get("year", "0000")))
        dcf_latest = dcf_sorted[-1] if dcf_sorted else {}
        image_path = f"../../img/{symbol}"
        visualize_dcf_time_series(dcf_data, symbol, image_path)
        dcf_value = dcf_latest.get("equityValuePerShare", 0)

        return {
            "symbol": symbol,
            "profile": profile[0] if profile else {},
            "ratios": ratios[0] if ratios else {},
            "key_metrics_ttm": key_metrics_ttm[0] if key_metrics_ttm else {},
            "dcf": dcf_data [0] if dcf_data else {},
            "ratings": ratings[0] if ratings else {},
            "scores": scores[0] if scores else {},
            "dcf_value": dcf_value,
            "image_path": image_path,
        }

    except Exception as e:
        logger.error(f"[fetch_fmp_data] {symbol} 실패: {e}")
        return {"symbol": symbol, "error": str(e)}

def generate_prompt(data: dict) -> str:
    profile = data.get("profile", {})
    ratios = data.get("ratios", {})
    dcf = data.get("dcf", {})
    key_metrics_ttm = data.get("key_metrics_ttm", {})

    name = profile.get('companyName', '기업명 미확인')
    price = profile.get('price', 0)

    roe = round(key_metrics_ttm.get('returnOnEquityTTM', 0) * 100, 2)
    per = round(ratios.get('priceToEarningsRatioTTM', 0), 2)
    div = round(ratios.get('dividendYieldTTM', 0) * 100, 2)
    debt = round(ratios.get('debtToAssetsRatioTTM', 0) * 100, 2)

    dcf_value = dcf.get("equityValuePerShare", 0)
    dcf_gap = round((dcf_value - price) / price * 100, 2) if price else 0

    wacc = dcf.get("wacc", None)
    longTermGrowthRate = dcf.get("longTermGrowthRate", None)
    longTermGrowthRate = dcf.get("longTermGrowthRate", None)
    terminal = dcf.get("terminalValue", None)

    prompt = f"""
📊 [{name}]의 재무 정보 요약:

- 현재 주가: ${price}
- PER: {per}
- ROE: {roe}%
- 배당수익률: {div}%
- 부채비율 (자산 대비): {debt}%
- WACC는 {wacc}%, 장기 성장률은 {longTermGrowthRate}%로 설정되었으며, DCF 기준 주당 가치: ${dcf_value} ({'저평가' if dcf_gap > 0 else '고평가'}) 입니다.
"""

    if wacc:
        prompt += f"- 할인율(WACC): {wacc}% "
    if terminal:
        prompt += f"- 최종기말가치(Terminal Value): {terminal:,} "

    prompt += " 이 데이터를 바탕으로 투자 매력도 분석 요약을 작성해 주세요."

    return prompt.strip()

client = OpenAI(api_key=settings.OPENAI_API_KEY)

async def gpt_analyze(data: dict) -> str:
    prompt = generate_prompt(data)

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # 필요시 gpt-4로 변경 가능
            messages=[
                {"role": "system", "content": "당신은 최고에 금융 증권 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"[gpt_analyze] GPT 분석 실패: {e}")
        return "GPT 분석에 실패했습니다."

def score_stock(data: dict) -> int:
    score = 0

    profile = data.get("profile", {})
    ratios = data.get("ratios", {})
    dcf = data.get("dcf", {})
    key_metrics_ttm = data.get("key_metrics_ttm", {})
    scores = data.get("scores", {})

    roe = key_metrics_ttm.get("returnOnEquityTTM", 0)
    dividend = ratios.get("dividendYieldTTM", 0)
    debt_ratio = ratios.get("debtToAssetsRatioTTM", 0)
    price = profile.get("price", 0)
    dcf_value = dcf.get("equityValuePerShare", 0)
    piotroskiScore = scores.get("piotroskiScore", 0)
    altmanZScore = scores.get("altmanZScore", 0)

    # ROE 점수
    if roe >= 0.15:
        score += 2
    elif roe >= 0.1:
        score += 1

    # 배당수익률 점수
    if dividend >= 0.03:
        score += 2
    elif dividend >= 0.015:
        score += 1

    # 부채비율 점수 (자산 대비)
    if debt_ratio <= 0.3:
        score += 2
    elif debt_ratio <= 0.5:
        score += 1

    # DCF 저평가 여부
    dcf_gap = ((dcf_value - price) / price) if price else 0
    if dcf_gap >= 0.2:
        score += 2
    elif dcf_gap >= 0.1:
        score += 1
        
    # Piotroski Score (예: 8 이상이면 우량)
    if piotroskiScore >= 8:
        score += 1

    # Altman Z-Score (예: 3 이상이면 안정적)
    if altmanZScore >= 3:
        score += 1

    return score

async def get_stock_screener_list(filters: dict) -> list[str]:
    url = f"{settings.FMP_BASE_URL}/stable/company-screener"
    
    # bool 처리
    for key in ["isEtf", "isFund", "isActivelyTrading"]:
        if key in filters:
            filters[key] = str(filters[key]).lower()

    filters["apikey"] = settings.API_KEY

    data = await call_api_async(url, filters)
    return [item["symbol"] for item in data if "symbol" in item]

def visualize_dcf_time_series(dcf_list: list[dict], symbol: str, save_path: str = "../../img/dcf_chart.png"):
    years = []
    equity_values = []
    waccs = []
    terminal_values = []

    for item in dcf_list:
        if not item.get("year"):
            continue
        years.append(str(item["year"]))
        equity_values.append(item.get("equityValuePerShare", 0))
        waccs.append(item.get("wacc", 0))
        terminal_values.append(item.get("terminalValue", 0))

    fig, ax1 = plt.subplots(figsize=(10, 6))

    ax1.plot(years, equity_values, marker='o', label="Equity/Share ($)")
    ax1.plot(years, terminal_values, marker='s', label="Terminal Value", linestyle='--')
    ax1.set_ylabel("Value ($)")
    ax1.set_title(f"{symbol} DCF 시계열")
    ax1.grid(True, linestyle="--", alpha=0.5)

    ax2 = ax1.twinx()
    ax2.plot(years, waccs, color='gray', marker='x', label="WACC (%)")
    ax2.set_ylabel("WACC (%)")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()
    
def format_telegram_message(result: dict) -> str:
    symbol = result["symbol"]
    score = result["score"]
    dcf = result.get("dcf_value", "N/A")
    price = result.get("current_price", "N/A")
    summary = result.get("summary", "")

    return f"""
📈 {symbol} 분석 결과*
점수: {score}
현재 주가: ${price}
DCF 가치: ${dcf}

{summary}
""".strip()
    
async def notify_telegram(message: str, image_path: str = None):
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM 설정이 누락되어 알림 전송 생략")
        return

    # 1. 메시지 전송
    url_msg = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": settings.TELEGRAM_CHAT_ID, "text": message}
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(url_msg, json=payload)
            logger.info("📬 Telegram 메시지 전송 완료")
        except Exception as e:
            logger.error(f"Telegram 메시지 전송 실패: {e}")

    # 2. 이미지 전송 (선택)
    if image_path and os.path.exists(image_path):
        url_photo = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendPhoto"
        data = {"chat_id": settings.TELEGRAM_CHAT_ID}
        with open(image_path, "rb") as photo:
            try:
                async with session.post(url_photo, data=data, files={"photo": photo}) as response:
                    logger.info(f"📸 Telegram 이미지 전송 완료: {response.status}")
            except Exception as e:
                logger.error(f"Telegram 이미지 전송 실패: {e}")

    
@router.get("/analysis/pipeline")
async def run_pipeline():
    # 1. 스크리너 필터링: 기술주 + 시가총액 100억 이상 + 배당 2% 이상
    filters = {
        "marketCapMoreThan": 0,
        "marketCapLowerThan": 1007331704681,
        "dividendMoreThan": 0.02,
        "isEtf": "false",
        "isFund": "false",
        "isActivelyTrading": "true",
        "country": "US",
        "sector": "Technology",
        "limit": 1
    }

    symbols = await get_stock_screener_list(filters)

    # 2. 재무 데이터 수집
    #tasks = [fetch_fmp_data(sym) for sym in symbols]
    tasks = [fetch_fmp_data(sym) for sym in symbols]
    all_data = await asyncio.gather(*tasks)
    
    # 3. GPT 분석 (또는 점수 계산)
    results = []
    for data in all_data:
        if "error" in data:
            logger.warning(f"⚠️ 데이터 오류: {data}")
            continue

        try:
            score = score_stock(data)
            summary = await gpt_analyze(data)

            result = {
                "symbol": data["symbol"],
                "score": score,
                "summary": summary,
                "dcf_value": data.get("dcf_value", 0),
                "current_price": data.get("profile", {}).get("price", 0),
            }
            results.append(result)
            # ✅ 텔레그램 전송
            message = format_telegram_message(result)
            await notify_telegram(message, image_path=data.get("image_path"))          
        except Exception as e:
            logger.error(f"GPT 분석 실패: {data['symbol']} - {e}")
            results.append({
                "symbol": data["symbol"],
                "score": None,
                "summary": "분석 실패",
                "error": str(e)
            })
    return {"count": len(results), "results": results}