import ast
import json
import pandas as pd
from typing import Tuple, Type, Dict, Any
from db import QuantDB
from utils.logger import logger
from backtest.strategy import BaseStrategy
from backtest.data_fetcher import DataFetcher
from backtest.analyzer import Analyzer
from backtest.engine import BacktestEngine
from backtest.strategy_registry import StrategyRegistry

class Worker:
    def __init__(self, engine=None, n_jobs=-1):
        self.engine = engine or BacktestEngine()
        self.strategy_configs = []
        self.n_jobs = n_jobs

    def append_strategy(self, strategy_config:Tuple[Type[BaseStrategy], Dict[str, Any]]):
        strategy, param_config = strategy_config
        param_config = param_config or {}
        self.strategy_configs.append((strategy, param_config))
        logger.info(f"append strategy:{strategy.__name__} {param_config}")

    def backtest(self, df: pd.DataFrame):
        final_results = {}
        for strategy_class, param_grid in self.strategy_configs:
            best_params, best_perf, best_equity = Analyzer.optimize_parameters(
                strategy_class, df, param_grid, n_jobs=self.n_jobs
            )
            best_perf["best_params"] = json.dumps(best_params)
            final_results[strategy_class.strategy_name] = {
                "name":strategy_class.display, "perf": best_perf, "equity_df": best_equity
            }
        return final_results

class DynamicWorker:
    def __init__(self, engine=None, n_jobs=-1):
        self.fetcher = DataFetcher()
        self.worker = Worker(engine or BacktestEngine(), n_jobs=n_jobs)

    def register_strategies(self, df: pd.DataFrame):
        self.worker.strategy_configs = [] 
        for _, row in df.iterrows():
            class_name = row['strategy_class']
            raw_params = row['param_configs']
            strategy_cls = StrategyRegistry.get_class(class_name)
            if not strategy_cls:
                logger.error(f"❌ 未能加载策略类: {class_name}")
                continue

            strategy_cls.display = row["strategy_name"]
            target_params = {}
            if isinstance(raw_params, dict):
                target_params = raw_params
            elif isinstance(raw_params, str):
                raw_params = raw_params.strip()
                try:
                    target_params = json.loads(raw_params)
                    if isinstance(target_params, str):
                        target_params = json.loads(target_params)
                except:
                    logger.error(f"❌ 字符串解析失败 [{class_name}]: {e}")
                    target_params = {}
            else:
                target_params = {}
            if not isinstance(target_params, dict):
                target_params = {}

            self.worker.append_strategy((strategy_cls, target_params))
            
        logger.info(f"📊 成功加载 {len(self.worker.strategy_configs)} 个策略")



    def backtest(self, symbol: str, start_date: str, end_date: str):
        """执行回测"""
        logger.info(f"🔍 正在为 {symbol} 执行回测...")
        df_data = self.fetcher.fetch_llm_data(symbol, start_date, end_date)
        self.register_strategies(QuantDB().fetch_strategy_pool()) 
        
        if df_data is None or df_data.empty:
            logger.error("数据源为空，无法执行回测")
            return {}
            
        return self.worker.backtest(df_data)



