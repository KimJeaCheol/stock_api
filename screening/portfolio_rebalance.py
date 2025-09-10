import asyncio
import logging
import traceback

import pandas as pd

from utils.fmp_api import get_stock_quote
from utils.notifier import notify_telegram

logger = logging.getLogger(__name__)

REBALANCE_THRESHOLD = 5  # 허용 오차 5%

async def run_portfolio_rebalance_pipeline(file_path: str = "portfolio.csv"):
    # 1. 포트폴리오 로드
    df = pd.read_csv(file_path)

    # 2. 현재가 가져오기
    prices = {}
    for symbol in df["symbol"]:
        quote = await get_stock_quote(symbol)
        price = quote.get("price", 0)
        if not price:
            logger.warning(f"⚠️ 가격 정보 없음: {symbol}")
        prices[symbol] = price

    # 3. 평가액 계산
    df["current_price"] = df["symbol"].apply(lambda x: prices.get(x, 0))
    df["market_value"] = df["quantity"] * df["current_price"]

    total_value = df["market_value"].sum()
    df["current_allocation"] = (df["market_value"] / total_value) * 100

    # 4. 리밸런싱 필요 여부 계산
    df["rebalance"] = df.apply(
        lambda row: needs_rebalancing(row["current_allocation"], row["target_allocation"]),
        axis=1
    )

    # 5. 리밸런싱이 필요한 종목 리스트업
    rebalance_df = df[df["rebalance"]]

    if rebalance_df.empty:
        message = "✅ 현재 포트폴리오는 리밸런싱이 필요 없습니다."
    else:
        message = "🔄 *포트폴리오 리밸런싱 추천 종목:*\n\n"
        for _, row in rebalance_df.iterrows():
            action = "매도" if row["current_allocation"] > row["target_allocation"] else "매수"
            target_value = (row["target_allocation"] / 100) * total_value
            current_value = row["market_value"]
            value_diff = target_value - current_value
            quantity_diff = int(value_diff // row["current_price"])  # 매수/매도 수량

            message += (
                f"🔹 {row['symbol']}\n"
                f" - 현재 비중: {row['current_allocation']:.2f}%\n"
                f" - 목표 비중: {row['target_allocation']}%\n"
                f" - 현재가: ${row['current_price']}\n"
                f" - 추천: {action} {abs(quantity_diff)}주\n\n"
            )

    # 6. Telegram 알림
    await notify_telegram(message)


async def rebalance_portfolio_for_report(file_path: str = "portfolio.csv") -> pd.DataFrame:
    try:
        logger.info(f"🔍 포트폴리오 파일 로드: {file_path}")
        df = pd.read_csv(file_path)

        logger.info(f"📈 심볼 목록: {df['symbol'].tolist()}")

        prices = {}
        for symbol in df["symbol"]:
            try:
                logger.info(f"💬 {symbol} 현재가 조회 시작")
                data = await get_stock_quote(symbol)
                logger.debug(f"📦 {symbol} 조회 결과: {data}")

                price = data.get("price", 0)
                if not price:
                    logger.warning(f"⚠️ {symbol}: 현재가 조회 실패 또는 0")
                prices[symbol] = price

            except Exception as e:
                logger.error(f"❌ {symbol} 가격 조회 중 오류 발생: {e}\n{traceback.format_exc()}")
                prices[symbol] = 0  # 실패해도 0으로 설정하고 계속 진행

        # DataFrame 컬럼 계산
        logger.info("🧮 포트폴리오 현재가, 평가액 계산 중")
        df["current_price"] = df["symbol"].apply(lambda x: prices.get(x, 0))
        df["market_value"] = df["quantity"] * df["current_price"]

        total_value = df["market_value"].sum()
        if total_value == 0:
            raise ValueError("포트폴리오 총 평가액이 0입니다. 가격 조회 실패 확인 필요.")

        df["current_allocation"] = (df["market_value"] / total_value) * 100

        df["rebalance"] = df.apply(
            lambda row: needs_rebalancing(row["current_allocation"], row["target_allocation"]),
            axis=1
        )

        df["target_market_value"] = (df["target_allocation"] / 100) * total_value
        df["quantity_diff"] = ((df["target_market_value"] - df["market_value"]) / df["current_price"]).round().astype(int)

        # ✅ 포트폴리오 요약 계산 추가
        portfolio_df = pd.read_csv(file_path)
        total_investment = (portfolio_df["quantity"] * portfolio_df["avg_buy_price"]).sum()
        total_return = ((total_value - total_investment) / total_investment) * 100

        portfolio_summary = {
            "total_investment": total_investment,
            "total_value": total_value,
            "total_return": total_return
        }

        logger.info("✅ 포트폴리오 리밸런싱 계산 완료")

        return df, portfolio_summary

    except Exception as e:
        logger.error(f"❌ 포트폴리오 리밸런싱 중 전체 오류 발생: {e}\n{traceback.format_exc()}")
        raise

def needs_rebalancing(current_weight, target_weight, threshold=5):
    return abs(current_weight - target_weight) > threshold
