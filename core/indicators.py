import pandas as pd
import numpy as np

class Indicators:
    @staticmethod
    def ema(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
        """计算指数移动平均线"""
        return df[column].ewm(span=period, adjust=False).mean()

    @staticmethod
    def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
        """
        计算 MACD 指标
        """
        ema_f = Indicators.ema(df, fast)
        ema_s = Indicators.ema(df, slow)
        
        macd_line = ema_f - ema_s
        # 信号线是对 MACD 线进行的 EMA
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        
        return macd_line, signal_line, hist

    @staticmethod
    def rsi(df: pd.DataFrame, period: int = 14, column: str = 'close') -> pd.Series:
        """
        计算 RSI 指标 (Wilder's Smoothing 版本):指数加权平均(com=period-1)
        """
        delta = df[column].diff()
        
        # 这里的 alpha = 1 / period
        up = delta.clip(lower=0)
        down = -delta.clip(upper=0)
        
        # 标准 RSI 使用的是 Wilder's Smoothing (EWM 的变体)
        ma_up = up.ewm(com=period - 1, adjust=False).mean()
        ma_down = down.ewm(com=period - 1, adjust=False).mean()
        
        # 计算相对强度 RS
        rs = ma_up / ma_down.replace(0, np.nan) # 防止除以0
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.fillna(50) # 填充初始 NaN 值
