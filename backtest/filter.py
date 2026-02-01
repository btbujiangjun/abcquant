import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any

class MarketRegimeFilter:
    """
    市场环境滤网：识别趋势(Trending)与震荡(Ranging)
    """
    @staticmethod
    def get_regime_stats(df: pd.DataFrame, window=20) -> Dict[str, float]:
        if len(df) < window:
            return {"er": 0.5, "vol_status": "normal"}
        
        # 1. 效率系数 (Efficiency Ratio): 净位移 / 总绝对路径
        # ER -> 1: 强趋势；ER -> 0: 随机震荡
        net_change = (df['close'].iloc[-1] - df['close'].iloc[-window]).__abs__()
        path = (df['close'] - df['close'].shift(1)).abs().rolling(window).sum().iloc[-1]
        er = net_change / (path + 1e-9)
        
        # 2. 波动率挤压 (BB Width)
        std = df['close'].rolling(window).std()
        ma = df['close'].rolling(window).mean()
        bb_width = (std * 4) / (ma + 1e-9)
        
        # 判断波动率状态
        vol_hist = bb_width.tail(100)
        is_squeeze = bb_width.iloc[-1] < vol_hist.quantile(0.2)
        
        return {
            "er": er,
            "bb_width": bb_width.iloc[-1],
            "is_squeeze": is_squeeze,
            "regime": "TREND" if er > 0.4 else "RANGE"
        }

class MacroMarketFilter:
    """
    宏观市场滤网：集成 VIX 风险偏好与 IXIC 指数确认
    """
    def __init__(self, vix_ticker="^VIX", ixic_ticker="^IXIC"):
        self.vix_ticker = vix_ticker
        self.ixic_ticker = ixic_ticker
        
    def get_macro_signals(self, window=20) -> Dict[str, Any]:
        # 下载近期宏观数据 (通常只需获取最近 60 天)
        vix_data = yf.download(self.vix_ticker, period="60d", interval="1d", progress=False)
        ixic_data = yf.download(self.ixic_ticker, period="60d", interval="1d", progress=False)
        
        # 1. VIX 状态分析
        curr_vix = vix_data['Close'].iloc[-1]
        vix_ma = vix_data['Close'].rolling(window).mean().iloc[-1]
        vix_std = vix_data['Close'].rolling(window).std().iloc[-1]
        
        # VIX 阶梯风险等级: 0(安全), 1(警戒), 2(极度恐慌)
        risk_level = 0
        if curr_vix > 30 or curr_vix > (vix_ma + 2 * vix_std):
            risk_level = 2  # 极度恐慌，应考虑清仓或对冲
        elif curr_vix > 20 or curr_vix > vix_ma:
            risk_level = 1  # 风险上升，应限制仓位
            
        # 2. IXIC (纳指) 动量确认
        # 判断科技股整体是否处于上升趋势
        ixic_sma = ixic_data['Close'].rolling(window).mean().iloc[-1]
        ixic_trend = "BULL" if ixic_data['Close'].iloc[-1] > ixic_sma else "BEAR"
        
        return {
            "vix_value": round(float(curr_vix), 2),
            "risk_level": risk_level,
            "ixic_trend": ixic_trend,
            "market_status": "RISK_OFF" if risk_level >= 1 or ixic_trend == "BEAR" else "RISK_ON"
        }

