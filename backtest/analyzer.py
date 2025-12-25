import numpy as np
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
        from itertools import product
        best_perf = -np.inf
        best_params = None
        keys, values = zip(*param_grid.items())
        print(f"keys:{keys}")
        print(f"values:{values}")
        for v in product(*values):
            params = dict(zip(keys,v))

            print(params)

            strat = strategy_class(df, **params)
            signals = strat.generate_signals()
            engine = BacktestEngine()
            equity_df = engine.run_backtest(signals)
            perf = Analyzer.performance(equity_df)['total_return']
            if perf > best_perf:
                best_perf = perf
                best_params = params
        return best_params, best_perf
