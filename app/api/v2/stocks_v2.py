# app/api/stocks.py
import json
import logging
import os
import traceback
from datetime import datetime
from typing import Any, List, Optional, Union

import aiohttp
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from financetoolkit import Toolkit

from app.core.config import settings
from app.core.logging import logger  # 이미 설정된 logger import
from screening.economic_monitor import (get_latest_economic_indicators,
                                        run_economic_monitor_pipeline,
                                        run_treasury_monitor_pipeline)
from screening.pipeline import (run_dividend_growth_pipeline,
                                run_pipeline_for_report)
from screening.portfolio_rebalance import (rebalance_portfolio_for_report,
                                           run_portfolio_rebalance_pipeline)
from utils.notifier import notify_telegram
from utils.report_generator import generate_investment_report

logging.disable(logging.NOTSET)  # 🚀 모든 로그 활성화
logging.getLogger().setLevel(logging.DEBUG)  # DEBUG 레벨 강제 설정

router = APIRouter()

async def call_api_async(url: str, params: Optional[dict] = None, timeout: int = 10):
    """비동기 API 호출을 처리하는 함수"""
    async with aiohttp.ClientSession() as session:  # 항상 새로운 세션 생성
        try:
            logger.info(f"FMP URL : {url}")
            async with session.get(url, params=params, timeout=timeout) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"API 호출 실패: {url} - {e}")
            raise HTTPException(status_code=500, detail=f"API 호출 실패: {e}")

@router.get("/ratios/profitability")
async def get_profitability_ratios(
    symbols: str = Query(..., description="Comma-separated list of stock symbols"),
    rounding: int = Query(4, description="Number of decimals to round to"),
    growth: bool = Query(False, description="Calculate growth of the ratios"),
    lag: int = Query(1, description="Lag period for growth calculation"),
    trailing: int = Query(None, description="Trailing period for TTM calculation (e.g., 4 for quarterly)")
):
    """
    특정 주식들의 수익성 비율(Profitability Ratios)을 가져오는 API
    2025-02-15 17:56:46,268 - app - INFO - Raw profitability_ratios DataFrame:
    date                                              2015  2016   2017    2018     2019   2020    2021   2022   2023   2024
    AAPL Gross Margin                                  NaN   NaN  -0.04   -0.02   -0.018 -0.003   0.106  0.134  0.055  0.067
        Operating Margin                              NaN   NaN -0.121  -0.079   -0.082 -0.094   0.211  0.252    0.0   0.04
        Net Profit Margin                             NaN   NaN -0.075   0.057    0.005 -0.067   0.222  0.211 -0.023 -0.051
        Interest Coverage Ratio                       NaN   NaN -0.729  -0.502   -0.309  0.088   1.161  0.654 -0.296    inf
        Income Before Tax Profit Margin               NaN   NaN -0.097  -0.039   -0.096 -0.109   0.178  0.238 -0.003  0.046
        Effective Tax Rate                            NaN   NaN -0.068  -0.285   -0.354 -0.213  -0.164  0.125  0.105  0.488
        Return on Assets                              NaN   NaN -0.473   0.081    0.129  0.075    0.79  0.642 -0.021 -0.081
        Return on Equity                              NaN   NaN  0.398   0.339    0.515  0.492   1.637  1.381  0.167 -0.103
        Return on Invested Capital                    NaN   NaN -0.004   0.072    0.255   0.19   0.709  0.619  0.115   0.08
        Return on Capital Employed                    NaN   NaN -0.307   0.178    0.231  0.049   0.664  0.919  0.145  0.067
        Return on Tangible Assets                     NaN   NaN -0.756   0.032    0.071  0.021   0.703  0.571 -0.032 -0.078
        Income Quality Ratio                          NaN   NaN -0.127  -0.103   -0.054   0.08  -0.125 -0.129  0.037  0.031
        Net Income per EBT                            NaN   NaN  0.024   0.098    0.115  0.048   0.031 -0.021 -0.016 -0.094
        Free Cash Flow to Operating Cash Flow Ratio   NaN   NaN -0.068   0.042     0.06  0.098   0.053  0.003  0.008  0.009
        EBT to EBIT Ratio                             NaN   NaN -0.025   -0.02   -0.018  0.002    0.03  0.018 -0.009  0.025
        EBIT to Revenue                               NaN   NaN -0.073  -0.014   -0.083 -0.111    0.15  0.216  0.003  0.019
    TSLA Gross Margin                                  NaN   NaN -0.171  -0.175   -0.122  0.117   0.524  0.219 -0.281 -0.301
        Operating Margin                              NaN   NaN -0.215  -0.811   -0.978   -4.5 -41.333  1.667  -0.24 -0.571
        Net Profit Margin                             NaN   NaN -0.241  -0.521    -0.79   -1.5  -3.943  5.696  0.505 -0.526
        Interest Coverage Ratio                       NaN   NaN -1.003   0.622    379.5  1.528   7.354 14.791  2.418  -0.61
        Income Before Tax Profit Margin               NaN   NaN  -0.13  -0.561   -0.856 -1.787   -5.37  3.541 -0.127 -0.452
        Effective Tax Rate                            NaN   NaN -0.067   0.611   10.786 -5.362  -1.667 -0.676 -5.555  1.488
        Return on Assets                              NaN   NaN  4.067   -0.25   -0.645 -1.515  -4.593  9.235  0.639 -0.644
        Return on Equity                              NaN   NaN 21.667  -0.155   -0.647 -1.276  -2.667  6.222   0.37 -0.683
        Return on Invested Capital                    NaN   NaN  7.133  -0.288   -0.672 -1.462  -4.575 10.375  0.678 -0.663
        Return on Capital Employed                    NaN   NaN -0.514  -0.519   -0.957 -4.538 -52.667  4.435 -0.161   -0.6
        Return on Tangible Assets                     NaN   NaN -0.701   -0.28   -0.651 -1.556    -5.2   10.8  0.762 -0.153
        Income Quality Ratio                          NaN   NaN -0.954 -13.338 -115.926 -5.363  -1.671 -0.864 -0.575  0.789
        Net Income per EBT                            NaN   NaN  0.002   0.021    0.127  -0.33  -0.225  0.289  0.689 -0.135
        Free Cash Flow to Operating Cash Flow Ratio   NaN   NaN 15.493  -1.008   -0.994 -5.324  -0.246   0.13  0.086 -0.524
        EBT to EBIT Ratio                             NaN   NaN  0.143   1.497    7.484  -0.84  -0.916  0.715  0.043 -0.024
        EBIT to Revenue                               NaN   NaN -0.337  -0.812   -0.976 -5.667 -41.667  2.054 -0.139 -0.444
    2025-02-15 17:56:46,300 - app - INFO - Processed DataFrame:
    level_0                                      level_1  2015  2016   2017    2018     2019   2020    2021   2022   2023   2024  
    0     AAPL                                 Gross Margin  None  None  -0.04   -0.02   -0.018 -0.003   0.106  0.134  0.055  0.067  
    1     AAPL                             Operating Margin  None  None -0.121  -0.079   -0.082 -0.094   0.211  0.252    0.0   0.04  
    2     AAPL                            Net Profit Margin  None  None -0.075   0.057    0.005 -0.067   0.222  0.211 -0.023 -0.051  
    3     AAPL                      Interest Coverage Ratio  None  None -0.729  -0.502   -0.309  0.088   1.161  0.654 -0.296   None  
    4     AAPL              Income Before Tax Profit Margin  None  None -0.097  -0.039   -0.096 -0.109   0.178  0.238 -0.003  0.046  
    5     AAPL                           Effective Tax Rate  None  None -0.068  -0.285   -0.354 -0.213  -0.164  0.125  0.105  0.488  
    6     AAPL                             Return on Assets  None  None -0.473   0.081    0.129  0.075    0.79  0.642 -0.021 -0.081  
    7     AAPL                             Return on Equity  None  None  0.398   0.339    0.515  0.492   1.637  1.381  0.167 -0.103  
    8     AAPL                   Return on Invested Capital  None  None -0.004   0.072    0.255   0.19   0.709  0.619  0.115   0.08  
    9     AAPL                   Return on Capital Employed  None  None -0.307   0.178    0.231  0.049   0.664  0.919  0.145  0.067  
    10    AAPL                    Return on Tangible Assets  None  None -0.756   0.032    0.071  0.021   0.703  0.571 -0.032 -0.078  
    11    AAPL                         Income Quality Ratio  None  None -0.127  -0.103   -0.054   0.08  -0.125 -0.129  0.037  0.031  
    12    AAPL                           Net Income per EBT  None  None  0.024   0.098    0.115  0.048   0.031 -0.021 -0.016 -0.094  
    13    AAPL  Free Cash Flow to Operating Cash Flow Ratio  None  None -0.068   0.042     0.06  0.098   0.053  0.003  0.008  0.009  
    14    AAPL                            EBT to EBIT Ratio  None  None -0.025   -0.02   -0.018  0.002    0.03  0.018 -0.009  0.025  
    15    AAPL                              EBIT to Revenue  None  None -0.073  -0.014   -0.083 -0.111    0.15  0.216  0.003  0.019  
    16    TSLA                                 Gross Margin  None  None -0.171  -0.175   -0.122  0.117   0.524  0.219 -0.281 -0.301  
    17    TSLA                             Operating Margin  None  None -0.215  -0.811   -0.978   -4.5 -41.333  1.667  -0.24 -0.571  
    18    TSLA                            Net Profit Margin  None  None -0.241  -0.521    -0.79   -1.5  -3.943  5.696  0.505 -0.526  
    19    TSLA                      Interest Coverage Ratio  None  None -1.003   0.622    379.5  1.528   7.354 14.791  2.418  -0.61  
    20    TSLA              Income Before Tax Profit Margin  None  None  -0.13  -0.561   -0.856 -1.787   -5.37  3.541 -0.127 -0.452  
    21    TSLA                           Effective Tax Rate  None  None -0.067   0.611   10.786 -5.362  -1.667 -0.676 -5.555  1.488  
    22    TSLA                             Return on Assets  None  None  4.067   -0.25   -0.645 -1.515  -4.593  9.235  0.639 -0.644  
    23    TSLA                             Return on Equity  None  None 21.667  -0.155   -0.647 -1.276  -2.667  6.222   0.37 -0.683  
    24    TSLA                   Return on Invested Capital  None  None  7.133  -0.288   -0.672 -1.462  -4.575 10.375  0.678 -0.663  
    25    TSLA                   Return on Capital Employed  None  None -0.514  -0.519   -0.957 -4.538 -52.667  4.435 -0.161   -0.6  
    26    TSLA                    Return on Tangible Assets  None  None -0.701   -0.28   -0.651 -1.556    -5.2   10.8  0.762 -0.153  
    27    TSLA                         Income Quality Ratio  None  None -0.954 -13.338 -115.926 -5.363  -1.671 -0.864 -0.575  0.789  
    28    TSLA                           Net Income per EBT  None  None  0.002   0.021    0.127  -0.33  -0.225  0.289  0.689 -0.135  
    29    TSLA  Free Cash Flow to Operating Cash Flow Ratio  None  None 15.493  -1.008   -0.994 -5.324  -0.246   0.13  0.086 -0.524  
    30    TSLA                            EBT to EBIT Ratio  None  None  0.143   1.497    7.484  -0.84  -0.916  0.715  0.043 -0.024  
    31    TSLA                              EBIT to Revenue  None  None -0.337  -0.812   -0.976 -5.667 -41.667  2.054 -0.139 -0.444     
    """
    try:
        tickers = symbols.split(",")  # 쉼표로 구분된 문자열을 리스트로 변환
        logger.info(f"Received request for tickers: {tickers}")

        # Toolkit 객체 생성
        toolkit = Toolkit(tickers, api_key=settings.API_KEY)

        # 수익성 비율 데이터 가져오기
        profitability_ratios = toolkit.ratios.collect_profitability_ratios(
            rounding=rounding,
            growth=growth,
            lag=lag,
            trailing=trailing
        )

        # DataFrame 로깅
        logger.info(f"Raw profitability_ratios DataFrame:\n{profitability_ratios}")

        # 특정 티커의 데이터를 추출
        result = profitability_ratios.loc[tickers]

        # 멀티인덱스 해제 (index를 컬럼으로 변환)
        result = result.reset_index()

        # 기간(Period 타입)을 문자열로 변환
        result.columns = [str(col) for col in result.columns]

        # ⚠️ NaN, inf, -inf 값을 None으로 변환
        result = result.replace([np.inf, -np.inf, np.nan], None)

        # 변환된 DataFrame 로깅
        logger.info(f"Processed DataFrame:\n{result}")

        # JSON 변환
        json_result = result.to_dict(orient="records")  # 리스트 형태로 변환

        # 최종 JSON 로깅
        logger.info(f"Final JSON response: {json_result}")

        return jsonable_encoder(json_result)

    except Exception as e:
        logger.error(f"Error in get_profitability_ratios: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    
@router.get("/models/dupont")
async def get_dupont_analysis(
    symbols: str = Query(..., description="Comma-separated list of stock symbols"),
    quarterly: bool = Query(False, description="Use quarterly data if True, otherwise yearly"),
    rounding: int = Query(4, description="Number of decimals to round to"),
    start_date: str = Query("2022-12-31", description="Start date for historical data (YYYY-MM-DD)")
):
    """
    특정 주식들의 DUPONT 분석 결과를 가져오는 API
    2025-02-15 17:33:44,749 - app - INFO - Raw DUPONT DataFrame:
    date                          2022Q4  2023Q1  2023Q2  2023Q3  2023Q4  2024Q1  2024Q2  2024Q3  2024Q4
    AMZN Interest Burden Ratio    -2.845   1.159   1.016   0.918   0.965   1.179   0.962   0.965   0.949
        Tax Burden Ratio          0.102   0.664   0.879   0.883   0.804   0.681   0.919    0.88   0.943
        Operating Profit Margin  -0.006   0.032   0.056   0.085   0.081   0.091   0.103   0.114   0.119
        Asset Turnover              NaN   0.275   0.285   0.297   0.335   0.271   0.273   0.279   0.311
        Equity Multiplier           NaN   3.084   2.915   2.743   2.637    2.53   2.396   2.299   2.219
        Return on Equity            NaN   0.021   0.042   0.056   0.055    0.05    0.06   0.062   0.073
    TSLA Interest Burden Ratio     0.979   0.951   0.817   0.863   0.942   0.754   0.851   0.976   0.572
        Tax Burden Ratio          0.952   0.943   1.127    1.05   3.842   0.964   0.921   0.798   1.464
        Operating Profit Margin   0.164    0.12   0.118   0.088   0.087   0.073   0.074   0.111   0.108
        Asset Turnover              NaN   0.276   0.281   0.253   0.251   0.197    0.23   0.216   0.213
        Equity Multiplier           NaN   1.778   1.749    1.73   1.698   1.676   1.677   1.686   1.675
        Return on Equity            NaN   0.053   0.053   0.035   0.134   0.018   0.022   0.031   0.032
    2025-02-15 17:33:44,768 - app - INFO - Processed DataFrame:
    level_0                  level_1 2022Q4 2023Q1 2023Q2 2023Q3 2023Q4 2024Q1 2024Q2 2024Q3 2024Q4
    0     AMZN    Interest Burden Ratio -2.845  1.159  1.016  0.918  0.965  1.179  0.962  0.965  0.949
    1     AMZN         Tax Burden Ratio  0.102  0.664  0.879  0.883  0.804  0.681  0.919   0.88  0.943
    2     AMZN  Operating Profit Margin -0.006  0.032  0.056  0.085  0.081  0.091  0.103  0.114  0.119
    3     AMZN           Asset Turnover   None  0.275  0.285  0.297  0.335  0.271  0.273  0.279  0.311
    4     AMZN        Equity Multiplier   None  3.084  2.915  2.743  2.637   2.53  2.396  2.299  2.219
    5     AMZN         Return on Equity   None  0.021  0.042  0.056  0.055   0.05   0.06  0.062  0.073
    6     TSLA    Interest Burden Ratio  0.979  0.951  0.817  0.863  0.942  0.754  0.851  0.976  0.572
    7     TSLA         Tax Burden Ratio  0.952  0.943  1.127   1.05  3.842  0.964  0.921  0.798  1.464
    8     TSLA  Operating Profit Margin  0.164   0.12  0.118  0.088  0.087  0.073  0.074  0.111  0.108
    9     TSLA           Asset Turnover   None  0.276  0.281  0.253  0.251  0.197   0.23  0.216  0.213
    10    TSLA        Equity Multiplier   None  1.778  1.749   1.73  1.698  1.676  1.677  1.686  1.675
    11    TSLA         Return on Equity   None  0.053  0.053  0.035  0.134  0.018  0.022  0.031  0.032    
    """
    try:
        tickers = symbols.split(",")  # 쉼표로 구분된 문자열을 리스트로 변환
        logger.info(f"Received request for tickers: {tickers}")

        # Toolkit 객체 생성
        toolkit = Toolkit(tickers, api_key=settings.API_KEY, quarterly=quarterly, start_date=start_date)

        # DUPONT 분석 실행
        dupont_analysis = toolkit.models.get_extended_dupont_analysis(rounding=rounding)

        # DataFrame 로깅
        logger.info(f"Raw DUPONT DataFrame:\n{dupont_analysis}")

        # 특정 티커의 데이터를 추출
        result = dupont_analysis.loc[tickers]

        # 멀티인덱스 해제 (index를 컬럼으로 변환)
        result = result.reset_index()

        # 기간(Period 타입)을 문자열로 변환
        result.columns = [str(col) for col in result.columns]

        # ⚠️ NaN, inf, -inf 값을 None으로 변환
        result = result.replace([np.inf, -np.inf, np.nan], None)

        # 변환된 DataFrame 로깅
        logger.info(f"Processed DataFrame:\n{result}")

        # JSON 변환
        json_result = result.to_dict(orient="records")  # 리스트 형태로 변환

        # 최종 JSON 로깅
        logger.info(f"Final JSON response: {json_result}")

        return jsonable_encoder(json_result)

    except Exception as e:
        logger.error(f"Error in get_dupont_analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/options/greeks")
async def collect_all_greeks(
    symbols: str = Query(..., description="Comma-separated list of stock symbols"),
    start_date: str = Query(None, description="Start date for Greeks calculation (YYYY-MM-DD)"),
    strike_price_range: float = Query(0.25, description="Percentage range for strike prices (e.g., 0.25 for 25%)"),
    strike_step_size: int = Query(5, description="Step size for strike prices"),
    expiration_time_range: int = Query(30, description="Number of days to expiration"),
    risk_free_rate: float = Query(None, description="Risk-free rate (leave empty for default)"),
    dividend_yield: float = Query(None, description="Dividend yield (leave empty for default)"),
    put_option: bool = Query(False, description="Calculate put option Greeks if True, otherwise call option Greeks"),
    show_input_info: bool = Query(False, description="Return input parameters used in the calculation"),
    rounding: int = Query(4, description="Number of decimals to round the results to")
):
    """
    특정 주식들의 옵션 Greeks(델타, 감마, 베가 등)를 계산하는 API
    """
    try:
        tickers = symbols.split(",")  # 쉼표로 구분된 문자열을 리스트로 변환
        logger.info(f"Received request for tickers: {tickers}")

        # Toolkit 객체 생성
        toolkit = Toolkit(tickers, api_key=settings.API_KEY)

        # 모든 Greeks 계산 실행
        all_greeks = toolkit.options.collect_all_greeks(
            start_date=start_date,
            strike_price_range=strike_price_range,
            strike_step_size=strike_step_size,
            expiration_time_range=expiration_time_range,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
            put_option=put_option,
            show_input_info=show_input_info,
            rounding=rounding
        )

        # DataFrame 로깅
        logger.info(f"Raw Greeks DataFrame:\n{all_greeks}")

        # 특정 티커의 데이터를 추출
        result = all_greeks.loc[tickers].reset_index()

        # 날짜 컬럼이 존재하면 문자열 변환
        result.columns = [str(col) for col in result.columns]

        # ⚠️ NaN, inf, -inf 값을 None으로 변환
        result = result.replace([np.inf, -np.inf, np.nan], None)

        # 변환된 DataFrame 로깅
        logger.info(f"Processed DataFrame:\n{result}")

        # JSON 변환
        json_result = result.to_dict(orient="records")  # 리스트 형태로 변환

        # 최종 JSON 로깅
        logger.info(f"Final JSON response: {json_result}")

        return jsonable_encoder(json_result)

    except Exception as e:
        logger.error(f"Error in collect_all_greeks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/options/chains")
async def get_option_chains(
    symbols: str = Query(..., description="Comma-separated list of stock symbols"),
    expiration_date: str = Query(None, description="Expiration date for the options (YYYY-MM-DD)"),
    in_the_money: bool = Query(None, description="Filter options that are in the money"),
    rounding: int = Query(4, description="Number of decimals to round to")
):
    """
    특정 주식들의 옵션 체인 데이터를 가져오는 API
    """
    try:
        tickers = symbols.split(",")  # 쉼표로 구분된 문자열을 리스트로 변환
        logger.info(f"Received request for tickers: {tickers}")

        # Toolkit 객체 생성
        toolkit = Toolkit(tickers, api_key=settings.API_KEY)

        # 옵션 체인 데이터 가져오기
        option_chains = toolkit.options.get_option_chains()        

        # DataFrame 로깅
        logger.info(f"Raw Options Chains DataFrame:\n{option_chains}")

        # 특정 티커의 데이터를 추출
        result = option_chains.loc[tickers].reset_index()

        # `In The Money` 필터링
        if in_the_money is not None:
            result = result[result["In The Money"] == in_the_money]

        # 날짜 컬럼이 존재하면 문자열 변환
        for date_col in ["Expiration", "Last Trade Date"]:
            if date_col in result.columns:
                result[date_col] = result[date_col].astype(str)

        # 컬럼을 문자열로 변환
        result.columns = [str(col) for col in result.columns]

        # ⚠️ NaN, inf, -inf 값을 None으로 변환
        result = result.replace([np.inf, -np.inf, np.nan], None)

        # 변환된 DataFrame 로깅
        logger.info(f"Processed DataFrame:\n{result}")

        # JSON 변환
        json_result = result.to_dict(orient="records")  # 리스트 형태로 변환

        # 최종 JSON 로깅
        logger.info(f"Final JSON response: {json_result}")

        return jsonable_encoder(json_result)

    except Exception as e:
        logger.error(f"Error in get_option_chains: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/options/black_scholes")
async def get_black_scholes_model(
    symbols: str = Query(..., description="Comma-separated list of stock symbols"),
    start_date: str = Query(None, description="Start date for option price calculation (YYYY-MM-DD)"),
    put_option: bool = Query(False, description="Calculate put option price if True, otherwise call option price"),
    strike_price_range: float = Query(0.25, description="Percentage range for strike prices (e.g., 0.25 for 25%)"),
    strike_step_size: int = Query(5, description="Step size for strike prices"),
    expiration_time_range: int = Query(30, description="Number of days to expiration"),
    risk_free_rate: float = Query(None, description="Risk-free rate (leave empty for default)"),
    dividend_yield: float = Query(None, description="Dividend yield (leave empty for default)"),
    rounding: int = Query(4, description="Number of decimals to round the results to")
):
    """
    특정 주식들의 Black-Scholes 모델 기반 옵션 가격을 계산하는 API
    """
    try:
        tickers = symbols.split(",")  # 쉼표로 구분된 문자열을 리스트로 변환
        logger.info(f"Received request for tickers: {tickers}")

        # Toolkit 객체 생성
        toolkit = Toolkit(tickers, api_key=settings.API_KEY)

        # Black-Scholes 모델 계산 실행
        black_scholes = toolkit.options.get_black_scholes_model(
            start_date=start_date,
            put_option=put_option,
            strike_price_range=strike_price_range,
            strike_step_size=strike_step_size,
            expiration_time_range=expiration_time_range,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
            rounding=rounding
        )

        # DataFrame 로깅
        logger.info(f"Raw Black-Scholes DataFrame:\n{black_scholes}")

        # 특정 티커의 데이터를 추출
        result = black_scholes.loc[tickers].reset_index()

        # 날짜 컬럼이 존재하면 문자열 변환
        result.columns = [str(col) for col in result.columns]

        # ⚠️ NaN, inf, -inf 값을 None으로 변환
        result = result.replace([np.inf, -np.inf, np.nan], None)

        # 변환된 DataFrame 로깅
        logger.info(f"Processed DataFrame:\n{result}")

        # JSON 변환
        json_result = result.to_dict(orient="records")  # 리스트 형태로 변환

        # 최종 JSON 로깅
        logger.info(f"Final JSON response: {json_result}")

        return jsonable_encoder(json_result)

    except Exception as e:
        logger.error(f"Error in get_black_scholes_model: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/options/implied_volatility")
async def get_implied_volatility(
    symbols: str = Query(..., description="Comma-separated list of stock symbols"),
    expiration_date: str = Query(None, description="Expiration date for the options (YYYY-MM-DD)"),
    put_option: bool = Query(False, description="Calculate put option IV if True, otherwise call option IV"),
    risk_free_rate: float = Query(None, description="Risk-free rate (leave empty for default)"),
    dividend_yield: float = Query(None, description="Dividend yield (leave empty for default)"),
    show_expiration_dates: bool = Query(False, description="Return available expiration dates instead of IV"),
    show_input_info: bool = Query(False, description="Return input parameters used in the calculation"),
    rounding: int = Query(4, description="Number of decimals to round the results to")
):
    """
    특정 주식들의 옵션 내재 변동성(Implied Volatility, IV)을 계산하는 API
    """
    try:
        tickers = symbols.split(",")  # 쉼표로 구분된 문자열을 리스트로 변환
        logger.info(f"Received request for tickers: {tickers}")

        # Toolkit 객체 생성
        toolkit = Toolkit(tickers, api_key=settings.API_KEY)

        # 내재 변동성(IV) 계산 실행
        implied_volatility = toolkit.options.get_implied_volatility(
            expiration_date=expiration_date,
            put_option=put_option,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
            show_expiration_dates=show_expiration_dates,
            show_input_info=show_input_info,
            rounding=rounding
        )

        # 만료일 목록 요청인 경우 리스트 반환
        if show_expiration_dates:
            logger.info(f"Available expiration dates: {implied_volatility}")
            return jsonable_encoder({"tickers": tickers, "available_expirations": implied_volatility})

        # DataFrame 로깅
        logger.info(f"Raw Implied Volatility DataFrame:\n{implied_volatility}")

        # 특정 티커의 데이터를 추출
        result = implied_volatility.loc[tickers].reset_index()

        # 날짜 컬럼이 존재하면 문자열 변환
        result.columns = [str(col) for col in result.columns]

        # ⚠️ NaN, inf, -inf 값을 None으로 변환
        result = result.replace([np.inf, -np.inf, np.nan], None)

        # 변환된 DataFrame 로깅
        logger.info(f"Processed DataFrame:\n{result}")

        # JSON 변환
        json_result = result.to_dict(orient="records")  # 리스트 형태로 변환

        # 최종 JSON 로깅
        logger.info(f"Final JSON response: {json_result}")

        return jsonable_encoder(json_result)

    except Exception as e:
        logger.error(f"Error in get_implied_volatility: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/options/binomial_tree")
async def get_binomial_trees_model(
    symbols: str = Query(..., description="Comma-separated list of stock symbols"),
    start_date: str = Query(None, description="Start date for option price calculation (YYYY-MM-DD)"),
    put_option: bool = Query(False, description="Calculate put option if True, otherwise call option"),
    strike_price_range: float = Query(0.25, description="Percentage range for strike prices (e.g., 0.25 for 25%)"),
    strike_step_size: int = Query(5, description="Step size for strike prices"),
    time_to_expiration: int = Query(1, description="Number of years to expiration"),
    timesteps: int = Query(10, description="Number of time steps in the binomial tree"),
    risk_free_rate: float = Query(None, description="Risk-free rate (leave empty for default)"),
    dividend_yield: float = Query(None, description="Dividend yield (leave empty for default)"),
    show_input_info: bool = Query(False, description="Return input parameters used in the calculation"),
    rounding: int = Query(4, description="Number of decimals to round the results to")
):
    """
    특정 주식들의 이항 옵션 가격 결정 모델(Binomial Option Pricing Model)을 계산하는 API
    """
    try:
        tickers = symbols.split(",")  # 쉼표로 구분된 문자열을 리스트로 변환
        logger.info(f"Received request for tickers: {tickers}")

        # Toolkit 객체 생성
        toolkit = Toolkit(tickers, api_key=settings.API_KEY)

        # 이항 옵션 가격 결정 모델 계산 실행
        binomial_trees = toolkit.options.get_binomial_model(
            start_date=start_date,
            put_option=put_option,
            strike_price_range=strike_price_range,
            strike_step_size=strike_step_size,
            time_to_expiration=time_to_expiration,
            timesteps=timesteps,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
            show_input_info=show_input_info,
            rounding=rounding
        )
        # DataFrame 로깅
        logger.info(f"Raw Binomial Trees Model DataFrame:\n{binomial_trees}")

        # 특정 티커의 데이터를 추출
        result = binomial_trees.loc[tickers].reset_index()

        # 날짜 컬럼이 존재하면 문자열 변환
        result.columns = [str(col) for col in result.columns]

        # ⚠️ NaN, inf, -inf 값을 None으로 변환
        result = result.replace([np.inf, -np.inf, np.nan], None)

        # 변환된 DataFrame 로깅
        logger.info(f"Processed DataFrame:\n{result}")

        # JSON 변환
        json_result = result.to_dict(orient="records")  # 리스트 형태로 변환

        # 최종 JSON 로깅
        logger.info(f"Final JSON response: {json_result}")

        return jsonable_encoder(json_result)

    except Exception as e:
        logger.error(f"Error in get_binomial_trees_model: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/options/stock_price_simulation")
async def get_stock_price_simulation(
    symbols: str = Query(..., description="Comma-separated list of stock symbols"),
    start_date: str = Query(None, description="Start date for stock price simulation (YYYY-MM-DD)"),
    time_to_expiration: int = Query(1, description="Number of years to expiration"),
    timesteps: int = Query(10, description="Number of time steps in the binomial tree"),
    risk_free_rate: float = Query(None, description="Risk-free rate (leave empty for default)"),
    show_unique_combinations: bool = Query(False, description="Show unique stock price combinations"),
    show_input_info: bool = Query(False, description="Return input parameters used in the calculation"),
    rounding: int = Query(4, description="Number of decimals to round the results to")
):
    """
    특정 주식들의 이항 모델 기반 주가 시뮬레이션(Stock Price Simulation)을 계산하는 API
    """
    try:
        tickers = symbols.split(",")  # 쉼표로 구분된 문자열을 리스트로 변환
        logger.info(f"Received request for tickers: {tickers}")

        # Toolkit 객체 생성
        toolkit = Toolkit(tickers, api_key=settings.API_KEY)

        # 주가 시뮬레이션 실행
        stock_simulation = toolkit.options.get_stock_price_simulation(
            start_date=start_date,
            time_to_expiration=time_to_expiration,
            timesteps=timesteps,
            risk_free_rate=risk_free_rate,
            show_unique_combinations=show_unique_combinations,
            show_input_info=show_input_info,
            rounding=rounding
        )

        # DataFrame 로깅
        logger.info(f"Raw Stock Price Simulation DataFrame:\n{stock_simulation}")

        # 특정 티커의 데이터를 추출
        result = stock_simulation.loc[tickers].reset_index()

        # 날짜 컬럼이 존재하면 문자열 변환
        result.columns = [str(col) for col in result.columns]

        # ⚠️ NaN, inf, -inf 값을 None으로 변환
        result = result.replace([np.inf, -np.inf, np.nan], None)

        # 변환된 DataFrame 로깅
        logger.info(f"Processed DataFrame:\n{result}")

        # JSON 변환
        json_result = result.to_dict(orient="records")  # 리스트 형태로 변환

        # 최종 JSON 로깅
        logger.info(f"Final JSON response: {json_result}")

        return jsonable_encoder(json_result)

    except Exception as e:
        logger.error(f"Error in get_stock_price_simulation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/technical-module")
async def get_average_directional_index(symbols: list[str] = Query(...), period: str = "weekly"):
    """
    여러 개의 주식 심볼에 대한 평균 방향성 지수(ADX) 조회

    :param symbols: 조회할 주식 티커 목록 (예: AAPL, TSLA, MSFT)
    :param period: 분석 기간 (daily, weekly, quarterly, yearly)
    :return: 각 주식 심볼의 ADX 값
    """
    valid_periods = ["daily", "weekly", "quarterly", "yearly"]
    if period not in valid_periods:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 period 값입니다. 사용 가능: {valid_periods}")

    try:
        toolkit = Toolkit(symbols, api_key=settings.API_KEY)
        adx_data = toolkit.technicals.get_average_directional_index(period=period)

        # 🔍 ADX 데이터 확인 로그
        logger.info(f"ADX Data Retrieved: {adx_data}")

        # 데이터가 비어 있는 경우 오류 반환
        if adx_data.empty:
            logger.warning("ADX 데이터가 존재하지 않음. 데이터 부족 가능.")
            raise HTTPException(status_code=404, detail="ADX 데이터를 찾을 수 없습니다. 데이터가 부족할 수 있습니다.")

        result = {symbol: adx_data[symbol].tolist() if symbol in adx_data else "ADX 데이터 없음" for symbol in symbols}
        return result
    except Exception as e:
        logger.error(f"ADX 데이터 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"ADX 데이터를 가져오는 중 오류 발생: {str(e)}")

@router.get("/dividends/growth")
async def get_dividend_growth_stocks():
    await run_dividend_growth_pipeline()
    return {"status": "Dividends Growth Stocks 메시지 전송 완료!"}

@router.get("/monitor/treasury")
async def treasury_monitor():
    await run_treasury_monitor_pipeline()
    return {"status": "Treasury Rates 모니터링 완료!"}

@router.get("/monitor/economics")
async def economics_monitor():
    await run_economic_monitor_pipeline()
    return {"status": "Economic Indicators 모니터링 완료!"}

@router.get("/portfolio/rebalance")
async def rebalance_portfolio():
    await run_portfolio_rebalance_pipeline(file_path="portfolio.csv")
    return {"status": "Portfolio Rebalancing Report Sent"}

@router.get("/report/generate")
async def generate_report():
    try:
        logger.info("🚀 [generate_report] 리포트 생성 시작")

        # 1️⃣ 종목 스크리닝 추천 결과 가져오기
        logger.info("🔍 종목 스크리닝 결과 가져오기 시작")
        screening_data = await run_pipeline_for_report()
        # if not screening_data or screening_data.get("count", 0) == 0:
        #     raise HTTPException(status_code=400, detail="2차 필터 통과 종목 없음: 리포트 생성 불가")

        screening_results = screening_data.get("results", [])
        logger.info(f"✅ 스크리닝 결과 {len(screening_results)}개")

        # 2️⃣ 포트폴리오 리밸런싱 계산
        logger.info("📈 포트폴리오 리밸런싱 계산 시작")
        rebalance_df, portfolio_summary = await rebalance_portfolio_for_report(file_path="portfolio.csv")
        owned_symbols = set(rebalance_df["symbol"])

        portfolio_rebalancing = []
        for _, row in rebalance_df.iterrows():
            portfolio_rebalancing.append({
                "symbol": row['symbol'],
                "current_price": row['current_price'],
                "target_allocation": row['target_allocation'],
                "current_allocation": row['current_allocation'],
                "recommendation": f"{'매수' if row['target_allocation'] > row['current_allocation'] else '매도'} {abs(row['quantity_diff'])}주"
            })
        logger.info(f"✅ 포트폴리오 리밸런싱 {len(portfolio_rebalancing)}개")

        # 3️⃣ 신규 종목 추천 리스트 (보유 중인 종목 제외)
        logger.info("🆕 신규 종목 추천 리스트 생성")
        stock_recommendations = []
        for stock in screening_results:
            if stock["symbol"] not in owned_symbols:
                stock_recommendations.append({
                    "symbol": stock["symbol"],
                    "score": stock.get("score", "N/A"),
                    "dcf_chart_path": stock.get("dcf_chart_path", ""),
                    "gpt_summary": stock.get("gpt_summary", "요약 데이터 없음")
                })
        logger.info(f"✅ 신규 추천 종목 {len(stock_recommendations)}개")

        # 4️⃣ 경제지표 요약
        logger.info("🌍 경제지표 요약 데이터 수집")
        economic_summary = await get_latest_economic_indicators()
        logger.info(f"✅ 경제지표 수집 완료")

        # 5️⃣ 리포트 파일명 및 경로
        report_name = f"{datetime.now().strftime('%Y%m%d')}_investment_report.pdf"
        output_path = f"reports/{report_name}"

        # 6️⃣ PDF 리포트 생성
        logger.info("📄 PDF 리포트 생성 시작")
        generate_investment_report(stock_recommendations, portfolio_rebalancing, portfolio_summary, economic_summary, output_path)
        logger.info(f"✅ PDF 리포트 저장 완료: {output_path}")

        # 7️⃣ Telegram 전송 (선택적)
        logger.info("✉️ Telegram 리포트 전송 시작")
        await notify_telegram(message="📄 투자 리포트 자동 생성 완료", file_path=output_path)
        logger.info("✅ Telegram 리포트 전송 완료")

        return FileResponse(path=output_path, filename=report_name, media_type='application/pdf')

    except HTTPException as http_exc:
        logger.error(f"❌ [HTTPException] {http_exc.detail}")
        raise http_exc

    except Exception as e:
        logger.error(f"❌ [generate_report] 전체 실패: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="투자 리포트 생성 중 내부 서버 오류 발생")