

import talib as ta
import yfinance as yf

from app.core.celery_app import celery_app
from app.core.logging import logger  # 이미 설정된 logger import


def get_celery_app():
    """Celery 애플리케이션을 Lazy Import로 가져오기"""
    from app.core.celery_app import celery_app  # ✅ 함수 내부에서 Import
    return celery_app

@celery_app.task
def analyze_candlestick_patterns(symbol: str):
    try:
        data = yf.download(symbol, period='1d', interval='1m')

        if data.empty:
            logger.warning(f"No data found for {symbol}")
            return {"error": "No data available"}

        hammer = ta.CDLHAMMER(data['Open'], data['High'], data['Low'], data['Close'])
        shooting_star = ta.CDLSHOOTINGSTAR(data['Open'], data['High'], data['Low'], data['Close'])
        doji = ta.CDLDOJI(data['Open'], data['High'], data['Low'], data['Close'])

        patterns = {
            "Hammer": hammer.tolist(),
            "Shooting Star": shooting_star.tolist(),
            "Doji": doji.tolist(),
        }

        return patterns

    except Exception as e:
        logger.error(f"Error in analyze_candlestick_patterns for {symbol}: {e}")
        return {"error": str(e)}


@celery_app.task
def analyze_trend(symbol: str):
    try:
        data = yf.download(symbol, period='1d', interval='1m')

        if data.empty:
            logger.warning(f"No data found for {symbol}")
            return {"error": "No data available"}

        data['MA50'] = ta.SMA(data['Close'], timeperiod=50)
        data['MA200'] = ta.SMA(data['Close'], timeperiod=200)
        data['RSI'] = ta.RSI(data['Close'], timeperiod=14)
        data['MACD'], data['MACDSignal'], data['MACDHist'] = ta.MACD(data['Close'])

        trend = {
            "MA50": data['MA50'].iloc[-1] if not data['MA50'].isna().all() else None,
            "MA200": data['MA200'].iloc[-1] if not data['MA200'].isna().all() else None,
            "RSI": data['RSI'].iloc[-1] if not data['RSI'].isna().all() else None,
            "MACD": data['MACD'].iloc[-1] if not data['MACD'].isna().all() else None,
            "Signal": data['MACDSignal'].iloc[-1] if not data['MACDSignal'].isna().all() else None
        }

        return trend

    except Exception as e:
        logger.error(f"Error in analyze_trend for {symbol}: {e}")
        return {"error": str(e)}


@celery_app.task
def generate_trade_signal(symbol: str):
    try:
        patterns = analyze_candlestick_patterns(symbol)
        trend = analyze_trend(symbol)

        if "error" in patterns or "error" in trend:
            return {"error": "Analysis failed", "patterns": patterns, "trend": trend}

        if patterns["Hammer"] and isinstance(patterns["Hammer"], list) and patterns["Hammer"][-1] > 0 and trend["RSI"] < 30:
            return "Buy Signal"
        elif patterns["Shooting Star"] and isinstance(patterns["Shooting Star"], list) and patterns["Shooting Star"][-1] > 0 and trend["RSI"] > 70:
            return "Sell Signal"
        else:
            return "Hold"

    except Exception as e:
        logger.error(f"Error in generate_trade_signal for {symbol}: {e}")
        return {"error": str(e)}

    
@celery_app.task
def backtest_strategy(symbol: str, strategy_params: dict):
    data = yf.download(symbol, start=strategy_params['start_date'], end=strategy_params['end_date'])
    data['MA'] = ta.SMA(data['Close'], timeperiod=strategy_params['ma_period'])
    data['Signal'] = data['Close'] > data['MA']

    returns = data['Close'].pct_change()
    strategy_returns = returns[data['Signal'].shift(1)]

    performance = {
        "total_return": (strategy_returns + 1).prod() - 1,
        "average_return": strategy_returns.mean(),
        "volatility": strategy_returns.std()
    }

    return performance

@celery_app.task
def manage_risk(symbol: str, risk_params: dict):
    data = yf.download(symbol, period='1d', interval='1m')
    current_price = data['Close'].iloc[-1]
    if current_price <= risk_params['stop_loss']:
        return "Sell Signal: Stop Loss Triggered"
    elif current_price >= risk_params['target_price']:
        return "Sell Signal: Target Price Reached"
    else:
        return "Hold"
    
@celery_app.task
def fetch_stock_data(symbol: str = "AAPL"):
    data = yf.download(symbol, period="1d", interval="1m")
    return data
