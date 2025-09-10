# utils/fetch_fmp_data.py
import asyncio
import os

from utils.fmp_api import (get_balance_sheet_statement,
                           get_cash_flow_statement, get_company_profile,
                           get_custom_dcf_valuation, get_financial_scores,
                           get_income_statement, get_key_metrics_ttm,
                           get_ratings_snapshot, get_ratios, get_ratios_ttm)
from utils.visualizer import visualize_dcf_time_series

# 이미지 저장 디렉토리 (stocks_v1.py IMG_DIR 기준)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
IMG_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../img"))
os.makedirs(IMG_DIR, exist_ok=True)

async def fetch_fmp_data(symbol: str) -> dict:
    try:
        # 📡 비동기 API 호출 준비
        profile_task = get_company_profile(symbol)
        ratios_ttm_task = get_ratios_ttm(symbol)
        ratios_task = get_ratios(symbol)
        key_metrics_ttm_task = get_key_metrics_ttm(symbol)
        dcf_task = get_custom_dcf_valuation(symbol)
        ratings_task = get_ratings_snapshot(symbol)
        scores_task = get_financial_scores(symbol)
        income_task = get_income_statement(symbol)
        cashflow_task = get_cash_flow_statement(symbol)
        balance_task = get_balance_sheet_statement(symbol)

        # 🧠 병렬 실행
        (
            profile,
            ratios_ttm,
            ratios,
            key_metrics_ttm,
            dcf_data,
            ratings,
            scores,
            income_statement,
            cash_flow,
            balance_sheet
        ) = await asyncio.gather(
            profile_task,
            ratios_ttm_task,
            ratios_task,
            key_metrics_ttm_task,
            dcf_task,
            ratings_task,
            scores_task,
            income_task,
            cashflow_task,
            balance_task
        )

        # ✅ DCF 데이터 중 최신 연도 추출
        dcf_sorted = sorted(dcf_data, key=lambda x: str(x.get("year", "0000")))
        dcf_latest = dcf_sorted[-1] if dcf_sorted else {}
        dcf_value = dcf_latest.get("equityValuePerShare", 0)

        # ✅ 차트 이미지 저장
        save_path = os.path.join(IMG_DIR, f"{symbol}.png")
        visualize_dcf_time_series(dcf_data, symbol, save_path)

        # 📦 통합 데이터 반환
        return {
            "symbol": symbol,
            "profile": profile[0] if profile else {},
            "ratios_ttm": ratios_ttm[0] if ratios_ttm else {},
            "ratios": ratios[0] if ratios else {},
            "key_metrics_ttm": key_metrics_ttm[0] if key_metrics_ttm else {},
            "dcf": dcf_latest,
            "ratings": ratings[0] if ratings else {},
            "scores": scores[0] if scores else {},
            "income_statement": income_statement[0] if income_statement else {},
            "cash_flow": cash_flow[0] if cash_flow else {},
            "balance_sheet": balance_sheet[0] if balance_sheet else {},
            "dcf_value": dcf_value,
            "save_path": save_path,
        }

    except Exception as e:
        return {"symbol": symbol, "error": str(e)}
