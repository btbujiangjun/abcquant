import talib
import pandas as pd

class IndicatorCalculator:
    @staticmethod
    def calc_ema_macd(
        df: pd.DataFrame, 
        ema_short=12, 
        ema_long=26, 
        macd_signal=9,
        decimal_places=2,
    ) -> pd.DataFrame:
        min_rows = max([ema_short, ema_long, macd_signal])
        if len(df) < min_rows:
            raise ValueError(f"Not enough rows:{len(df)}/{min_rows}")
        required_columns = ['date', 'close']
        if any(col not in df.columns for col in required_columns):
            raise ValueError(f"Filed {required_columns} is required")        

        df = df.sort_values(by="date", ascending=True).reset_index(drop=True)
        df["ema_short"] = talib.EMA(df["close"], timeperiod=ema_short)
        df["ema_long"] = talib.EMA(df["close"], timeperiod=ema_long)
        df["macd"], df["signal"], df["hist"] = talib.MACD(
            df["close"], 
            fastperiod=ema_short, 
            slowperiod=ema_long, 
            signalperiod=macd_signal
        )

        return df.round(decimal_places)

    @staticmethod
    def calc_ema_macd_kdj_boll(
        df: pd.DataFrame,
        ema_short=12,
        ema_long=26,
        macd_signal=9,
        rsi_period=14,
        kdj_period=9,
        bbands_period=20,
        atr_period=14,
        decimal_places=2,
    ) -> pd.DataFrame:
        min_rows = max([ema_short, ema_long, macd_signal, rsi_period, kdj_period, bbands_period, atr_period])
        if len(df) < min_rows:
            raise ValueError(f"Not enough rows:{len(df)}/{min_rows}")
        required_columns = ['date', 'high', 'low', 'close']
        if any(col not in df.columns for col in required_columns):
            raise ValueError(f"Filed {required_columns} is required")        

        df = df.sort_values(by="date", ascending=True).reset_index(drop=True)

        # --- EMA ---
        df["ema_short"] = talib.EMA(df["close"], timeperiod=ema_short)
        df["ema_long"] = talib.EMA(df["close"], timeperiod=ema_long)

        # --- MACD ---
        df["macd"], df["signal"], df["hist"] = talib.MACD(
            df["close"],
            fastperiod=ema_short,
            slowperiod=ema_long,
            signalperiod=macd_signal,
        )

        # --- RSI ---
        df["rsi"] = talib.RSI(df["close"], timeperiod=rsi_period)

        # --- KDJ (基于 Stochastic Oscillator) ---
        df["kdj_k"], df["kdj_d"] = talib.STOCH(
            df["high"],
            df["low"],
            df["close"],
            fastk_period=kdj_period,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0,
        )
        df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]

        # --- Bollinger Bands ---
        df["bb_upper"], df["bb_mid"], df["bb_lower"] = talib.BBANDS(
            df["close"],
            timeperiod=bbands_period,
            nbdevup=2,
            nbdevdn=2,
            matype=0,
        )

        # --- ATR (平均真实波幅) ---
        df["atr"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=atr_period)

        return df.round(decimal_places)


