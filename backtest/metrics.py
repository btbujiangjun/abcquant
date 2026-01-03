from enum import Enum
from dataclasses import dataclass, asdict

class PositionStatus(Enum):
    """定义持仓状态枚举"""
    HOLDING = "HOLDING"
    EMPTY = "EMPTY"

@dataclass(frozen=True)
class PerformanceMetrics:
    """性能指标数据模型"""
    total_return: float = 0.0       # 总收益率
    annual_return: float = 0.0      # 年化收益率
    max_drawdown: float = 0.0       # 最大回撤
    win_rate: float = 0.0           # 日度胜率
    trade_win_rate: float = 0.0     # 按笔胜率
    trade_count: int = 0            # 交易次数
    sharpe_ratio: float = 0.0      # 夏普比率
    calmar_ratio: float = 0.0       # 卡玛比率
    profit_loss_ratio: float = 0.0  # 盈亏比
    total_days: int = 0             # 交易天数 
    trade_days: int = 0             # 持仓天数
    empty_days: int = 0             # 空仓天数
    current_position: str = PositionStatus.EMPTY.value
    is_in_position: bool = False    # 是否持仓
    last_trade_pnl: float = 0.0     # 上次交易盈亏比（若在场内则为浮动盈亏）

