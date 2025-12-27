import pandas as pd
import numpy as np
from core.indicators import Indicators

class BaseStrategy:
    strategy_name = "BaseStrategy"

    def __init__(self, data: pd.DataFrame):
        if data is None or len(data) < 2:
            raise ValueError(f"Data length must be > 1")
        if "date" not in data.columns:
            raise KeyError("Column `date` is required")
            
        self.data = data.sort_values("date").reset_index(drop=True)
        self.signals = None

    def generate_signals(self) -> pd.DataFrame:
        raise NotImplementedError("Subclasses must implement generate_signals()")

class LongTermValueStrategy(BaseStrategy):
    """长期持有策略：第一天买入，最后一天卖出"""
    strategy_name = "LongTermValueStrategy"

    def generate_signals(self):
        df = self.data.copy()
        df['signal'] = 0
        df.at[df.index[0], "signal"] = 1
        df.at[df.index[-1], "signal"] = -1
        self.signals = df
        return df

class EMACrossStrategy(BaseStrategy):
    """EMA 交叉策略：金叉买入，死叉卖出"""
    strategy_name = "EMACrossStrategy"

    def __init__(self, data, short=12, long=26):
        super().__init__(data)
        if "close" not in data.columns:
            raise KeyError("`close` field is required")
        self.short = short
        self.long = long

    def generate_signals(self):
        df = self.data.copy()
        ema_s = Indicators.ema(df, self.short)
        ema_l = Indicators.ema(df, self.long)
        
        conditions = [
            (ema_s > ema_l),
            (ema_s < ema_l)
        ]
        choices = [1, -1]
        df['signal'] = np.select(conditions, choices, default=0)
        
        # 进阶优化：如果只想在“交叉”瞬间发出信号（避免持续信号）
        # df['signal'] = df['signal'].diff().fillna(0) 
        
        self.signals = df
        return df

class LLMStrategy(BaseStrategy):
    """基于大模型评分的策略"""
    strategy_name = "LLMStrategy"

    def __init__(self, data, buy_score=0.7, sell_score=0.0): 
        super().__init__(data)
        if "score" not in data.columns:
            raise KeyError("`score` field is required")
        self.buy_score = buy_score
        self.sell_score = sell_score

    def generate_signals(self):
        df = self.data.copy()
        df['signal'] = np.where(df['score'] >= self.buy_score, 1, 
                       np.where(df['score'] <= self.sell_score, -1, 0))
        
        self.signals = df
        return df

