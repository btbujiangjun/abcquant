import numpy as np
from itertools import product
from utils.logger import logger
from backtest.engine import BacktestEngine

class Analyzer:
    @staticmethod
    def performance(df):
        df = df.copy()
        df['returns'] = df['equity'].pct_change().fillna(0)
        total_return = df['equity'].iloc[-1]/df['equity'].iloc[0]-1
        max_drawdown = ((df['equity'].cummax()-df['equity'])/df['equity'].cummax()).max()
        win_rate = (df['returns']>0).sum()/len(df)
        return {"total_return":total_return, "max_drawdown":max_drawdown, "win_rate":win_rate}

    @staticmethod
    def optimize_parameters(strategy_class, df, param_grid):
        best_perf, best_params = -np.inf, {}
        
        if len(param_grid.items()) != 2:
            logger.info(f"optimize_parameters: two parameters are required")
            return best_params, best_perf    

        keys, values = zip(*param_grid.items())
        for v in product(*values):
            params = dict(zip(keys,v))
            strat = strategy_class(df, **params)
            signals = strat.generate_signals()
            engine = BacktestEngine()
            equity_df = engine.run_backtest(signals)
            perf = Analyzer.performance(equity_df)['total_return']
            if perf > best_perf:
                best_perf, best_params = perf, params
        return best_params, best_perf
