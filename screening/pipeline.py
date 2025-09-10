# screening/pipeline.py
import asyncio
import datetime
import logging

from config.advanced_filters import ADVANCED_FILTERS
from config.screening_rules import WEEKLY_SCREENING_RULES
from screening.apply_filters import apply_filters
from screening.dividends_filter import fetch_dividend_growth_stocks
from screening.fetch_candidates import fetch_candidates
from utils.fetch_fmp_data import fetch_fmp_data
from utils.formatter import (format_dividend_growth_message,
                             format_telegram_message)
from utils.gpt_summary import gpt_analyze
from utils.notifier import notify_telegram
from utils.scoring import score_stock
from utils.visualizer import visualize_dcf_time_series

logger = logging.getLogger(__name__)

async def run_pipeline():
    # 현재 요일 가져오기
    today = datetime.datetime.now().strftime("%A").lower()

    base_filters = WEEKLY_SCREENING_RULES.get(today)
    advanced_filter = ADVANCED_FILTERS.get(today)
    logger.info(f"오늘 요일: {today}, 기본 필터: {base_filters}, 고급 필터: {advanced_filter}")
    
    if not base_filters or not advanced_filter:
        logger.error(f"⚠️ 오늘 요일({today})에 해당하는 스크리닝 룰이 없습니다.")
        return {"error": "스크리닝 룰 없음"}
    
    # 1차 필터: 기본 스크리너 필터
    symbols = await fetch_candidates(base_filters)
    if not symbols:
        logger.error("⚠️ 1차 필터 통과한 심볼 없음")
        return {"error": "후보 심볼 없음"}
    logger.info(f"1차 필터 통과 심볼: {symbols}")

    # 2차 필터: 고급 재무 비율 필터
    filtered_symbols = await apply_filters(symbols, advanced_filter)
    if not filtered_symbols:
        logger.error("⚠️ 2차 필터 통과한 심볼 없음")
        return {"error": "고급 필터 통과 심볼 없음"}
    logger.info(f"2차 필터 통과 심볼: {filtered_symbols}")
    # 종목별 처리
    results = []

    async def process_symbol(symbol):
        try:
            data = await fetch_fmp_data(symbol)

            if "error" in data:
                logger.warning(f"⚠️ 데이터 수집 실패: {symbol}")
                return

            score = score_stock(data)
            summary = await gpt_analyze(data)

            result = {
                "symbol": symbol,
                "score": score,
                "dcf_value": data.get("dcf_value", 0),
                "current_price": data.get("profile", {}).get("price", 0),
                "summary": summary
            }
            results.append(result)

            # 텔레그램 전송
            message = format_telegram_message(data)
            message += f"\n🧠 GPT 분석 요약:\n{summary}\n점수: {score}/17"
            await notify_telegram(message, save_path=data.get("save_path"))

        except Exception as e:
            logger.error(f"❌ {symbol} 처리 실패: {e}")

    tasks = [process_symbol(symbol) for symbol in filtered_symbols]
    await asyncio.gather(*tasks)

    return {"count": len(results), "results": results}

async def run_dividend_growth_pipeline():
    stocks = await fetch_dividend_growth_stocks(min_yield=3.0)
    message = format_dividend_growth_message(stocks)
    await notify_telegram(message)


async def run_pipeline_for_report():
    today = datetime.datetime.now().strftime("%A").lower()

    base_filters = WEEKLY_SCREENING_RULES.get(today)
    advanced_filter = ADVANCED_FILTERS.get(today)
    logger.info(f"오늘 요일: {today}, 기본 필터: {base_filters}, 고급 필터: {advanced_filter}")

    if not base_filters or not advanced_filter:
        logger.error(f"⚠️ 오늘 요일({today})에 해당하는 스크리닝 룰이 없습니다.")
        return {"error": "스크리닝 룰 없음"}

    symbols = await fetch_candidates(base_filters)
    if not symbols:
        logger.error("⚠️ 1차 필터 통과한 심볼 없음")
        return {"error": "후보 심볼 없음"}
    logger.info(f"1차 필터 통과 심볼: {symbols}")

    filtered_symbols = await apply_filters(symbols, advanced_filter)
    if not filtered_symbols:
        logger.error("⚠️ 2차 필터 통과한 심볼 없음")
        return {"error": "고급 필터 통과 심볼 없음"}
    logger.info(f"2차 필터 통과 심볼: {filtered_symbols}")

    results = []

    async def process_symbol(symbol):
        try:
            data = await fetch_fmp_data(symbol)

            if "error" in data:
                logger.warning(f"⚠️ 데이터 수집 실패: {symbol}")
                return

            score = score_stock(data)
            summary = await gpt_analyze(data)

            # 📊 DCF 차트 저장 경로 지정
            save_path = f"visualize/{symbol}_dcf_chart.png"
            
            # DCF 차트 시계열 시각화
            visualize_dcf_time_series(data.get("dcf_data"), symbol, save_path)

            result = {
                "symbol": symbol,
                "score": score,
                "dcf_value": data.get("dcf_value", 0),
                "current_price": data.get("profile", {}).get("price", 0),
                "summary": summary,
                "dcf_chart_path": save_path
            }
            results.append(result)

        except Exception as e:
            logger.error(f"❌ {symbol} 처리 실패: {e}")

    tasks = [process_symbol(symbol) for symbol in filtered_symbols]
    await asyncio.gather(*tasks)

    return {"count": len(results), "results": results}