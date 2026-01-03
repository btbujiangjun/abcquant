import numpy as np
import pandas as pd
from itertools import product
from functools import partial
from dataclasses import asdict
from typing import Dict, Any, Tuple, Optional, List, Union
from concurrent.futures import ProcessPoolExecutor
from utils.logger import logger
from backtest.metrics import PositionStatus, PerformanceMetrics

class Analyzer:
    """
    量化回测分析器
    功能点：向量化计算、状态机追踪、多进程并行、异常隔离
    """
    TRADING_DAYS_PER_YEAR = 252
    EPSILON = 1e-12

    @staticmethod
    def performance(df: pd.DataFrame) -> Dict[str, Any]:
        """
        计算回测表现指标
        :param df: 包含 'equity' (净值) 和 'ops' (操作: BUY/SELL/空字符串) 的 DataFrame
        """
        if df is None or df.empty or 'ops' not in df or 'equity' not in df:
            return asdict(PerformanceMetrics())

        # 1. 基础数据准备
        equity = df['equity'].to_numpy(dtype=np.float64)
        total_days = len(equity)
        returns = np.diff(equity) / (equity[:-1] + Analyzer.EPSILON)
        
        # 2. 交易状态与按笔盈亏逻辑
        trade_count, trade_win_rate, last_trade_pnl = 0, 0.0 , 0.0
        current_pos = PositionStatus.EMPTY.value
        is_in_pos = False

        if 'ops' in df.columns:
            # 获取买入和卖出的索引位置
            buy_mask = df['ops'] == 'BUY'
            sell_mask = df['ops'] == 'SELL'
            
            buy_indices = df.index[buy_mask].tolist()
            sell_indices = df.index[sell_mask].tolist()
            
            # 计算已完成的每笔交易盈亏
            n_completed = min(len(buy_indices), len(sell_indices))
            if n_completed > 0:
                buy_prices = df.loc[buy_mask, 'equity'].values[:n_completed]
                sell_prices = df.loc[sell_mask, 'equity'].values[:n_completed]
                
                # 向量化计算盈亏比：(卖出价 - 买入价) / 买入价
                trade_profits = (sell_prices - buy_prices) / (buy_prices + Analyzer.EPSILON)
                trade_count = n_completed
                trade_win_rate = float(np.sum(trade_profits > 0) / n_completed)
                last_trade_pnl = float(trade_profits[-1])

            # 判定当前实时状态
            # 找到最后一个非空操作
            valid_ops = df[df['ops'].isin(['BUY', 'SELL'])]
            if not valid_ops.empty:
                last_op = valid_ops['ops'].iloc[-1]
                if last_op == 'BUY':
                    current_pos = PositionStatus.HOLDING.value
                    is_in_pos = True
                    # 计算当前持仓的浮动盈亏
                    last_buy_price = valid_ops['equity'].iloc[-1]
                    last_trade_pnl = float((equity[-1] - last_buy_price) / (last_buy_price + Analyzer.EPSILON))

        # 3. 风险与收益指标向量化计算
        total_ret = float(equity[-1] / equity[0] - 1)
        ann_ret = (total_ret / total_days) * Analyzer.TRADING_DAYS_PER_YEAR
        
        # 最大回撤
        rolling_max = np.maximum.accumulate(equity)
        drawdowns = (rolling_max - equity) / (rolling_max + Analyzer.EPSILON)
        max_dd = float(np.max(drawdowns))

        # 活跃日统计 (有收益变动的日子)
        active_mask = np.abs(returns) > Analyzer.EPSILON
        active_returns = returns[active_mask]
        
        win_rate, sharpe, pl_ratio = 0.0, 0.0, 0.0
        
        if len(active_returns) > 0:
            win_rate = float(np.sum(active_returns > 0) / len(active_returns))
            mean_ret = np.mean(active_returns)
            std_ret = np.std(active_returns)
            if std_ret > Analyzer.EPSILON:
                sharpe = float(np.sqrt(Analyzer.TRADING_DAYS_PER_YEAR) * mean_ret / std_ret)
            
            pos_avg = np.mean(active_returns[active_returns > 0]) if np.any(active_returns > 0) else 0
            neg_avg = np.abs(np.mean(active_returns[active_returns < 0])) if np.any(active_returns < 0) else 0
            pl_ratio = float(pos_avg / (neg_avg + Analyzer.EPSILON))

        # 4. 组装结果
        res = PerformanceMetrics(
            total_return=total_ret,
            annual_return=ann_ret,
            max_drawdown=max_dd,
            win_rate=win_rate,
            trade_win_rate=trade_win_rate,
            trade_count=trade_count,
            sharpe_ratio=sharpe,
            calmar_ratio=float(ann_ret / (max_dd + Analyzer.EPSILON)),
            profit_loss_ratio=pl_ratio,
            total_days=total_days,
            trade_days=int(np.sum(active_mask)),
            empty_days=int(total_days - np.sum(active_mask)),
            current_position=current_pos,
            is_in_position=is_in_pos,
            last_trade_pnl=last_trade_pnl
        )
        return asdict(res)

    @staticmethod
    def _run_worker(params, strategy_class, df):
        """子进程执行单元"""
        try:
            from backtest.engine import BacktestEngine 
            strat = strategy_class(df, **params)
            signals = strat.generate_signals()
            engine = BacktestEngine()
            equity_df = engine.run_backtest(signals)
            perf = Analyzer.performance(equity_df)
            return params, perf, equity_df
        except Exception as e:
            logger.error(f"Worker Error | Params: {params} | Msg: {str(e)}", exc_info=True)
            return params, {"total_return": -np.inf}, None

    @classmethod
    def optimize_parameters(cls, strategy_class, df, param_grid, n_jobs=-1, target_metric="total_return"):
        """
        并行参数优化
        :param target_metric: 优化目标，可选项参考 PerformanceMetrics 字段
        """
        if not isinstance(param_grid, dict):
            raise ValueError("param_grid must be a dictionary")

        # 生成笛卡尔积组合
        keys = list(param_grid.keys())
        combinations = [dict(zip(keys, v)) for v in product(*param_grid.values())] or [{}]
        
        logger.info(f"Starting Grid Search: {len(combinations)} combinations")
        
        best_params, best_perf, best_equity, max_score = {}, None, None, -np.inf

        # 并行计算
        workers = None if n_jobs == -1 else n_jobs
        worker_func = partial(cls._run_worker, strategy_class=strategy_class, df=df)

        with ProcessPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(worker_func, combinations))

        # 评估结果
        for params, perf, equity_df in results:
            if equity_df is not None:
                score = perf.get(target_metric, -np.inf)
                if score > max_score:
                    max_score = score
                    best_params, best_perf, best_equity = params, perf, equity_df

        return best_params, best_perf, best_equity
