# spiders/yfinance_spider.py

import os
import yfinance as yf
from config import STOCKS_PATH

class YFinanceSpider:
    def get_stock_data(self, symbol, start_date, end_date):
        """从yfinance获取股票历史数据"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)
            return df
        except Exception as e:
            print(f"YFinance Spider: An error occurred for {symbol}: {e}")
            return None

    def save_data(self, df, symbol):
        """将数据保存到本地文件"""
        file_path = os.path.join(STOCKS_PATH, f"{symbol}_yfinance.csv")
        df.to_csv(file_path)
        print(f"YFinance Spider: {symbol} data saved to {file_path}")
