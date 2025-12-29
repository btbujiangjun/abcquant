import numpy as np
import pandas as pd
from itertools import product
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from functools import partial
from utils.logger import logger
from backtest.engine import BacktestEngine

class Analyzer:
    @staticmethod
    def performance(df):
        result = {
            "total_return": 0,      # 总收益率
            "annual_return": 0,     # 年化收益率    
            "max_drawdown": 0,      # 最大回撤
            "win_rate": 0,          # 日度胜率
            "trade_win_rate": 0,    # 按笔胜率 (买/卖对)
            "trade_count": 0,       # 总交易次数 (一买一卖算一次)
            "sharpe": 0,            # 夏普比率
            "total_days": 0,        # 交易天数
            "trade_days": 0,        # 持仓天数
            "empty_days": 0,        # 空仓天数
            "calmar": 0,            # 卡玛比率
            "pl_ratio": 0,          # 盈亏比
        }

        if df.empty:
            return result

        equity = df['equity'].values
        total_days = len(equity)
        result["total_days"] = total_days
        result["total_return"] = float(equity[-1] / equity[0] - 1)

        # 1. 计算每日收益率与天数统计
        returns = np.diff(equity) / (equity[:-1] + 1e-9)
        is_trading = np.abs(returns) > 1e-9
        result["trade_days"] = int(np.sum(is_trading))
        result["empty_days"] = int(result["total_days"] - result["trade_days"])

        # 2. 按笔胜率统计 (核心新增逻辑)
        trades_profits, buy_price = [], None
        for _, row in df.iterrows():
            if row['ops'] == 'BUY':
                buy_price = row['equity']
            elif row['ops'] == 'SELL' and buy_price is not None:
                # 计算这一笔交易的盈亏百分比
                profit = (row['equity'] - buy_price) / buy_price
                profit = row['equity'] - buy_price
                trades_profits.append(profit)
                buy_price = None # 重置，等待下次买入

        result["trade_count"] = len(trades_profits)
        if result["trade_count"] > 0:
            win_trades = [p for p in trades_profits if p > 0]
            result["trade_win_rate"] = float(len(win_trades) / result["trade_count"])

        # 3. 滚动最大回撤
        peak = np.maximum.accumulate(equity)
        max_drawdown = np.max((peak - equity) / (peak + 1e-9))
        result["max_drawdown"] = float(max_drawdown)

        # 4. 日度活跃日胜率
        active_returns = returns[is_trading]
        if len(active_returns) > 0:
            result["win_rate"] = float(np.sum(active_returns > 0) / len(active_returns))
            # 夏普
            std = np.std(active_returns)
            result["sharpe"] = float(np.sqrt(252) * np.mean(active_returns) / (std + 1e-9))

            # 盈亏比 (平均盈利 / 平均亏损的绝对值)
            pos_ret = active_returns[active_returns > 0]
            neg_ret = active_returns[active_returns < 0]
            result["pl_ratio"] = float(np.mean(pos_ret) / np.abs(np.mean(neg_ret))) if len(neg_ret) > 0 else 0
        
        # 年化收益 / 最大回撤 (假设回测周期转换为年)
        annual_return = (result["total_return"] / total_days) * 252
        result["annual_return"] = annual_return
        result["calmar"] = float(annual_return / (max_drawdown + 1e-9))

        return result

    @staticmethod
    def _run_single_backtest(params, strategy_class, df):
        try:
            from backtest.engine import BacktestEngine
            strat = strategy_class(df, **params)
            signals = strat.generate_signals()
            engine = BacktestEngine()
            equity_df = engine.run_backtest(signals)
            perf = Analyzer.performance(equity_df)
            return params, perf, equity_df
        except Exception as e:
            logger.error(f"Error _run_single_backtest: {str(e)} {params} {strategy_class}")
            return params, {"total_return": -np.inf}, None

    @staticmethod
    def optimize_parameters(strategy_class, df, param_grid, n_jobs=-1):
        """
        并行版参数优化
        :param n_jobs: 使用的CPU核心数，-1表示使用全部
        """
        if isinstance(param_grid, str):
            raise ValueError(f"Analyzer 期望收到 dict 类型的参数网格，但收到的是字符串: {param_grid}")

        if param_grid is None or len(param_grid) == 0:
            param_combinations = [{}]
        else:
            keys = list(param_grid.keys())
            values = list(param_grid.values())
            param_combinations = [dict(zip(keys, v)) for v in product(*values)]
        
        best_perf_value = -np.inf
        best_params, best_equity, best_perf = {}, None, None

        workers = None if n_jobs == -1 else n_jobs
        func = partial(Analyzer._run_single_backtest, strategy_class=strategy_class, df=df)

        with ProcessPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(func, param_combinations))

        # 遍历结果找最优解(当前只考虑总收益，可能需要多角度衡量)
        for params, perf_val, equity_df in results:
            if equity_df is not None and perf_val["total_return"] > best_perf_value:
                best_perf, best_perf_value = perf_val, perf_val["total_return"]
                best_params, best_equity = params, equity_df
        return best_params, best_perf, best_equity

