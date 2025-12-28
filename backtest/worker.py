import json
import pandas as pd
from utils.logger import logger
from backtest.data_fetcher import DataFetcher
from backtest.analyzer import Analyzer
from backtest.engine import BacktestEngine
from backtest.strategy import(
    BaseStrategy, 
    RSIStrategy, 
    BollingerStrategy, 
    VolatilityLLMStrategy, 
    LongTermValueStrategy, 
    EMACrossStrategy, 
    LLMStrategy,
    ATRStopLLMStrategy,
    KeltnerStrategy,
    VolumePriceStrategy,
    TripleBarrierLLMStrategy,
    AdaptiveVolStrategy,
)

class Worker:
    def __init__(self, engine=None, n_jobs=-1):
        self.engine = engine or BacktestEngine()
        self.strategy_configs = []
        self.n_jobs = n_jobs

    def append_strategy(self, strategy_config):
        strategy, param_config = strategy_config 
        param_config = param_config or {}
        self.strategy_configs.append((strategy, param_config))
        logger.info(f"append strategy:{strategy.__name__} {param_config}")

    def backtest(self, df: pd.DataFrame):
        final_results = {}
        
        for strategy_class, param_grid in self.strategy_configs:
            best_params, best_perf, best_equity = Analyzer.optimize_parameters(
                strategy_class, 
                df, 
                param_grid, 
                n_jobs=self.n_jobs
            )
            best_perf["best_params"] = json.dumps(best_params)
            final_results[strategy_class.strategy_name] = {
                "perf": best_perf,
                "equity_df": best_equity
            }
            
        return final_results

class DefaultWorker:
    def __init__(self, engine=None):
        self.fetcher = DataFetcher()
        self.worker = Worker(engine or BacktestEngine())
        self.worker.append_strategy((LongTermValueStrategy, None))
        self.worker.append_strategy((
            RSIStrategy, 
            {'period':[14], 'low':[20, 30, 40], 'high':[60, 70, 80]}
        ))
        self.worker.append_strategy((
            BollingerStrategy, 
            {'period':[15, 20, 25], 'std_dev':[2], 'coefficient':[0.1, 0.05]}
        ))
        self.worker.append_strategy((
            KeltnerStrategy, 
            {
                'period':[15, 20, 25], 
                'multiplier':[1.5, 2.0, 2.5], 
                'coefficient':[0.1, 0.05, 0.0],
            }
        ))
        self.worker.append_strategy((
            VolumePriceStrategy, 
            {
                'vol_period':[15, 20, 25], 
                'price_period':[5, 10, 15], 
                'buy_vol_rate':[0.2, 0.5, 0.7],
                "buy_price_rate":[0.05, 0.1, 0.15],
                "sell_price_rate":[-0.05, -0.1, -0.15],
            }
        ))
        self.worker.append_strategy((
            TripleBarrierLLMStrategy, 
            {
                'buy_score':[0.5, 0.6, 0.7, 0.8], 
                'sell_score':[0.0, 0.2, -0.1], 
                'rsi_period':[7, 14, 21],
                "ma_period":[90, 150, 200],
                "rsi_limit":[60, 70, 80],
            }
        ))
        self.worker.append_strategy((
            AdaptiveVolStrategy, 
            {
                'window':[30, 45, 60], 
                'atr_period':[7, 14, 21],
            }
        ))
        self.worker.append_strategy((
            VolatilityLLMStrategy, 
            {
                'buy_score':[0.5, 0.6, 0.7, 0.8], 
                'sell_score':[0.0, 0.2, -0.1], 
                'period':[5, 10, 15], 
                'vol_threshold':[0.03, 0.1, 0.15],
            }
        ))
        self.worker.append_strategy((
            EMACrossStrategy, 
            {'short':[10,12,15], 'long':[20,26,30]}
        ))
        self.worker.append_strategy((
            ATRStopLLMStrategy, 
            {
                'buy_score':[0.5, 0.6, 0.7, 0.8], 
                'sell_score':[0.0, 0.2, -0.1], 
                'period':[7, 14, 21], 
                'atr_multiplier':[1.0, 1.5, 2.0],
            }
        ))
        self.worker.append_strategy((
            LLMStrategy, 
            {'buy_score':[0.5, 0.6, 0.7, 0.8], 'sell_score':[0.0, 0.2, -0.1]}
        ))

    def backtest(self, symbol:str, start_date, end_date):
        df = self.fetcher.fetch_llm_data(symbol, start_date, end_date)
        return self.worker.backtest(df)




