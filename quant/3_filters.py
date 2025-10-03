import jqdatasdk
import pandas as pd
import talib
from datetime import date, timedelta

# 登录 JoinQuant
jqdatasdk.auth("15901481583", "Jjian9jun")

def fetch_stock_analysis(stock_code="000001.XSHE", end_date=None):
    if end_date is None:
        end_date = date.today().strftime("%Y-%m-%d")
    
    start_date = (pd.to_datetime(end_date) - timedelta(days=360)).strftime("%Y-%m-%d")

    # 1. 获取日K数据
    df_day = jqdatasdk.get_price(
        stock_code, 
        start_date=start_date, 
        end_date=end_date, 
        frequency="daily",
        fields=["open", "close", "high", "low", "volume"])
    df_day.index = pd.to_datetime(df_day.index)

    # 2. 计算EMA
    df_day["ema_short"] = talib.EMA(df_day["close"], timeperiod=12)
    df_day["ema_long"] = talib.EMA(df_day["close"], timeperiod=26)

    # 3. 计算MACD
    macd, signal, hist = talib.MACD(df_day["close"], fastperiod=12, slowperiod=26, signalperiod=9)
    df_day["macd"] = macd
    df_day["signal"] = signal
    df_day["hist"] = hist
    print(f"df_day:{df_day}")

    # 4. 周K数据
    df_week = df_day.resample("W-FRI").last()
    df_week["ema_short"] = talib.EMA(df_week["close"], timeperiod=12)
    df_week["ema_long"] = talib.EMA(df_week["close"], timeperiod=26)
    macd_w, signal_w, hist_w = talib.MACD(df_week["close"], fastperiod=12, slowperiod=26, signalperiod=9)
    df_week["macd"] = macd_w
    df_week["signal"] = signal_w
    df_week["hist"] = hist_w

    print(f"df_week:{df_week}")

    # 5. 提取最后一期（日 & 周）
    today = df_day.iloc[-1]
    yesterday = df_day.iloc[-2]
    this_week = df_week.iloc[-1]
    last_week = df_week.iloc[-2]

    # 计算斜率（差分近似）
    day_short_slope = today["ema_short"] - yesterday["ema_short"]
    day_long_slope = today["ema_long"] - yesterday["ema_long"]
    day_hist_slope = today["hist"] - yesterday["hist"]

    week_short_slope = this_week["ema_short"] - last_week["ema_short"]
    week_long_slope = this_week["ema_long"] - last_week["ema_long"]
    week_hist_slope = this_week["hist"] - last_week["hist"]

    # 拼装 prompt
    prompt = f"""
### 三层滤网策略详细分析
1. **周K线分析：**
- 周EMA均线指标：当前交易周短期EMA为{this_week["ema_short"]:.2f}, 长期EMA为{this_week["ema_long"]:.2f}, 短期EMA斜率为{week_short_slope:.2f}, 长期EMA斜率{week_long_slope:.2f}, \
短期EMA{"高于" if this_week["ema_short"]>this_week["ema_long"] else "低于"}长期EMA, 短期EMA斜率{"高于" if week_short_slope>week_long_slope else "低于"}长期EMA斜率, \
前一交易周, 短期EMA斜率为{last_week["ema_short"] - df_week.iloc[-3]["ema_short"]:.2f}, 当前交易周短期EMA斜率{"高于" if week_short_slope > (last_week["ema_short"] - df_week.iloc[-3]["ema_short"]) else "低于"}前一时间点短期EMA斜率；
- 周MACD指标：当前交易周MACD线为{this_week["macd"]:.2f}, 信号线为{this_week["signal"]:.2f}, MACD柱状图为{this_week["hist"]:.2f}, MACD柱状图斜率为{week_hist_slope:.2f}；

2. **日K线分析：**
- 日K基础信息：开盘:{today["open"]:.2f}，最低:{today["low"]:.2f}，最高:{today["high"]:.2f}，收盘价:{today["close"]:.2f}，涨跌幅:{(today["close"]/yesterday["close"]-1)*100:.2f}%；
- 日均线指标：当前交易日短期EMA为{today["ema_short"]:.2f}, 长期EMA为{today["ema_long"]:.2f}, 短期EMA斜率为{day_short_slope:.2f}, 长期EMA斜率{day_long_slope:.2f}, \
短期EMA{"高于" if today["ema_short"]>today["ema_long"] else "低于"}长期EMA, 短期EMA斜率{"高于" if day_short_slope>day_long_slope else "低于"}长期EMA斜率；
- 日MACD指标：当前交易日MACD线为{today["macd"]:.2f}, 信号线为{today["signal"]:.2f}, MACD柱状图为{today["hist"]:.2f}, MACD柱状图斜率为{day_hist_slope:.2f}；
- 日成交量：当前交易日成交量为{today["volume"]:.0f}，前一个交易日成交量为{yesterday["volume"]:.0f}；

### 技术面综合评分
综合以上分析，技术面给予 <score> 分。

### 历史数据
1. 周K线：{df_week.tail(5).to_dict(orient="index")}
2. 日K线：{df_day.tail(5).to_dict(orient="index")}
"""
    return prompt

if __name__ == "__main__":
    result = fetch_stock_analysis("600519.XSHG", "2025-06-25")  # 茅台示例
    print(result)

