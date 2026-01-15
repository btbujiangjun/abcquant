import re
import json
import talib
import pandas as pd
from typing import Type, Dict, Any
from datetime import datetime, timedelta
from db import QuantDB
from utils.time import *
from utils.logger import logger
from utils.checkpoint import Checkpoint
from config import CRITICAL_STOCKS_US
from quant.indicator import IndicatorCalculator
from quant.llm import LLMClient
from core.ohlc import OHLCData

class PriceDataInvalidError(Exception):
    def __init__(self, 
            symbol:str,
            date:str, 
            daily_date:str, 
            week_date:str):
        self.symbol = symbol
        super().__init__(f"{symbol} price data invalid: date:{date}, latest_date:{daily_date}, latest_week:{week_date}.")

# =====================
# 策略基类
# =====================
class Strategy:
    name: str = "base"

    def __init__(self, llm:LLMClient, db:QuantDB=QuantDB()):
        self.llm = llm
        self.db = db
        self.columns = ['date', 'open', 'close', 'high', 'low', 'volume', 
            'ema_short', 'ema_long', 'macd', 'signal', 'hist',
            'rsi', 'kdj_k', 'kdj_d', 'kdj_j', 'bb_upper', 'bb_mid', 'bb_lower', 'atr'
        ]

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
            day_peroid: int=400, 
            week_peroid: int=50,
            date: str=None
        ) -> str:
        # 1. 获取股票价格数据
        df_day = self.db.query_stock_price(
            symbol, 
            interval="daily",
            date=date, 
            top_k=day_peroid
        )
        df_week = OHLCData(df_day).daily_week() 

        # 2. 数据有效性检验
        if len(df_day) < 1 or len(df_week) < 1:
            raise ValueError(f"{symbol}/{date} ohlc data is none")

        latest_day  = df_day['date'].iat[-1].split()[0]
        latest_week = df_week['date'].iat[-1].split()[0]
        covered_week = days_delta(latest_week, 7) 
        if latest_day != date or covered_week < date:
            raise PriceDataInvalidError(symbol, date, latest_day, latest_week)
        
        # 3. 股票基本信息
        stock_info = self.db.query_stock_info(symbol)
        stock_info = stock_info["info"].iat[0] if isinstance(stock_info, pd.DataFrame) and not stock_info.empty else "{}"
        try:
            data = json.loads(stock_info)
            #用周期内最后一天收盘价格替换实时价格数据，避免数据错乱
            if not is_today(date) and not is_yesterday(date) or "currentPrice" not in data:
                data["currentPrice"] = df_day['close'].iat[-1]
                stock_info = json.dumps(data, ensure_ascii=False)
        except Exception as e:
            logger.error(f"{symbol} update current price error:{e}")


        # 4. 加指标
        df_day = IndicatorCalculator.calc_ema_macd_kdj_boll(df_day)
        df_week = IndicatorCalculator.calc_ema_macd_kdj_boll(
            df_week, 
            ema_short=6, 
            ema_long=13, 
            macd_signal=4
        )

        # 5. 策略分析
        analysis = self.analyze(df_day, df_week, stock_info)

        # 6. 构造 prompt
        prompt = self.build_prompt(analysis)
        logger.debug(prompt)

        # 7. 调用 LLM
        report = self.llm.chat(prompt)

        # 8. remove think block
        think_str = "</think>"
        idx = report.rfind(think_str)
        if idx > -1:
            report = report[idx + len(think_str):]
 
        # 9. 提取 score
        score = None
        matches = re.findall(r"<score>([-+]?\d*\.?\d+)</score>", report)
        if matches:
            try:
                score = float(matches[-1])
            except ValueError:
                score = None
                logger.warning(f"Not found score from llm reponse for {symbol} at {latest_day}")

        # 10. 返回格式化结果
        return {
            "symbol": symbol,
            "date": latest_day,
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
## 👤 角色设定
你是一位专业的量化分析师，专注于技术分析与量化策略开发。你精通三层滤网交易系统（Three Screen Trading System），擅长：
- 多时间框架分析（周线、日线、日内）
- 技术指标解读（EMA、MACD、RSI、KDJ、布林带等）
- 价格行为与形态识别
- 风险管理与风险收益比评估

**你的任务**：基于提供的股票数据，运用三层滤网交易系统进行全面技术分析，并给出未来一周价格走势的量化评分。

---

## 📋 待分析数据

### 股票基本信息
- **股票代码**：{today["symbol"]}
- **国家/地区**：{today["country"]}
- **所属行业**：{today["industry"]}
- **所属板块**：{today["sector"]}

### 周K线分析数据
**当前周期数据**：
- **短期EMA值**：{this_week["ema_short"]:.2f}，斜率：{analysis["week_short_slope"]:.2f}
- **长期EMA值**：{this_week["ema_long"]:.2f}，斜率：{analysis["week_long_slope"]:.2f}
- **EMA关系**：短期EMA {"高于" if this_week["ema_short"]>this_week["ema_long"] else "低于"}长期EMA
- **EMA斜率关系**：短期EMA斜率 {"高于" if analysis["week_short_slope"]>analysis["week_long_slope"] else "低于"}长期EMA斜率
- **短期EMA斜率变化**：前一周为{last_week["ema_short"] - df_week.iloc[-3]["ema_short"]:.2f}，当前{"高于" if analysis["week_short_slope"] > (last_week["ema_short"] - df_week.iloc[-3]["ema_short"]) else "低于"}前一周
- **MACD线值**：{this_week["macd"]:.2f}
- **MACD信号线值**：{this_week["signal"]:.2f}
- **MACD柱状图值**：{this_week["hist"]:.2f}，斜率：{analysis["week_hist_slope"]:.2f}

### 日K线分析数据
**当前交易日数据**：
- **日期**：最新交易日
- **价格数据**：
  - 开盘：{today["open"]:.2f}
  - 最高：{today["high"]:.2f}
  - 最低：{today["low"]:.2f}
  - 收盘：{today["close"]:.2f}
  - 涨跌幅：{(today["close"]/yesterday["close"]-1)*100:.2f}%
- **均线指标**：
  - 短期EMA：{today["ema_short"]:.2f}，斜率：{analysis["day_short_slope"]:.2f}
  - 长期EMA：{today["ema_long"]:.2f}，斜率：{analysis["day_long_slope"]:.2f}
- **MACD指标**：
  - MACD线：{today["macd"]:.2f}
  - 信号线：{today["signal"]:.2f}
  - 柱状图：{today["hist"]:.2f}，斜率：{analysis["day_hist_slope"]:.2f}
- **成交量**：
  - 当前交易日：{today["volume"]:.0f}
  - 前一个交易日：{yesterday["volume"]:.0f}
  - 变化率：{(today["volume"] - yesterday["volume"]) * 100 / (yesterday["volume"] or 1):.1f}%

### 历史数据参考
- **周K线（近20周）**：{df_week[self.columns].tail(20).to_dict(orient="records")}
- **日K线（近40日）**：{df_day[self.columns].tail(40).to_dict(orient="records")}

---

## 🎯 分析要求

### 三层滤网分析框架

#### **第一层滤网：周线趋势分析（主趋势判断）**
**目的**：确定市场的核心方向，作为所有交易决策的基础。

**分析要点**：
1. **EMA趋势分析**：
   - 位置关系：短期EMA vs. 长期EMA（多头/空头排列）
   - 斜率变化：趋势加速/减速信号
   - 关键点：短期EMA斜率改善是趋势可能转变的早期信号

2. **MACD动量分析**：
   - MACD线与信号线相对位置
   - 柱状图方向与斜率变化
   - 动量加速/衰竭信号识别

3. **综合趋势判断**：
   - 明确趋势方向（上涨/下跌/震荡）
   - 评估趋势强度与可持续性
   - 识别趋势衰竭或反转信号

#### **第二层滤网：日线逆势机会（交易机会筛选）**
**目的**：在主要趋势方向下寻找高质量的逆势交易机会或趋势确认信号。

**分析要点**：
1. **EMA与价格关系**：
   - 日线EMA排列状态
   - 股价相对于短期EMA的位置
   - 均线斜率变化

2. **MACD动量与背离**：
   - 日线MACD状态
   - 寻找价格与MACD的背离信号
   - 评估动量变化

3. **价格行为与成交量**：
   - K线形态识别（锤头线、吞没形态、十字星等）
   - 成交量分析（放量/缩量、成交量变化率）
   - 价格与关键位关系

#### **第三层滤网：入场时机筛选（精准择时）**
**目的**：确定具体入场点，评估风险收益比，制定交易计划。

**分析要点**：
1. **关键价位识别**：
   - 支撑位识别（前期低点、成交密集区、长期EMA、布林带下轨）
   - 阻力位识别（前期高点、成交密集区、长期EMA、布林带上轨）
   - 关键突破位识别

2. **风险指标评估**：
   - 超买/超卖状态（如RSI、KDJ数据可用则使用）
   - 波动率评估
   - 市场情绪指标

3. **多时间框架共振**：
   - 评估周线、日线信号一致性
   - 识别多时间框架共振信号
   - 评估信号强度与可靠性

4. **风险收益比评估**：
   - 基于关键价位计算潜在盈亏比
   - 评估交易机会的性价比

---

## ⚖️ 综合评分系统

### 评分范围：[-1, 1]
- **-1.0 至 -0.6**：强烈看跌
- **-0.6 至 -0.2**：温和看跌
- **-0.2 至 0.2**：中性震荡
- **0.2 至 0.6**：温和看涨
- **0.6 至 1.0**：强烈看涨

### 评分考量维度与权重
| 维度 | 权重 | 评估要点 |
|------|------|----------|
| **周线趋势方向** | 40% | EMA排列、MACD动量、趋势强度 |
| **日线动量与结构** | 30% | MACD状态、K线形态、成交量配合 |
| **关键价位与风险** | 20% | 支撑阻力有效性、风险收益比 |
| **风险指标状态** | 10% | 超买超卖、波动率、市场情绪 |

### 评分标准细则
1. **强烈看跌 (-1.0 ~ -0.6)**：
   - 周线明确下跌趋势，EMA空头排列
   - MACD处于零轴下方且柱状图扩大
   - 日线无有效反弹信号，价格位于关键阻力下方
   - 成交量配合下跌放大

2. **温和看跌 (-0.6 ~ -0.2)**：
   - 周线下跌趋势，但出现减速信号
   - MACD可能显示动量衰竭
   - 日线可能出现超卖但反弹无力
   - 整体仍处弱势格局

3. **中性震荡 (-0.2 ~ 0.2)**：
   - 周线与日线方向不明
   - EMA相互缠绕，无明显趋势
   - 价格在关键区间内震荡
   - 成交量萎缩，市场观望情绪浓厚

4. **温和看涨 (0.2 ~ 0.6)**：
   - 周线下跌趋势出现衰竭或上涨趋势初期
   - MACD出现金叉或柱状图转正
   - 日线形成明确看涨结构（如放量突破）
   - 风险收益比相对有利

5. **强烈看涨 (0.6 ~ 1.0)**：
   - 周线上涨趋势明确，EMA多头排列
   - MACD处于零轴上方且柱状图扩大
   - 日线给出强势买入信号，成交量配合
   - 多时间框架共振看涨

---

## 📤 输出要求

### 输出格式规范
**请严格按照以下结构和Markdown格式输出分析结果：**

#### 第一层滤网分析（周线趋势）
*   **EMA分析结论**：[基于短期EMA={this_week["ema_short"]:.2f}, 长期EMA={this_week["ema_long"]:.2f}，短期斜率={analysis["week_short_slope"]:.2f}, 长期斜率={analysis["week_long_slope"]:.2f}，得出...]
*   **MACD分析结论**：[基于MACD线={this_week["macd"]:.2f}, 信号线={this_week["signal"]:.2f}，柱状图={this_week["hist"]:.2f}，斜率={analysis["week_hist_slope"]:.2f}，得出...]
*   **周线趋势综合判断**：[明确趋势方向及强度，如"主下跌趋势，但出现动量衰竭迹象"]

#### 第二层滤网分析（日线机会）
*   **EMA与价格分析**：[基于日线短期EMA={today["ema_short"]:.2f}, 长期EMA={today["ema_long"]:.2f}，分析日线EMA排列、股价与均线关系]
*   **MACD与动量分析**：[基于日线MACD线={today["macd"]:.2f}, 信号线={today["signal"]:.2f}，分析日线MACD状态，有无背离信号]
*   **K线形态与成交量**：
    *   形态：[基于开盘{ today["open"]:.2f}，最高{ today["high"]:.2f}，最低{ today["low"]:.2f}，收盘{ today["close"]:.2f}，分析具体K线形态描述及技术含义]
    *   成交量：[当日成交量{ today["volume"]:.0f}，较前日变化{(today["volume"] - yesterday["volume"]) * 100 / (yesterday["volume"] or 1):.1f}%，分析其市场含义]
*   **日线机会综合判断**：[明确机会类型，如"超跌后的技术性反弹机会"]

#### 第三层滤网分析（入场时机）
*   **关键价位识别**：
    *   支撑位：[基于历史数据识别1-2个关键支撑位及理由]
    *   阻力位：[基于历史数据识别1-2个关键阻力位及理由]
*   **风险指标评估**：
    *   超买/超卖：[基于历史数据中的RSI、KDJ等指标状态分析]
    *   波动率：[基于历史价格波动分析当前波动状态]
*   **多框架综合与评估**：
    *   信号一致性：[周线与日线信号是否共振]
    *   风险收益比：[基于关键位距离评估潜在盈亏比]
    *   交易倾向：[顺势入场/逆势搏反弹/观望]

#### 综合评分
基于以上三层滤网分析，{today["symbol"]}未来一周价格走势的综合评分为：

<score>[精确到小数点后一位的数字，范围-1.0到1.0]</score>

---

## 📝 使用说明

### 分析流程
1. **数据检查**：确认提供的数据完整性和合理性
2. **逐层分析**：严格按照三层滤网顺序进行分析
3. **交叉验证**：检查不同指标间的信号一致性
4. **综合评估**：整合所有信息给出最终评分
5. **格式化输出**：按指定格式整理分析结果

### 注意事项
1. **客观性原则**：所有结论必须有具体数据支撑
2. **风险提示**：识别并注明分析中的不确定性
3. **逻辑一致性**：确保各层滤网分析逻辑连贯
4. **格式规范**：严格遵守输出格式要求

---
**现在，请基于上述数据和框架开始你的专业分析。**
"""


        return f"""
你是一名专业的量化分析师，擅长通过技术形态识别股价趋势。  
请严格根据以下数据进行分析：
### 三层滤网策略详细分析
### 股票信息
- 股票代码：{today["symbol"]}, 国家：{today["country"]}, 行业：{today["industry"]}, 板块：{today["sector"]}

### 周K线分析
- 周EMA均线指标：当前交易周短期EMA为{this_week["ema_short"]:.2f}, 长期EMA为{this_week["ema_long"]:.2f}, 短期EMA斜率为{analysis["week_short_slope"]:.2f}, 长期EMA斜率{analysis["week_long_slope"]:.2f}, 短期EMA{"高于" if this_week["ema_short"]>this_week["ema_long"] else "低于"}长期EMA, 短期EMA斜率{"高于" if analysis["week_short_slope"]>analysis["week_long_slope"] else "低于"}长期EMA斜率, 前一交易周短期EMA斜率为{last_week["ema_short"] - df_week.iloc[-3]["ema_short"]:.2f}, 当前交易周短期EMA斜率{"高于" if analysis["week_short_slope"] > (last_week["ema_short"] - df_week.iloc[-3]["ema_short"]) else "低于"}前一时间点短期EMA斜率；
- 周MACD指标：当前交易周MACD线为{this_week["macd"]:.2f}, 信号线为{this_week["signal"]:.2f}, MACD柱状图为{this_week["hist"]:.2f}, MACD柱状图斜率为{analysis["week_hist_slope"]:.2f}

### 日K线分析
- 日K基础信息：开盘:{today["open"]:.2f}，最低:{today["low"]:.2f}，最高:{today["high"]:.2f}，收盘价:{today["close"]:.2f}，涨跌幅:{(today["close"]/yesterday["close"]-1)*100:.2f}%
- 日均线指标：当前交易日短期EMA为{today["ema_short"]:.2f}, 长期EMA为{today["ema_long"]:.2f}, 短期EMA斜率为{analysis["day_short_slope"]:.2f}, 长期EMA斜率{analysis["day_long_slope"]:.2f}
- 日MACD指标：当前交易日MACD线为{today["macd"]:.2f}, 信号线为{today["signal"]:.2f}, MACD柱状图为{today["hist"]:.2f}, MACD柱状图斜率为{analysis["day_hist_slope"]:.2f}
- 日成交量：当前交易日成交量为{today["volume"]:.0f}，前一个交易日成交量为{yesterday["volume"]:.0f}

### 历史数据参考
- 周K线（近20周）：{df_week[self.columns].tail(20).to_dict(orient="records")}
- 日K线（近40日）：{df_day[self.columns].tail(40).to_dict(orient="records")}

### 综合评分
基于上述分析结论，对{today["symbol"]}未来一周价格走势给出[-1,1]区间内的综合评分，并在最后输出 <score> 标签。
<score></score>
"""

# =====================
# 双底策略(DoubleBottomStrategy)
# =====================
class DoubleBottomStrategy(Strategy):
    name: str = "double_bottom"

    def __init__(self, 
            llm:LLMClient,
            db:QuantDB=QuantDB(),
            window: int = 30, 
            tolerance: float = 0.05
        ):
        """
        :param window: 检测的时间窗口（交易日数）
        :param tolerance: 容忍度，例如0.05表示第二个低点可以比第一个低点低5%以内
        """
        super().__init__(llm=llm, db=db)
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
            db:QuantDB=QuantDB(),
            window: int = 30, 
            tolerance: float = 0.05
        ):
        """
        :param window: 检测时间窗口
        :param tolerance: 两个顶点容忍度，例如0.05表示第二个高点可以比第一个高点低/高5%以内
        """
        super().__init__(llm=llm, db=db)
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
        db:QuantDB=QuantDB(),
        window: int = 60, 
        tolerance: float = 0.08, 
        handle_window: int = 15
    ):
        """
        :param window: 检测时间窗口
        :param handle_ratio: 杯柄回撤比例（相对于杯体深度），常见 <= 0.33
        """
        super().__init__(llm=llm, db=db)
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
            raise ValueError(f"❤️  未知策略: {name}, 可选: {available}")
        return cls._strategies[name](**kwargs)

class StrategyHelper():
    def __init__(self, llm:LLMClient, db:QuantDB=QuantDB()):
        self.llm = llm
        strategy_names = [
            "three_filters", 
            "double_bottom", 
            "double_top", 
            "cup_handle"
        ]
        strategy_names = ["three_filters"]
        self.db = db
        self.strategies = [StrategyFactory.create(name, llm=self.llm, db=self.db) for name in strategy_names]

    def analysis(self, symbol:str, date:str, update:bool=False) -> bool:
        date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
        if not update:
            df = self.db.query_analysis_report(symbol, date)         
            if isinstance(df, pd.DataFrame) and not df.empty:
                logger.info(f"🟡 Analysis report {symbol} on {date} already exists.")
                return True
        
        data = dict()
        for strategy in self.strategies:
            try:
                res = strategy.quant(symbol, date=date)
                data[f"{res['strategy']}_score"]  = res["score"], 
                data[f"{res['strategy']}_report"] = res["report"]
            except PriceDataInvalidError as e:
                logger.warning(e)
                return False
            except Exception as e:
                logger.error(f"🚫{symbol} {date} quant error:{e}")
                return False

        if len(data) > 0:
            data["symbol"]  = symbol
            data["date"]    = date
            data["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.db.update_analysis_report(pd.DataFrame(data))
            return True

    def update(self, symbol: str, days: int=10, update=False, cp:Checkpoint=None):
        today = datetime.today()
        for day in range(days):
            date = today - timedelta(days=day)
            date_str = date.strftime("%Y-%m-%d")
            
            if not update:
                df = self.db.query_analysis_report(symbol, date=date_str, top_k=1)        
                if isinstance(df, pd.DataFrame) and not df.empty:
                    logger.info(f"🟡 Analysis report for {symbol} ({date_str}) already exists.")
                    continue
            if cp is not None and not cp.seek({"symbol": symbol, "date":date_str}):
                logger.info(F"🟡 Skip Analysis report {symbol}({date_str}) by checkpoint mode")
                continue
            if self.analysis(symbol, date_str, update=update):
                logger.info(F"💚Analysis report {symbol} at {date_str} finished.")

    def update_latest(self, symbols:list[str]=CRITICAL_STOCKS_US, days:int=2, update:bool=False):
        for symbol in symbols:
            self.update(symbol, days=days, update=update)

if __name__ == "__main__":
    from quant.llm import ModelScopeClinet
    symbols, update, days = CRITICAL_STOCKS_US, True, 1200
    #symbols, update, days = ['BTC-USD'], True, 20
    helper = StrategyHelper(ModelScopeClinet(), QuantDB())
    #helper.analysis("MSTX", "2025-10-30", update=False)

    cp = Checkpoint("./.quant_ckpt")
    #cp = None
    for symbol in symbols:
        helper.update(symbol, days, update=update, cp=cp)
    

