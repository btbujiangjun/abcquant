import re
import talib
import pandas as pd
from typing import Type, Dict, Any
from datetime import datetime, timedelta
from utils.logger import logger
from db import QuantDB
from quant.llm import LLMClient, OpenAIClient


# =====================
# 数据处理与指标计算
# =====================
class IndicatorCalculator:
    @staticmethod
    def add_ema_macd(
        df: pd.DataFrame, 
        ema_short=12, 
        ema_long=26, 
        macd_signal=9
    ) -> pd.DataFrame:
        df = df.sort_values(by="date", ascending=True).reset_index(drop=True)
        df["ema_short"] = talib.EMA(df["close"], timeperiod=ema_short)
        df["ema_long"] = talib.EMA(df["close"], timeperiod=ema_long)
        macd, signal, hist = talib.MACD(
            df["close"], 
            fastperiod=ema_short, 
            slowperiod=ema_long, 
            signalperiod=macd_signal
        )
        df["macd"], df["signal"], df["hist"] = macd, signal, hist
        return df

# =====================
# 策略基类
# =====================
class Strategy:
    name: str = "base"

    def __init__(self, llm:LLMClient):
        self.llm = llm
        self.db = QuantDB()

    def analyze(self, 
            df_day: pd.DataFrame, 
            df_week: pd.DataFrame,
            stock_info: str,
        ) -> Dict[str, Any]:
        raise NotImplementedError

    def build_prompt(self, analysis: Dict[str, Any]) -> str:
        raise NotImplementedError

    def quant(self, 
            symbol: str, 
            day_peroid: int=360, 
            week_peroid: int=360,
            date: str=None
        ) -> str:
        # 1. 获取数据
        df_day = self.db.query_stock_price(
            symbol, 
            interval="daily",
            date=date, 
            top_k=day_peroid
        )
        df_week = self.db.query_stock_price(
            symbol, 
            interval="weekly",
            date=date, 
            top_k=week_peroid
        )
        stock_info = self.db.query_stock_info(symbol)
        stock_info = stock_info["info"].iat[0] if isinstance(stock_info, pd.DataFrame) and not stock_info.empty else ""

        # 2. 加指标
        df_day = IndicatorCalculator.add_ema_macd(df_day)
        df_week = IndicatorCalculator.add_ema_macd(
            df_week, 
            ema_short=6, 
            ema_long=13, 
            macd_signal=4
        )

        # 3. 策略分析
        analysis = self.analyze(df_day, df_week, stock_info)

        # 4. 构造 prompt
        prompt = self.build_prompt(analysis)

        # 5. 调用 LLM
        report = self.llm.chat(prompt)
        
        # 6. 提取 score
        score = None
        match = re.search(r"<score>([-+]?\d*\.?\d+)</score>", report)
        if match:
            try:
                score = float(match.group(1))
            except ValueError:
                score = None

        return {
            "symbol": symbol,
            "date": df_day["date"].iat[-1],
            "strategy": self.name,
            "score": score,
            "report": report
        }


# =====================
# 三层滤网策略
# =====================
class ThreeFilterStrategy(Strategy):
    name: str = "three_filters"

    def analyze(self, 
            df_day: pd.DataFrame, 
            df_week: pd.DataFrame,
            stock_info: str,
        ) -> Dict[str, Any]:
        if len(df_day) < 2 or len(df_week) < 2:
            raise ValueError(f"Three Filters analysis error: data isn't enough.")

        today, yesterday = df_day.iloc[-1], df_day.iloc[-2]
        this_week, last_week = df_week.iloc[-1], df_week.iloc[-2]

        return {
            "today": today,
            "yesterday": yesterday,
            "this_week": this_week,
            "last_week": last_week,
            "day_short_slope": today["ema_short"] - yesterday["ema_short"],
            "day_long_slope": today["ema_long"] - yesterday["ema_long"],
            "day_hist_slope": today["hist"] - yesterday["hist"],
            "week_short_slope": this_week["ema_short"] - last_week["ema_short"],
            "week_long_slope": this_week["ema_long"] - last_week["ema_long"],
            "week_hist_slope": this_week["hist"] - last_week["hist"],
            "df_day": df_day,
            "df_week": df_week,
            "stock_info": stock_info,
        }

    def build_prompt(self, analysis: Dict[str, Any]) -> str:
        today, yesterday = analysis["today"], analysis["yesterday"]
        this_week, last_week = analysis["this_week"], analysis["last_week"]
        df_day, df_week = analysis["df_day"], analysis["df_week"]
        
        return f"""
你是一名专业的量化分析师，擅长通过技术形态识别股价趋势。  
请根据提供的数据进行分析：
### 三层滤网策略详细分析
1. **基本信息**
- 股票代码：{today["symbol"]}, 国家：{today["country"]}, 行业：{today["industry"]}, 板块：{today["sector"]}, 价格：{today["current_price"]}, 52周最高价：{today["fifty_two_week_high"]}, 52周最低价：{today["fifty_two_week_low"]}, 做空率：{today["short_ratio"]}, 分析师推荐指数：{today["recommendation"]} \
2. ****
- 股票信息:{analysis["stock_info"]}\
3. **周K线分析：**
- 周EMA均线指标：当前交易周短期EMA为{this_week["ema_short"]:.2f}, 长期EMA为{this_week["ema_long"]:.2f}, 短期EMA斜率为{analysis["week_short_slope"]:.2f}, 长期EMA斜率{analysis["week_long_slope"]:.2f}, \
短期EMA{"高于" if this_week["ema_short"]>this_week["ema_long"] else "低于"}长期EMA, 短期EMA斜率{"高于" if analysis["week_short_slope"]>analysis["week_long_slope"] else "低于"}长期EMA斜率, \
前一交易周, 短期EMA斜率为{last_week["ema_short"] - df_week.iloc[-3]["ema_short"]:.2f}, 当前交易周短
    期EMA斜率{"高于" if analysis["week_short_slope"] > (last_week["ema_short"] - df_week.iloc[-3]["ema_short"]) else "低于"}前一时间点短期EMA斜率；
- 周MACD指标：当前交易周MACD线为{this_week["macd"]:.2f}, 信号线为{this_week["signal"]:.2f}, MACD柱状图为{this_week["hist"]:.2f}, MACD柱状图斜率为{analysis["week_hist_slope"]:.2f}；

4. **日K线分析：**
- 日K基础信息:开盘:{today["open"]:.2f}，最低:{today["low"]:.2f}，最高:{today["high"]:.2f}，收盘价:{today["close"]:.2f}，涨跌幅:{(today["close"]/yesterday["close"]-1)*100:.2f}%；
- 日均线指标：当前交易日短期EMA为{today["ema_short"]:.2f}, 长期EMA为{today["ema_long"]:.2f}, 短期EMA斜率为{analysis["day_short_slope"]:.2f}, 长期EMA斜率{analysis["day_long_slope"]:.2f}；
- 日MACD指标：当前交易日MACD线为{today["macd"]:.2f}, 信号线为{today["signal"]:.2f}, MACD柱状图为{today["hist"]:.2f}, MACD柱状图斜率为{analysis["day_hist_slope"]:.2f}；
- 日成交量：当前交易日成交量为{today["volume"]:.0f}，前一个交易日成交量为{yesterday["volume"]:.0f}；

### 历史数据
1. 周K线：{df_week.tail(40).to_dict(orient="index")}
2. 日K线：{df_day.tail(20).to_dict(orient="index")}

### 技术面综合评分
综合以上分析，请给出一个介于 [-1,1] 的评分，并在最后输出 <score> 标签：
<score></score>
"""        


# =====================
# 双底策略(DoubleBottomStrategy)
# =====================
class DoubleBottomStrategy(Strategy):
    name: str = "double_bottom"

    def __init__(self, 
            llm:LLMClient,
            window: int = 30, 
            tolerance: float = 0.05
        ):
        """
        :param window: 检测的时间窗口（交易日数）
        :param tolerance: 容忍度，例如0.05表示第二个低点可以比第一个低点低5%以内
        """
        super().__init__(llm)
        self.window = window
        self.tolerance = tolerance

    def analyze(self, 
            df_day: pd.DataFrame, 
            df_week: pd.DataFrame,
            stock_info: str,
        ) -> Dict[str, Any]:
        df = df_day.tail(self.window).reset_index(drop=True)
        prices = df["close"].values

        # 找两个低点（简单用最小值+次小值来模拟）
        first_idx = prices.argmin()
        first_low = prices[first_idx]

        # 次低点必须在first_idx之后
        second_idx = first_idx + prices[first_idx+1:].argmin() + 1 if first_idx < len(prices)-1 else None
        second_low = prices[second_idx] if second_idx else None

        is_double_bottom = False
        if second_low and second_low >= first_low * (1 - self.tolerance):
            is_double_bottom = True

        return {
            "window": self.window,
            "first_low": float(first_low),
            "second_low": float(second_low) if second_low else None,
            "first_idx": int(first_idx),
            "second_idx": int(second_idx) if second_idx else None,
            "is_double_bottom": is_double_bottom,
            "df_day": df,
            "stock_info": stock_info,
        }


    def build_prompt(self, analysis: Dict[str, Any]) -> str:
        if analysis["is_double_bottom"]:
            pattern_desc = f"在最近 {analysis['window']} 个交易日内，出现双底形态：第一个底部价位 {analysis['first_low']:.2f}，第二个底部价位 {analysis['second_low']:.2f}，符合双底条件。"
        else:
            pattern_desc = f"在最近 {analysis['window']} 个交易日内，没有明显双底形态。"


        second_low = f"{analysis['second_low']:.2f}" if analysis['second_low'] is not None else '无'
        
        return f"""
你是一名专业的量化分析师，擅长通过技术形态识别股价趋势。  
我会提供给你一段股票的历史数据（日期和收盘价为主），请你按照以下要求进行分析：
### 双底策略分析
- 第一个底部（索引 {analysis['first_idx']}）：价格 {analysis['first_low']:.2f}
- 第二个底部（索引 {analysis['second_idx']}）：价格 {second_low}

### 形态判断
{pattern_desc}

### 股票基本信息
{analysis["stock_info"]}

### 技术面评分
综合分析，形态信号给予介于[-1,1]之间的 <score> 分,并在最后输出 <score> 标签：
<score></score>
"""


# =====================
# 双顶策略 (DoubleTopStrategy)
# =====================
class DoubleTopStrategy(Strategy):
    name: str = "double_top"
    
    def __init__(self, 
            llm:LLMClient,
            window: int = 30, 
            tolerance: float = 0.05
        ):
        """
        :param window: 检测时间窗口
        :param tolerance: 两个顶点容忍度，例如0.05表示第二个高点可以比第一个高点低/高5%以内
        """
        super().__init__(llm)
        self.window = window
        self.tolerance = tolerance

    def analyze(self, 
            df_day: pd.DataFrame, 
            df_week: pd.DataFrame,
            stock_info: str,
        ) -> Dict[str, Any]:
        df = df_day.tail(self.window).reset_index(drop=True)
        prices = df["close"].values

        # 找第一个高点
        first_idx = prices.argmax()
        first_high = prices[first_idx]

        # 第二个高点（必须在 first_idx 之后）
        second_idx = first_idx + prices[first_idx+1:].argmax() + 1 if first_idx < len(prices)-1 else None
        second_high = prices[second_idx] if second_idx else None

        is_double_top = False
        if second_high and abs(second_high - first_high) / first_high <= self.tolerance:
            is_double_top = True

        return {
            "window": self.window,
            "first_high": float(first_high),
            "second_high": float(second_high) if second_high else None,
            "first_idx": int(first_idx),
            "second_idx": int(second_idx) if second_idx else None,
            "is_double_top": is_double_top,
            "df_day": df,
            "stock_info": stock_info
        }

    def build_prompt(self, analysis: Dict[str, Any]) -> str:
        if analysis["is_double_top"]:
            pattern_desc = f"在最近 {analysis['window']} 个交易日内，出现双顶形态：第一个顶点 {analysis['first_high']:.2f}，第二个顶点 {analysis['second_high']:.2f}，符合双顶条件。"
        else:
            pattern_desc = f"在最近 {analysis['window']} 个交易日内，没有明显双顶形态。"

        second_high = f"{analysis['second_high']:.2f}" if analysis['second_high'] else '无'

        return f"""
你是一名专业的量化分析师，擅长通过技术形态识别股价趋势。  
我会提供给你一段股票的历史数据（日期和收盘价为主），请你按照以下要求进行分析：
### 双顶策略分析
- 第一个顶点（索引 {analysis['first_idx']}）：价格 {analysis['first_high']:.2f}
- 第二个顶点（索引 {analysis['second_idx']}）：价格 {second_high}

### 形态判断
{pattern_desc}

### 股票基本信息
{analysis["stock_info"]}

### 技术面评分
综合分析，形态信号给予介于[-1,1]之间的 <score> 分,并在最后输出 <score> 标签：
<score></score>
"""


# =====================
# 杯柄形态策略 (CupHandleStrategy)
# =====================
class CupHandleStrategy(Strategy):
    name: str = "cup_handle"

    def __init__(self, 
        llm:LLMClient,
        window: int = 60, 
        tolerance: float = 0.08, 
        handle_window: int = 15
    ):
        """
        :param window: 检测时间窗口
        :param handle_ratio: 杯柄回撤比例（相对于杯体深度），常见 <= 0.33
        """
        super().__init__(llm)
        self.window = window
        self.tolerance = tolerance
        self.handle_window = handle_window

    def analyze(self, 
            df_day: pd.DataFrame, 
            df_week: pd.DataFrame,
            stock_info: str,
        ) -> Dict[str, Any]:
        df = df_day.tail(self.window).reset_index(drop=True)
        prices = df["close"].values

        left_high = prices[0]
        bottom_idx = prices.argmin()
        bottom = prices[bottom_idx]
        right_high = prices[-1]

        # 判断杯体：底部比两边低，且两边价格接近
        is_cup = bottom < left_high and bottom < right_high and abs(left_high - right_high) / left_high <= self.tolerance

        # 判断柄：底部右边到末尾，是否存在小幅回调
        handle_exists = False
        if bottom_idx < len(prices) - self.handle_window:
            handle_part = prices[bottom_idx+1:]
            if handle_part.min() > bottom and handle_part.argmin() < self.handle_window:
                handle_exists = True

        is_cup_handle = is_cup and handle_exists

        return {
            "window": self.window,
            "left_high": float(left_high),
            "right_high": float(right_high),
            "bottom": float(bottom),
            "bottom_idx": int(bottom_idx),
            "is_cup_handle": is_cup_handle,
            "df_day": df,
            "stock_info": stock_info,
        }

    def build_prompt(self, analysis: Dict[str, Any]) -> str:
        if analysis["is_cup_handle"]:
            pattern_desc = f"在最近 {analysis['window']} 个交易日内，检测到杯柄形态：左高点 {analysis['left_high']:.2f}，右高点 {analysis['right_high']:.2f}，底部 {analysis['bottom']:.2f}，形态成立。"
        else:
            pattern_desc = f"在最近 {analysis['window']} 个交易日内，没有明显杯柄形态。"

        return f"""
你是一名专业的量化分析师，擅长通过技术形态识别股价趋势。  
我会提供给你一段股票的历史数据（日期和收盘价为主），请你按照以下要求进行分析：
### 杯柄形态策略分析
- 左高点：价格 {analysis['left_high']:.2f}
- 底部（索引 {analysis['bottom_idx']}）：价格 {analysis['bottom']:.2f}
- 右高点：价格 {analysis['right_high']:.2f}

### 形态判断
{pattern_desc}

### 股票基本信息
{analysis["stock_info"]}

### 技术面评分
综合分析，形态信号给予介于[-1,1]之间的 <score> 分,并在最后输出 <score> 标签：
<score></score>
"""

# =====================================================
# 工厂类
# =====================================================
class StrategyFactory:
    _strategies: Dict[str, Type[Strategy]] = {}

    @classmethod
    def discover(cls) -> None:
        """自动发现并注册所有继承 Strategy 的类"""
        for subclass in Strategy.__subclasses__():
            # 如果策略类有自定义的 name，就用它，否则用类名小写
            name = getattr(subclass, "name", subclass.__name__.lower())
            cls._strategies[name] = subclass

    @classmethod
    def create(cls, name: str, **kwargs) -> Strategy:
        """创建策略实例"""
        if not cls._strategies:  # 如果还没加载，就自动发现
            cls.discover()
        if name not in cls._strategies:
            available = ", ".join(cls._strategies.keys())
            raise ValueError(f"未知策略: {name}, 可选: {available}")
        return cls._strategies[name](**kwargs)

class StrategyHelper():
    def __init__(self):
        self.llm = OpenAIClient()
        strategy_names = [
            "three_filters", 
            "double_bottom", 
            "double_top", 
            "cup_handle"
        ]
        self.strategies = [StrategyFactory.create(name, llm=self.llm) for name in strategy_names]
        self.db = QuantDB()

    def analysis(self, symbol:str, date:str, update:bool=False):
        date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
        if not update:
            df = self.db.query_analysis_report(symbol, date)         
            if isinstance(df, pd.DataFrame) and not df.empty:
                logger.info(f"Analysis report {symbol} at {date} exists.")
                return
        
        data = dict()
        for strategy in self.strategies:
            try:
                res = strategy.quant(symbol, date=date)
                data[f"{res['strategy']}_score"]  = res["score"], 
                data[f"{res['strategy']}_report"] = res["report"]
            except Exception as e:
                logger.error(f"{symbol} {date} quant error:{e}")

        if len(data) > 0:
            data["symbol"]  = symbol
            data["date"]    = date
            self.db.update_analysis_report(pd.DataFrame(data))
            logger.info(f"Finish analysis {symbol} at {date.split()[0]}")
        else:
            logger.error(f"Quant {symbol} {date} skipped.")

    def update(self, symbol: str, days: int=10):
        today = datetime.today()
        df = self.db.query_analysis_report(symbol, top_k=1)        
        if isinstance(df, pd.DataFrame) and not df.empty:
            date = datetime.strptime(df["date"].iat[-1], "%Y-%m-%d")
            data = date + timedelta(days=1)
        else:
            date = today - timedelta(days=days)      
        
        while(date < today):
            date_str = date.strftime("%Y-%m-%d")
            self.analysis(symbol, date_str)
            date = date + timedelta(days=1)
            logger.info(F"Analysis report {symbol} at {date_str} finished.")

if __name__ == "__main__":
    #LI
    symbols = ["XPEV", "NIO", "BABA", "NVDA", "TSLA", "TQQQ", "SQQQ", "MSTX", "MSTZ", "PDD", "NBIS", "CRWV", "SE", "HOOD", "BILI", "YINN"]
    symbols = ["XPEV"]
    helper = StrategyHelper()
    helper.analysis("XPEV", "2025-10-03", update=True)
    for symbol in symbols:
        helper.update(symbol, 15)

    """
    llm = OpenAIClient()
    strategy_names = [
        "three_filter", 
        "double_bottom", 
        "double_top", 
        "cup_handle"
    ]
    strategies = [StrategyFactory.create(name, llm=llm) for name in strategy_names]
   
     
    results = []
    for strategy in strategies:
        res = strategy.quant(ticker)
        results.append(res)

    # 表格输出评分对比
    if len(results) > 0:
        table = [[r["strategy"], r["score"]] for r in results]
        print(f"=== {ticker} 策略技术面评分({results[0]['date'].split()[0]}) ===")
        
        from tabulate import tabulate 
        print(tabulate(table, headers=["策略", "Score"], tablefmt="github"))

    # 输出详细报告
    for r in results:
        print(f"\n=== {r['strategy']} 报告 ===")
        print(r["report"]) 

    print(results)
    """


