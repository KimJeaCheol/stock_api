import logging

import talib as ta
import yfinance as yf

from app.celery.celery import celery_app  # 기존 Celery 설정을 가져옴

logger = logging.getLogger(__name__)

@celery_app.task
def analyze_candlestick_patterns(symbol: str):
    data = yf.download(symbol, period='1d', interval='1m')
    hammer = ta.CDLHAMMER(data['Open'], data['High'], data['Low'], data['Close'])
    shooting_star = ta.CDLSHOOTINGSTAR(data['Open'], data['High'], data['Low'], data['Close'])
    doji = ta.CDLDOJI(data['Open'], data['High'], data['Low'], data['Close'])

    patterns = {
        "Hammer": hammer.tolist(),
        "Shooting Star": shooting_star.tolist(),
        "Doji": doji.tolist(),
    }

    return patterns

@celery_app.task
def analyze_trend(symbol: str):
    data = yf.download(symbol, period='1d', interval='1m')
    data['MA50'] = ta.SMA(data['Close'], timeperiod=50)
    data['MA200'] = ta.SMA(data['Close'], timeperiod=200)
    data['RSI'] = ta.RSI(data['Close'], timeperiod=14)
    data['MACD'], data['MACDSignal'], data['MACDHist'] = ta.MACD(data['Close'])

    trend = {
        "MA50": data['MA50'].iloc[-1],
        "MA200": data['MA200'].iloc[-1],
        "RSI": data['RSI'].iloc[-1],
        "MACD": data['MACD'].iloc[-1],
        "Signal": data['MACDSignal'].iloc[-1]
    }

    return trend

@celery_app.task
def generate_trade_signal(symbol: str):
    patterns = analyze_candlestick_patterns(symbol)
    trend = analyze_trend(symbol)

    if patterns['Hammer'][-1] > 0 and trend['RSI'] < 30:
        return "Buy Signal"
    elif patterns['Shooting Star'][-1] > 0 and trend['RSI'] > 70:
        return "Sell Signal"
    else:
        return "Hold"
    
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
