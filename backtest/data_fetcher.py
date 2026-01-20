from db import QuantDB
import pandas as pd
import yfinance as yf
from utils.logger import logger
from spiders.stock_spider import YF_US_Spider

class DataFetcher:
    def __init__(self, db_path:str="./data/quant_data.db"):
        self.db = QuantDB(db_path)
        self.yf_spider = YF_US_Spider()
        self.fields = ['date', 'open', 'high', 'low', 'close', 'volume']

    def fetch_llm_data(self, symbol, start:str|None=None, end:str|None=None):
        logger.info(f"Fetching {symbol} llm analysis data")
        df = self.db.query_analysis_report(
            symbol=symbol,
            start_date=start,
            end_date=end,
        )
        df['score'] = df['three_filters_score']
        df = df[self.fields + ['score']]
        return df

    def fetch_db(self, symbol, start:str|None=None, end:str|None=None):
        logger.info(f"Fetching {symbol} data from db")
        df = self.db.query_stock_price(
            symbol = symbol,
            interval = 'daily',
            start_date = start,
            end_date = end,
        ) 
        df = df[self.fields]
        return df

    def fetch_yf(self, symbol, start, end):
        logger.info(f"Fetching {symbol} data from Yahoo Finance")
        return self.yf_spider.fetch_stock_data(symbol, "daily", start, end)

    def fetch_csv(self, file_path):
        logger.info(f"Loading data from {file_path}")
        df = pd.read_csv(file_path)
        assert all([field in df.columns for field in self.fields]), f"fields:{self.fields} are required" 
        return df

    def fetch_us_macro(self, start:str|None=None, end:str|None=None):
        logger.info(f"Fetching US Macro data from db")
        return {symbol:self.db.query_stock_price(
            symbol = symbol,
            interval = 'daily',
            start_date = start,
            end_date = end,
        )[self.fields] for symbol in ['VIX', 'IXIC']}

