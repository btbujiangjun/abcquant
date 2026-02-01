from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

# --- 1. 数据模型：定义因子结构 ---
class MarketFactors(BaseModel):
    """市场风险因子数据模型"""
    vix: float = Field(22.0, description="波动率指数")
    adl_divergence: bool = Field(True, description="涨跌家数背离状态")
    ted_spread: float = Field(0.5, description="TED利差，衡量信用风险")
    liquidity_score: float = Field(0.8, ge=0, le=1, description="流动性评分 0-1")
    timestamp: datetime = Field(default_factory=datetime.now)

    @validator('vix')
    def check_vix_range(cls, v):
        if v < 0: raise ValueError("VIX cannot be negative")
        return v

# --- 2. 逻辑引擎：环境感知风控 ---
class MarketRegimeEngine:
    """环境感知状态机"""
    
    def __init__(self, factors: MarketFactors):
        self.f = factors

    def calculate_multiplier(self) -> float:
        """
        计算全局风险乘数 (Regime Multiplier)
        顶级逻辑：非线性惩罚 + 极端熔断
        """
        # 初始乘数
        multiplier = 1.0
        
        # 1. 波动率惩罚：使用阶梯或平滑函数
        if self.f.vix > 35:
            multiplier *= 0.4  # 极度恐慌
        elif self.f.vix > 25:
            multiplier *= 0.7  # 高波震荡
            
        # 2. 宽度背离 (Market Breadth)
        # 宽度背离意味着只有少数权重股在涨，确定性极低
        if self.f.adl_divergence:
            multiplier *= 0.6
            
        # 3. 流动性因子直接线性缩放
        multiplier *= self.f.liquidity_score

        # 4. 极端风险熔断 (TED Spread)
        # 如果信用利差突破 1.2（通常意味着类似2008的系统性危机），直接归零
        if self.f.ted_spread > 1.2:
            return 0.0

        # 确保结果在 [0, 1.2] 之间（允许在极度安全时小幅加杠杆）
        return round(max(0.0, multiplier), 4)

# --- 3. 调用示例 ---
if __name__ == "__main__":
    raw_data = {
        "vix": 28.5,
        "adl_divergence": True,
        "ted_spread": 0.4,
        "liquidity_score": 0.9
    }
    
    factors = MarketFactors(**raw_data)
    
    engine = MarketRegimeEngine(factors)
    result = engine.calculate_multiplier()
    
    print(f"[{factors.timestamp}] 市场风险乘数: {result}")
