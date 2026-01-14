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
        
        return rsi.fillna(50) # 默认填充 50 中性值

    @staticmethod
    def bbands(df: pd.DataFrame, period: int = 20, std_dev: int = 2, column: str = 'close'):
        """
        计算布林带 (Bollinger Bands)
        返回: (中轨, 上轨, 下轨)
        """
        mid = df[column].rolling(window=period, min_periods=1).mean()
        std = df[column].rolling(window=period, min_periods=1).std()
        
        upper = mid + (std * std_dev)
        lower = mid - (std * std_dev)
        
        return mid, upper.fillna(mid), lower.fillna(mid)

    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14):
        """
        计算平均真实波幅 (Average True Range)
        用途：用于设置波动率止损或计算头寸大小
        """
        high, low, prev_close = df['high'], df['low'], df['close'].shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        # ATR 应该使用 Wilder 的平滑方式 (alpha=1/N)
        return tr.ewm(alpha=1/period, adjust=False).mean().ffill()
        return tr.rolling(window=period).mean()

    @staticmethod
    def kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3):
        """
        计算 KDJ 指标
        返回: (K值, D值, J值)
        """
        low_list = df['low'].rolling(window=n, min_periods=1).min()
        high_list = df['high'].rolling(window=n, min_periods=1).max()
        
        # 计算 RSV
        rsv = (df['close'] - low_list) / (high_list - low_list) * 100
        # 如果 diff 为 0，通常 RSV 维持在 50
        rsv = rsv.fillna(50)       
 
        # K, D 分别是 RSV 和 K 的 EMA
        k = rsv.ewm(com=m1-1, adjust=False).mean()
        d = k.ewm(com=m2-1, adjust=False).mean()
        j = 3 * k - 2 * d
        
        return k, d, j
