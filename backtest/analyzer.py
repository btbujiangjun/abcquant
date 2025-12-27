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
        if df.empty:
            return {"total_return": 0, "max_drawdown": 0, "win_rate": 0}
            
        equity = df['equity'].values
        total_return = equity[-1] / equity[0] - 1
        
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        max_drawdown = np.max(drawdown)
        
        # 胜率计算
        returns = np.diff(equity) / equity[:-1]
        win_rate = np.sum(returns > 0) / len(returns) if len(returns) > 0 else 0
        
        return {
            "total_return": total_return, 
            "max_drawdown": max_drawdown, 
            "win_rate": win_rate
        }

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
        if param_grid is None or len(param_grid) == 0:
            param_combinations = [{}]
        else:
            keys = list(param_grid.keys())
            values = list(param_grid.values())
            param_combinations = [dict(zip(keys, v)) for v in product(*values)]
        
        best_perf_value = -np.inf
        best_params = {}
        best_equity = None

        workers = None if n_jobs == -1 else n_jobs
        func = partial(Analyzer._run_single_backtest, strategy_class=strategy_class, df=df)

        with ProcessPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(func, param_combinations))

        # 遍历结果找最优解
        for params, perf_val, equity_df in results:
            if equity_df is not None and perf_val["total_return"] > best_perf_value:
                best_perf, best_perf_value = perf_val, perf_val["total_return"]
                best_params = params
                best_equity = equity_df

        return best_params, best_perf, best_equity

