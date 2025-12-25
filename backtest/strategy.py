
from core.indicators import Indicators

class BaseStrategy:
    def __init__(self, data):
        self.data = data
        self.signals = []

    def generate_signals(self):
        raise NotImplementedError("generate_signals() must be implemented by subclass")

class ValueStrategy(BaseStrategy):
    def __init__(self, data):
        super().__init__(data)

    def generate_signals(self):
        df = self.data.copy()
        df['signal'] = 0
        df.loc[df.index[0], "signal"] = 1
        df.loc[df.index[-1], "signal"] = -1
        return df

class EMACrossStrategy(BaseStrategy):
    def __init__(self, data, short=12, long=26):
        super().__init__(data)
        self.short = short
        self.long = long

    def generate_signals(self):
        df = self.data.copy()
        df['ema_short'] = Indicators.ema(df, self.short)
        df['ema_long'] = Indicators.ema(df, self.long)
        df['signal'] = 0
        df.loc[df['ema_short'] > df['ema_long'], 'signal'] = 1
        df.loc[df['ema_short'] < df['ema_long'], 'signal'] = -1
        self.signals = df
        return df

class LLMStrategy(BaseStrategy):
    def __init__(self, data, buy_score=0.7, sell_score=0.0):
        super().__init__(data)
        self.buy_score = buy_score
        self.sell_score = sell_score

    def generate_signals(self):
        df = self.data.copy()
        df['signal'] = 0
        df.loc[df['score'] >= self.buy_score, 'signal'] = 1
        df.loc[df['score'] < self.sell_score, 'signal'] = -1
        self.signals = df
        return df

