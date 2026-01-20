import pandas as pd

class EMACrossStrategy:
    def __init__(self, short, long):
        self.short = short
        self.long = long

    def generate_signal(self, df):
        """输入历史K线，输出信号：1买入, -1卖出, 0无动作"""
        if len(df) < self.long * 2: return 0
        
        ema_s = df['close'].ewm(span=self.short, adjust=False).mean()
        ema_l = df['close'].ewm(span=self.long, adjust=False).mean()
        
        # 金叉：快线上穿慢线
        if ema_s.iloc[-1] > ema_l.iloc[-1] and ema_s.iloc[-2] <= ema_l.iloc[-2]:
            return 1
        # 死叉：快线下穿慢线
        elif ema_s.iloc[-1] < ema_l.iloc[-1] and ema_s.iloc[-2] >= ema_l.iloc[-2]:
            return -1
        return 0
