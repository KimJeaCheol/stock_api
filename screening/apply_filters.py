# screening/apply_filters.py
import logging

from utils.fmp_api import get_key_metrics_ttm, get_ratios_ttm

logger = logging.getLogger(__name__)

async def apply_filters(symbols: list, advanced_filter: dict) -> list:
    passed = []

    for symbol in symbols:
        try:
            ratios_list = await get_ratios_ttm(symbol)
            key_metrics_list = await get_key_metrics_ttm(symbol)
            logger.info(f"{symbol} ratios_list: {ratios_list}")
            logger.info(f"{symbol} key_metrics_list: {key_metrics_list}")

            if not ratios_list or not key_metrics_list:
                continue

            ratios = ratios_list[0]
            key_metrics = key_metrics_list[0]

            passed_flag = True
            for key, (op, value) in advanced_filter.items():
                # ROE 관련이면 key_metrics에서 가져오고
                if key == "returnOnEquityTTM":
                    actual = key_metrics.get(key)
                else:
                    actual = ratios.get(key)

                if actual is None:
                    passed_flag = False
                    logger.info(f"❌ {symbol}: {key} 데이터 없음")                    
                    break

                if op == ">" and not actual > value:
                    passed_flag = False
                    logger.info(f"❌ {symbol}: {key} {actual} <= {value}")
                    break
                if op == "<" and not actual < value:
                    passed_flag = False
                    logger.info(f"❌ {symbol}: {key} {actual} >= {value}")
                    break

            if passed_flag:
                passed.append(symbol)

        except Exception as e:
            logger.error(f"❌ {symbol} 필터링 중 오류: {e}")
            continue  # 하나 오류 나도 스킵하고 계속

    return passed