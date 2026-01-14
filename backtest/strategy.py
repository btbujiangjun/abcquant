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
        self.signals = df
        return df

class EMACrossStrategy(BaseStrategy):
    """EMA 交叉策略：金叉买入，死叉卖出"""
    strategy_class = "EMACrossStrategy"

    def __init__(self, data, short=12, long=26):
        super().__init__(data)
        if "close" not in data.columns:
            raise KeyError("`close` field is required")
        if short >= long:
            raise ValueError("short EMA must be < long EMA")

        self.short = short
        self.long = long

    def generate_signals(self):
        df = self.data.copy()

        ema_s = Indicators.ema(df, self.short)
        ema_l = Indicators.ema(df, self.long)

        s_prev = ema_s.shift(1)
        l_prev = ema_l.shift(1)

        conditions = [
            (s_prev > l_prev),  # 多头区间
            (s_prev < l_prev)   # 空头区间
        ]
        choices = [1, -1]
        df['signal'] = np.select(conditions, choices, default=0)
        df.iloc[:self.long * 3, df.columns.get_loc('signal')] = 0 #冷启动

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

class MagicNineStrategy(BaseStrategy):
    """
    神奇九转策略 (基于 TD Sequential 简化)
    核心逻辑：连续 9 天收盘价低于（买入结构）或高于（卖出结构）4天前的收盘价。
    """
    strategy_class = "MagicNineStrategy"
    strategy_name = "神奇九转策略"

    def __init__(self, data: pd.DataFrame, window=4, target_count=9):
        """
        :param data: 包含 'close' 的 DataFrame
        :param window: 比较跨度，默认为 4
        :param target_count: 触发信号的连续计数，默认为 9
        """
        super().__init__(data)
        if "close" not in data.columns:
            raise KeyError("`close` field is required")
        self.window = window
        self.target_count = target_count

    def generate_signals(self) -> pd.DataFrame:
        df = self.data.copy()

        # 1. 判定当前收盘价与 N 天前收盘价的关系
        # up_cond: 卖出结构条件 (收盘价 > 4天前收盘价)
        # down_cond: 买入结构条件 (收盘价 < 4天前收盘价)
        up_cond = df['close'] > df['close'].shift(self.window)
        down_cond = df['close'] < df['close'].shift(self.window)

        # 2. 计算连续计数的逻辑函数 (向量化 + 循环优化)
        def _get_sequential_counts(series):
            counts = np.zeros(len(series))
            cur = 0
            for i, val in enumerate(series):
                if val:
                    cur += 1
                else:
                    cur = 0
                counts[i] = cur
            return counts

        # 计算上升计数和下降计数
        df['up_count'] = _get_sequential_counts(up_cond)
        df['down_count'] = _get_sequential_counts(down_cond)

        # 3. 生成信号
        # signal = 1: 买入结构完成 (连续 9 个 down) -> 潜在反弹点
        # signal = -1: 卖出结构完成 (连续 9 个 up) -> 潜在回调点
        df['signal'] = 0
        df.loc[df['down_count'] == self.target_count, 'signal'] = 1
        df.loc[df['up_count'] == self.target_count, 'signal'] = -1

        self.signals = df
        return df

class DualThrustStrategy(BaseStrategy):
    """
    Dual Thrust 策略：基于前 N 日波幅的突破系统
    """
    strategy_class = "DualThrustStrategy"

    def __init__(self, data, period=5, k1=0.5, k2=0.5):
        super().__init__(data)
        self.period = period
        self.k1 = k1  # 上轨系数
        self.k2 = k2  # 下轨系数

    def generate_signals(self):
        df = self.data.copy()
        
        # 计算过去 N 天的最高价、最低价、收盘价
        hh = df['high'].rolling(self.period).max().shift(1)
        hc = df['close'].rolling(self.period).max().shift(1)
        lc = df['close'].rolling(self.period).min().shift(1)
        ll = df['low'].rolling(self.period).min().shift(1)
        
        # 核心逻辑：Range = max(HH-LC, HC-LL)
        df['range'] = np.maximum(hh - lc, hc - ll)
        
        # 计算当日上下轨
        # 这里的 open 是当日开盘价
        df['upper'] = df['open'] + self.k1 * df['range']
        df['lower'] = df['open'] - self.k2 * df['range']
        
        # 信号判定
        df['signal'] = np.where(df['close'] > df['upper'], 1,
                       np.where(df['close'] < df['lower'], -1, 0))
        
        self.signals = df
        return df

class DonchianStrategy(BaseStrategy):
    """
    唐奇安通道突破策略 (海龟法核心)
    """
    strategy_class = "DonchianStrategy"

    def __init__(self, data, n1=20, n2=10):
        super().__init__(data)
        self.n1 = n1  # 入场通道周期
        self.n2 = n2  # 离场通道周期

    def generate_signals(self):
        df = self.data.copy()
        
        # 入场线：过去 n1 天的最高/最低
        df['upper_in'] = df['high'].rolling(self.n1).max().shift(1)
        df['lower_in'] = df['low'].rolling(self.n1).min().shift(1)
        
        # 离场线：过去 n2 天的最低价 (多头离场)
        df['exit_long'] = df['low'].rolling(self.n2).min().shift(1)
        
        signals = np.zeros(len(df))
        in_position = False
        
        # 由于涉及持仓状态锁定，这里使用循环更严谨
        close = df['close'].values
        upper_in = df['upper_in'].values
        exit_long = df['exit_long'].values
        
        for i in range(1, len(df)):
            if not in_position:
                if close[i] > upper_in[i]:
                    signals[i] = 1
                    in_position = True
            else:
                if close[i] < exit_long[i]:
                    signals[i] = -1
                    in_position = False
                    
        df['signal'] = signals
        self.signals = df
        return df

class MeanReversionStrategy(BaseStrategy):
    """
    基于 Z-Score 的均值回归策略
    """
    strategy_class = "MeanReversionStrategy"

    def __init__(self, data, period=20, threshold=2.0):
        super().__init__(data)
        self.period = period
        self.threshold = threshold

    def generate_signals(self):
        df = self.data.copy()
        
        # 计算移动平均和标准差
        df['ma'] = df['close'].rolling(self.period).mean()
        df['std'] = df['close'].rolling(self.period).std()
        
        # 计算 Z-Score: (价格 - 均值) / 标准差
        df['zscore'] = (df['close'] - df['ma']) / df['std']
        
        # 信号：极高位做空，极低位做多
        df['signal'] = np.where(df['zscore'] < -self.threshold, 1,
                       np.where(df['zscore'] > self.threshold, -1, 0))
        
        self.signals = df
        return df

class MACDDivergenceStrategy(BaseStrategy):
    """MACD 柱体背离策略：识别趋势动能衰竭"""
    strategy_class = "MACDDivergenceStrategy"

    def __init__(self, data, fast=12, slow=26, signal=9):
        super().__init__(data)
        self.params = (fast, slow, signal)

    def generate_signals(self) -> pd.DataFrame:
        df = self.data.copy()
        # 直接调用你的 Indicators
        macd_l, signal_l, hist = Indicators.macd(df, *self.params)
        
        # 简化逻辑：价格创新低但 Hist 抬升 (底背离预警)
        price_falling = df['close'] < df['close'].shift(1)
        hist_rising = hist > hist.shift(1)
        hist_negative = hist < 0
        
        # 信号：1 买入(底背离), -1 卖出(顶背离)
        df['signal'] = np.where(price_falling & hist_rising & hist_negative, 1,
                       np.where(~price_falling & ~hist_rising & (hist > 0), -1, 0))
        
        self.signals = df
        return df

class KDJStrategy(BaseStrategy):
    """KDJ 超买超卖策略"""
    strategy_class = "KDJStrategy"

    def __init__(self, data, n=9, m1=3, m2=3):
        super().__init__(data)
        self.params = (n, m1, m2)

    def generate_signals(self):
        df = self.data.copy()
        k, d, j = Indicators.kdj(df, *self.params)
        
        # 逻辑：J线下穿20买入（超卖恢复），上穿80卖出（超买回调）
        # 或者使用更经典的 K, D 金叉
        buy_cond = (k > d) & (k.shift(1) <= d.shift(1)) & (d < 30)
        sell_cond = (k < d) & (k.shift(1) >= d.shift(1)) & (d > 70)
        
        df['signal'] = np.where(buy_cond, 1, np.where(sell_cond, -1, 0))
        
        self.signals = df
        return df

class ResonanceStrategy(BaseStrategy):
    """布林带 + RSI 共振策略"""
    strategy_class = "ResonanceStrategy"

    def __init__(self, data, b_period=20, r_period=14):
        super().__init__(data)
        self.b_p = b_period
        self.r_p = r_period

    def generate_signals(self):
        df = self.data.copy()
        
        mid, upper, lower = Indicators.bbands(df, period=self.b_p)
        rsi = Indicators.rsi(df, period=self.r_p)
        
        # 买入：触碰布林下轨 且 RSI 处于超卖区 (< 35)
        buy_signal = (df['close'] <= lower) & (rsi < 35)
        # 卖出：触碰布林上轨 且 RSI 处于超买区 (> 65)
        sell_signal = (df['close'] >= upper) & (rsi > 65)
        
        df['signal'] = np.where(buy_signal, 1, np.where(sell_signal, -1, 0))
        
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

