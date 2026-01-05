import pandas as pd
import numpy as np
from core.indicators import Indicators

class BaseStrategy:
    strategy_class = "BaseStrategy"
    strategy_name = "基类策略"

    def __init__(self, data: pd.DataFrame):
        if data is None or len(data) < 2:
            raise ValueError(f"Data length must be > 1")
        if "date" not in data.columns:
            raise KeyError("Column `date` is required")
        self.data = data.sort_values("date").reset_index(drop=True)
        self.signals = None

    def generate_signals(self) -> pd.DataFrame:
        raise NotImplementedError("Subclasses must implement generate_signals()")

    # 动态计算仓位的逻辑建议
    def get_position_size(equity, close_price, atr, risk_per_trade=0.01):
        """
        equity: 总资产
        risk_per_trade: 每笔交易允许亏损总资产的比例 (1%)
        """
        risk_amount = equity * risk_per_trade
        stop_distance = 2.0 * atr  # 你的止损距离
        if stop_distance == 0: return 0
    
        # 买入股数 = 风险额 / 止损距离
        shares_to_buy = risk_amount / stop_distance
        return shares_to_buy

class LongTermValueStrategy(BaseStrategy):
    """长期持有策略：第一天买入，最后一天卖出"""
    strategy_class = "LongTermValueStrategy"

    def __init__(self, data):
        super().__init__(data)
    
    def generate_signals(self):
        df = self.data.copy()
        df['signal'] = 0
        df.at[df.index[0], "signal"] = 1
        #df.at[df.index[-1], "signal"] = -1
        self.signals = df
        return df

class EMACrossStrategy(BaseStrategy):
    """EMA 交叉策略：金叉买入，死叉卖出"""
    strategy_class = "EMACrossStrategy"

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
        self.signals = df
        return df

class RSIStrategy(BaseStrategy):
    """RSI 逆势策略：超跌买入，超涨卖出"""
    strategy_class = "RSIStrategy"

    def __init__(self, data, period=14, low=30, high=70):
        super().__init__(data)
        self.period = period
        self.low = low
        self.high = high

    def generate_signals(self):
        df = self.data.copy()
        # 假设 Indicators 已实现 rsi 方法
        df['rsi'] = Indicators.rsi(df, self.period)
        
        conditions = [
            (df['rsi'] < self.low),
            (df['rsi'] > self.high)
        ]
        choices = [1, -1]
        df['signal'] = np.select(conditions, choices, default=0)
        
        self.signals = df
        return df

class BollingerStrategy(BaseStrategy):
    """布林带策略：价格回归与突破"""
    strategy_class = "BollingerStrategy"

    def __init__(self, data, period=20, std_dev=2, coefficient=0.05):
        super().__init__(data)
        self.period = period
        self.std_dev = std_dev
        self.coefficient = coefficient

    def generate_signals(self):
        df = self.data.copy()
        # 计算中轨、上轨、下轨
        mid, upper, lower = Indicators.bbands(df, self.period, self.std_dev)

        # 价格低于下轨买入，高于上轨卖出
        df['signal'] = np.where(df['close'] < lower * (1 + self.coefficient), 1, 
                       np.where(df['close'] > upper * (1 - self.coefficient), -1, 0))
        
        self.signals = df
        return df

class LLMStrategy(BaseStrategy):
    """基于大模型评分的策略"""
    strategy_class = "LLMStrategy"

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

class VolatilityLLMStrategy(LLMStrategy):
    """波动率保护型 LLM 策略"""
    strategy_class = "VolLLMStrategy"

    def __init__(self, data, buy_score=0.7, sell_score=0.0, period=10, vol_threshold=0.03):
        super().__init__(data, buy_score, sell_score)
        self.buy_score = buy_score
        self.sell_score = sell_score
        self.period = period
        self.vol_threshold = vol_threshold

    def generate_signals(self):
        df = self.data.copy()
        # 计算日内波动率 (High-Low)/Close
        df['vol'] = (df['high'] - df['low']) / df['close']
        df['vol_ma'] = df['vol'].rolling(self.period).mean()

        # 信号：分数够高 且 最近波动率不太离谱
        df['signal'] = np.where((df['score'] >= self.buy_score) & (df['vol_ma'] < self.vol_threshold), 1, 
                       np.where(df['score'] <= self.sell_score, -1, 0))
        
        self.signals = df
        return df

class KeltnerStrategy(BaseStrategy):
    """肯特纳通道：结合 EMA 和 ATR 的趋势突破策略"""
    strategy_class = "KeltnerStrategy"

    def __init__(self, data, period=20, multiplier=2.0, coefficient=0.05):
        super().__init__(data)
        self.period = period
        self.multiplier = multiplier
        self.coefficient = coefficient

    def generate_signals(self):
        df = self.data.copy()
        ema = Indicators.ema(df, self.period)
        atr = Indicators.atr(df, self.period).bfill()
        
        upper = ema + (atr * self.multiplier)
        lower = ema - (atr * self.multiplier)

        # 向上突破上轨买入，跌破中轨（EMA）或下轨卖出
        df['signal'] = np.where(df['close'] > upper * (1 - self.coefficient), 1, 
                       np.where(df['close'] < ema * (1 + self.coefficient), -1, 0))
        
        self.signals = df
        return df

class VolumePriceStrategy(BaseStrategy):
    """量价共振策略：放量上涨买入，缩量或破位卖出"""
    strategy_class = "VolumePriceStrategy"

    def __init__(self, data, 
            vol_period=20, 
            price_period=10, 
            buy_vol_rate=0.5, 
            buy_price_rate=0.05, 
            sell_price_rate=-0.03):
        super().__init__(data)
        self.vol_period = vol_period
        self.price_period = price_period
        self.buy_vol_rate = buy_vol_rate
        self.buy_price_rate = buy_price_rate
        self.sell_price_rate = sell_price_rate

    def generate_signals(self):
        df = self.data.copy()
        # 计算成交量均线
        vol_ma = df['volume'].rolling(self.vol_period).mean()
        # 计算价格变化率
        price_change = df['close'].pct_change(self.price_period)

        # 信号：成交量超过平均水平 50% 且 价格处于上涨趋势
        df['signal'] = np.where((df['volume'] > vol_ma * (1 + self.buy_vol_rate)) & (price_change > self.buy_price_rate), 1, 
                       np.where(price_change < self.sell_price_rate, -1, 0))
        
        self.signals = df
        return df

class TripleBarrierLLMStrategy(LLMStrategy):
    """三重屏障 LLM：只在牛市且非超买状态下执行"""
    strategy_class = "TripleBarrierLLMStrategy"

    def __init__(self, data, buy_score=0.8, sell_score=0.0, rsi_period=14, ma_period=200, rsi_limit=70):
        super().__init__(data, buy_score, sell_score)
        self.buy_score = buy_score
        self.sell_score = sell_score
        self.ma_period = ma_period
        self.rsi_period = rsi_period
        self.rsi_limit = rsi_limit

    def generate_signals(self):
        df = self.data.copy()
        ma_long = df['close'].rolling(self.ma_period).mean()
        rsi = Indicators.rsi(df, self.rsi_period)

        # 屏障1: 价格在长线均线之上 (大趋势向上)
        # 屏障2: RSI 未达到超买区 (避开赶顶)
        # 屏障3: LLM 评分达标
        conditions = (df['close'] > ma_long) & (rsi < self.rsi_limit) & (df['score'] >= self.buy_score)
        
        df['signal'] = np.where(conditions, 1, 
                       np.where(df['score'] <= self.sell_score, -1, 0))
       
        self.signals = df
        return df

class AdaptiveVolStrategy(BaseStrategy):
    """自适应波动率：捕获从极度缩量到放量启动的瞬间"""
    strategy_class = "AdaptiveVolStrategy"

    def __init__(self, data, window=60, atr_period=14):
        super().__init__(data)
        self.window = window
        self.atr_period = atr_period

    def generate_signals(self):
        df = self.data.copy()
        # 计算 ATR 的历史百分位
        df['atr'] = Indicators.atr(df, self.atr_period)
        df['atr_rank'] = df['atr'].rolling(self.window).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1])

        # 逻辑：当 ATR 处于历史低位（地量）后开始抬头，且价格上涨
        # 这通常是“横盘结束，选择方向”的时刻
        df['signal'] = np.where((df['atr_rank'] < 0.2) & (df['close'] > df['close'].shift(1)), 1, 
                       np.where(df['atr_rank'] > 0.8, -1, 0))
        
        self.signals = df
        return df

class ATRStopLLMStrategy(LLMStrategy):
    """
    核心逻辑：
    - 入场：score >= buy_score
    - 跟踪止损：止损位 = 最高价 - n * ATR (止损位只升不降)
    - 出场：价格跌破止损位 OR score <= sell_score
    """
    strategy_class = "ATRStopLLMStrategy"

    def __init__(self, data, buy_score=0.8, sell_score=0.2, period=14, atr_multiplier=2.5):
        super().__init__(data, buy_score, sell_score)
        self.buy_score = buy_score
        self.sell_score = sell_score
        self.period = period
        self.n = atr_multiplier

    def generate_signals(self) -> pd.DataFrame:
        df = self.data.copy()
        df['atr'] = Indicators.atr(df, self.period).bfill()
        
        signals = np.zeros(len(df))
        stop_prices = np.full(len(df), np.nan) # 记录止损线用于观察
        
        in_position = False
        current_stop = 0.0

        close = df['close'].values
        scores = df['score'].values
        atrs = df['atr'].values

        for i in range(1, len(df)):
            if not in_position:
                # 检查买入条件
                if scores[i] >= self.buy_score:
                    in_position = True
                    signals[i] = 1
                    current_stop = close[i] - (self.n * atrs[i])
            else:
                # 更新跟踪止损位 (仅向上移动)
                new_stop = close[i] - (self.n * atrs[i])
                current_stop = max(current_stop, new_stop)
                
                # 检查出场条件
                if close[i] < current_stop or scores[i] <= self.sell_score:
                    in_position = False
                    signals[i] = -1
                    current_stop = 0
            
            if in_position:
                stop_prices[i] = current_stop

        df['signal'] = signals
        df['stop_line'] = stop_prices
        self.signals = df
        return df

