from backtest.data_fetcher import DataFetcher
from backtest.strategy import LongTermValueStrategy, EMACrossStrategy, LLMStrategy
from backtest.engine import BacktestEngine
from backtest.analyzer import Analyzer
from utils.logger import logger
from backtest.worker import Worker


def main():
    fetcher = DataFetcher()
    symbols = ["XPEV", "TSLA", "LI", "NVDA"]  # 多品种回测
    results = []

    testor = Worker()
    testor.append_strategy(LongTermValueStrategy)
    testor.append_strategy(EMACrossStrategy, {'short':[10,12,15], 'long':[20,26,30]})
    testor.append_strategy(LLMStrategy, {'buy_score':[0.5, 0.6, 0.7, 0.8], 'sell_score':[0.0, 0.2, -0.1]})


    for symbol in symbols:
        df = fetcher.fetch_llm_data(symbol, "2025-01-01", "2025-12-31")
        print(df)
        results.append({symbol:testor.backtest(df)})

    print(results)

    return

        
    for symbol in symbols:
        df = fetcher.fetch_llm_data(symbol, "2025-01-01", "2025-12-31")
        #df = fetcher.fetch_yahoo(symbol, "2022-01-01", "2025-10-05")

        print(f"df:{len(df)}")
        print(df.head())

        # 参数优化
        param_grid = {'short':[10,12,15], 'long':[20,26,30]}
        best_params, best_perf = Analyzer.optimize_parameters(EMACrossStrategy, df, param_grid)
        strategy = EMACrossStrategy(df, **best_params)

        param_grid = {'buy_score':[0.5, 0.6, 0.7, 0.8], 'sell_score':[0.0, 0.2, -0.1]}
        best_params, best_perf = Analyzer.optimize_parameters(LLMStrategy, df, param_grid)
        logger.info(f"{symbol} Best Params: {best_params}, Best Return: {best_perf:.2%}")

        # 使用最优参数回测
        strategy = LLMStrategy(df, **best_params)
        signals = strategy.generate_signals()
        engine = BacktestEngine(initial_cash=100000)
        equity_df = engine.run_backtest(signals)

        perf = Analyzer.performance(equity_df)
        results[symbol] = perf
        logger.info(f"{symbol} Backtest Performance: {perf}")

        #价值投资
        param_grid = {}
        best_params, best_perf = Analyzer.optimize_parameters(LongTermValueStrategy, df, param_grid)
        value_strategy = LongTermValueStrategy(df)
        value_signals = value_strategy.generate_signals()
        engine = BacktestEngine(initial_cash=100000)
        equity_df = engine.run_backtest(value_signals)

        perf = Analyzer.performance(equity_df)
        print(f"value strategy:{perf}") 

        # 可视化
        engine.plot_equity(equity_df, symbol)

    logger.info(f"All Symbols Performance: {results}")

if __name__ == "__main__":
    main()
