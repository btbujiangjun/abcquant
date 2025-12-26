import pandas as pd
from core.indicators import Indicators

class BaseStrategy:
    strategy_name = "BaseStrategy"
    def __init__(self, data:pd.DataFrame):
        assert len(data) > 1, f"data len:{len(data)} must be > 1"
        assert "date" in data.columns, f"column `date` is required"
        self.data = data.copy().sort_values("date", ascending=True).reset_index(drop=True)
        self.signals = []

    def generate_signals(self):
        raise NotImplementedError("generate_signals() must be implemented by subclass")

class LongTermValueStrategy(BaseStrategy):
    strategy_name = "LongTermValueStrategy"
    def __init__(self, data):
        super().__init__(data)

    def generate_signals(self):
        df = self.data
        df['signal'] = 0
        df.loc[df.index[0], "signal"] = 1
        df.loc[df.index[-1], "signal"] = -1
        return df

class EMACrossStrategy(BaseStrategy):
    strategy_name = "EMACrossStrategy"
    def __init__(self, data, short=12, long=26):
        super().__init__(data)
        assert long > short, f"long:{long} must be > short:{short}"
        assert "close" in data.columns, f"`close` filed is required"
        self.short = short
        self.long = long

    def generate_signals(self):
        df = self.data
        df['ema_short'] = Indicators.ema(df, self.short)
        df['ema_long'] = Indicators.ema(df, self.long)
        df['signal'] = 0
        df.loc[df['ema_short'] > df['ema_long'], 'signal'] = 1
        df.loc[df['ema_short'] < df['ema_long'], 'signal'] = -1
        self.signals = df
        return df

class LLMStrategy(BaseStrategy):
    strategy_name = "LLMStrategy"
    def __init__(self, data, buy_score=0.7, sell_score=0.0):
        super().__init__(data)
        assert buy_score > sell_score, f"buy_score:{buy_score} must be > sell_score:{sell_score}"
        assert "score" in data.columns, f"`score` filed is required"
        self.buy_score = buy_score
        self.sell_score = sell_score

    def generate_signals(self):
        df = self.data
        df['signal'] = 0
        df.loc[df['score'] >= self.buy_score, 'signal'] = 1
        df.loc[df['score'] <= self.sell_score, 'signal'] = -1
        self.signals = df
        return df

