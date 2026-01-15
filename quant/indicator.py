import talib
import pandas as pd

class IndicatorCalculator:
    # 统一参数默认值
    DEFAULTS = {
        'ema_short': 12, 'ema_long': 26, 'macd_signal': 9,
        'rsi_period': 14, 'kdj_period': 9, 'bb_period': 20, 'atr_period': 14,
        'decimal_places': 2
    }

    @classmethod
    def calc_ema_macd(cls, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """基础计算：处理排序、校验并计算 EMA 和 MACD"""
        p = {**cls.DEFAULTS, **kwargs}
        required = ['date', 'close']
        if any(col not in df.columns for col in required):
            raise ValueError(f"Missing columns: {required}")
        df = df.sort_values(by="date", ascending=True).reset_index(drop=True) 
        
        # ema_short, ema_long, macd, signal, hist
        df["ema_short"] = talib.EMA(df["close"], p['ema_short'])
        df["ema_long"] = talib.EMA(df["close"], p['ema_long'])
        df["macd"], df["signal"], df["hist"] = talib.MACD(
            df["close"], p['ema_short'], p['ema_long'], p['macd_signal']
        )
        return df.round(p['decimal_places'])

    @classmethod
    def calc_ema_macd_kdj_boll(cls, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """扩展计算：复用 EMA/MACD 结果并追加其他指标"""
        p = {**cls.DEFAULTS, **kwargs}
        # 1. 校验需要的列
        if not {'high', 'low', 'date'}.issubset(df.columns):
            raise ValueError("High/Low columns required for KDJ/ATR/BOLL")
        df = df.sort_values(by="date", ascending=True).reset_index(drop=True)

        # 2. EMA, MACD
        df = cls.calc_ema_macd(df, **p)
        
        close, high, low = df["close"], df["high"], df["low"]
        
        # 3. RSI, ATR
        df["rsi"] = talib.RSI(close, p['rsi_period'])
        df["atr"] = talib.ATR(high, low, close, p['atr_period'])
        
        # KDJ
        df["kdj_k"], df["kdj_d"] = talib.STOCH(
            high, low, close, 
            fastk_period=p['kdj_period'], slowk_period=3, slowd_period=3
        )
        df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]

        # Bollinger
        df["bb_upper"], df["bb_mid"], df["bb_lower"] = talib.BBANDS(
            close, timeperiod=p['bb_period'], nbdevup=2, nbdevdn=2
        )

        return df.round(p['decimal_places'])

