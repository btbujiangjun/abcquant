import json
import pandas as pd
import numpy as np
from typing import Tuple, Type, Dict, Any, Optional
from datetime import datetime

from db import QuantDB
from utils.logger import logger
from utils.time import today_str
from utils.format import str_to_dict, numpy_to_python
from config import CRITICAL_STOCKS_US
from core.market import MarketIdentifier
from backtest.strategy import BaseStrategy, LLMStrategy
from backtest.data_fetcher import DataFetcher
from backtest.analyzer import Analyzer
from backtest.engine import BacktestEngine
from backtest.strategy_registry import StrategyRegistry
from backtest.ensemble import EnsembleEngine

class Worker:
    def __init__(self, engine=None, 
            n_jobs=1,
            target_risk_ratio=2,
            max_leverage=1,
            is_long_only=True):
        self.engine = engine or BacktestEngine()
        self.strategy_configs = []
        self.n_jobs = n_jobs
        self.ensemble = EnsembleEngine(target_risk_ratio, max_leverage, is_long_only)

    def append_strategy(self, strategy_config: Tuple[Type[BaseStrategy], Dict[str, Any]]):
        strategy_cls, param_config = strategy_config
        self.strategy_configs.append((strategy_cls, param_config or {}))
        logger.debug(f"✅ 已添加策略: {strategy_cls.__name__} | 参数网格数量: {len(param_config) if param_config else 0}")

    def backtest(self, 
            symbol: str, 
            df: pd.DataFrame, 
            df_macro: Dict[str, pd.DataFrame]=None,
            current_pos: int = 0) -> Tuple[Dict, Dict]:
        """执行组合回测并生成融合报告"""
        signals = {}
        if not self.strategy_configs:
            logger.warning("⚠️ 未配置任何策略，回测跳过")
            return {}, {}

        for strategy_class, param_grid in self.strategy_configs:
            logger.info(f"🚀 正在优化策略: {strategy_class.strategy_class}...")
            best_params, best_perf, best_equity = Analyzer.optimize_parameters(
                strategy_class, df, param_grid, n_jobs=self.n_jobs
            )
            
            signals[strategy_class.strategy_class] = {
                "symbol": symbol,
                "strategy_name": strategy_class.strategy_name, 
                "strategy_class": strategy_class.strategy_class,
                "param_config": best_params,
                "perf": best_perf,
                "equity_df": best_equity,
            }

        report = self.ensemble.action(signals, df, df_macro, current_pos=current_pos)
        return signals, report

class DynamicWorker:
    def __init__(self, 
            engine=None, 
            n_jobs=1,
            target_risk_ratio=2,
            max_leverage=1,
            is_long_only=True,
        ):
        self.db = QuantDB()
        self.fetcher = DataFetcher()
        self.worker = Worker(
            engine or BacktestEngine(), 
            n_jobs=n_jobs,
            target_risk_ratio = target_risk_ratio,
            max_leverage = max_leverage,
            is_long_only = is_long_only,
        )

    def register_strategies(self, not_llm=False):
        df_pool = self.db.fetch_strategy_pool()
        if df_pool is None or df_pool.empty:
            logger.warning("🟡 策略池为空")
            return

        self.worker.strategy_configs = [] 
        for _, row in df_pool.iterrows():
            class_key = row['strategy_class']
            strategy_cls = StrategyRegistry.get_class(class_key)
            
            if not strategy_cls:
                logger.error(f"❌ 未知策略类，请检查 Registry: {class_key}")
                continue

            if not_llm and class_key != "BaseStrategy" and \
                    (class_key == "LLMStrategy" or \
                    strategy_cls.__base__.__name__ == "LLMStrategy"):
                continue

            # 注入元数据
            strategy_cls.strategy_name = row.get("strategy_name", class_key)
            strategy_cls.strategy_class = class_key

            try:            
                params = str_to_dict(row.get('param_configs'))
                self.worker.append_strategy((strategy_cls, params))
            except Exception as e:
                logger.error(f"❌ 参数解析失败: [{class_key}]{str(e)}")

        logger.info(f"📊 动态加载完成，共计 {len(self.worker.strategy_configs)} 个有效策略")

    def _backtest(self, 
            symbol: str, 
            df_data: pd.DataFrame,
            df_macro: Dict[str, pd.DataFrame]=None) -> Tuple[Dict, Dict]:
        """执行完整回测流程"""
        if df_data is None or df_data.empty:
            logger.error(f"❌ {symbol} 数据数据不能为空")
            return {}, {}
            
        return self.worker.backtest(symbol, df_data, df_macro)

    def _macro_data(self, symbol:str, start_date: str, end_date: str):
        return self.fetcher.fetch_us_macro(start_date, end_date) if MarketIdentifier.identify(symbol) == 'US' else {}

    def backtest_llm_db(self, symbol: str, start_date: str, end_date: str) -> Tuple[Dict, Dict]:
        df_data = self.fetcher.fetch_llm_data(symbol, start_date, end_date)
        self.register_strategies() 
        return self._backtest(symbol, df_data, self._macro_data(symbol, start_date, end_date))

    def backtest_online(self, symbol: str, start_date: str, end_date: str) -> Tuple[Dict, Dict]:
        df_data = self.fetcher.fetch_yf(symbol, start_date, end_date)
        self.register_strategies(not_llm=True) 
        return self._backtest(symbol, df_data, self._macro_data(symbol, start_date, end_date))

    def backtest(self, symbol: str, start_date: str, end_date: str) -> Tuple[Dict, Dict]:
        if symbol in CRITICAL_STOCKS_US:
            return self.backtest_llm_db(symbol, start_date, end_date)
        else:
            return self.backtest_online(symbol, start_date, end_date)

    def backtest_daily(self, symbol: str):
        """例行任务：回测、融合并持久化至 SQLite"""
        start_date = "2020-01-01"
        end_date = today_str()
        
        try:
            results, report = self.backtest(symbol, start_date, end_date)

            if not results or not report:
                logger.warning(f"🟡 {symbol} 回测结果为空，放弃入库")
                return

            # 处理数据类型安全 (防止 numpy 类型导致 json 序列化失败)
            #safe_report = self._serialize_for_db(report)
            report = numpy_to_python(report)
            
            res_signal = self.db.update_strategy_signal(results)
            res_report = self.db.update_strategy_report(symbol, report)

            if res_signal > 0 and res_report > 0:
                logger.info(f"💚 {symbol} 每日例行任务成功入库 | 建议仓位: {report.get('suggested_position')}")
            else:
                logger.error(f"⚠️ {symbol} 入库失败 [Signal:{res_signal}, Report:{res_report}]")
                
        except Exception as e:
            logger.exception(f"🔥 {symbol} 天级回测发生致命错误: {e}")
