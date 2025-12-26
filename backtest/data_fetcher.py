from db import QuantDB
import pandas as pd
import yfinance as yf
from utils.logger import logger

class DataFetcher:
    def __init__(self, db_path:str="./data/quant_data.db"):
        self.db = QuantDB(db_path)
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

    def fetch_yahoo(self, symbol, start, end):
        logger.info(f"Fetching {symbol} data from Yahoo Finance")
        df = yf.download(symbol, start=start, end=end)
        df.reset_index(inplace=True)
        df.rename(columns={'Date':'date','Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'}, inplace=True)
        return df

    def fetch_csv(self, file_path):
        logger.info(f"Loading data from {file_path}")
        df = pd.read_csv(file_path)
        assert all([field in df.columns for field in self.fields]), f"fields:{self.fields} are required" 
        return df
