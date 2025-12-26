import pandas as pd
from utils.logger import logger
from backtest.data_fetcher import DataFetcher
from backtest.analyzer import Analyzer
from backtest.engine import BacktestEngine
from backtest.strategy import BaseStrategy, LongTermValueStrategy, EMACrossStrategy, LLMStrategy

class Worker:
    def __init__(self, engine=BacktestEngine()):
        self.strategies = []
        self.params = []
        self.engine = engine

    def append_strategy(self, strategy, param_grid={}):
        self.strategies.append(strategy)
        self.params.append(param_grid)
        logger.info(f"append strategy:{strategy.__name__}")

    def backtest(self, df: pd.DataFrame):
        results = {}
        for strategy_class, param in zip(self.strategies, self.params):
            best_params, best_perf = Analyzer.optimize_parameters(strategy_class, df, param)
            
            logger.info(f"Best Params: {best_params}, Best Return: {best_perf:.2%}")

            strategy = strategy_class(df, **best_params)
            signals = strategy.generate_signals()            
            equity_df = self.engine.run_backtest(signals)
            perf = Analyzer.performance(equity_df)

            results[strategy.strategy_name] = {"equity_df": equity_df, "perf": perf}
            logger.info(f"{strategy.strategy_name} Backtest Performance: {perf}, Best Params:{best_params}")

        return results

class DefaultWorker:
    def __init__(self, engine=BacktestEngine()):
        self.fetcher = DataFetcher()
        self.worker = Worker(engine)
        self.worker.append_strategy(LongTermValueStrategy)
        self.worker.append_strategy(EMACrossStrategy, {'short':[10,12,15], 'long':[20,26,30]})
        self.worker.append_strategy(LLMStrategy, {'buy_score':[0.5, 0.6, 0.7, 0.8], 'sell_score':[0.0, 0.2, -0.1]})

    def backtest(self, symbol:str, start_date, end_date):
        df = self.fetcher.fetch_llm_data(symbol, start_date, end_date)
        return self.worker.backtest(df)




