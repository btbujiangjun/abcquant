# spiders/finnhub_spider.py

import os
from datetime import datetime
import finnhub
import pandas as pd
from config import FINNHUB_API_KEY, STOCKS_PATH

class FinnhubSpider:
    def __init__(self):
        self.client = finnhub.Client(api_key=FINNHUB_API_KEY)

    def get_stock_candles(self, symbol, start_date, end_date):
        """获取股票K线数据"""
        try:
            _from = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
            _to = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp())
            
            # 这里需要注意，免费API可能不支持K线数据，可能需要付费计划
            data = self.client.stock_candles(symbol, 'D', _from, _to)
            
            if data and data.get('s') == 'ok':
                df = pd.DataFrame(data)
                df['t'] = pd.to_datetime(df['t'], unit='s')
                df.set_index('t', inplace=True)
                return df
            else:
                print(f"Finnhub Spider: Failed to get candle data for {symbol}. Error: {data.get('s', 'Unknown')}")
                return None
        except Exception as e:
            print(f"Finnhub Spider: An error occurred for {symbol}: {e}")
            return None

    def save_data(self, df, symbol, data_type):
        """将数据保存到本地文件"""
        file_path = os.path.join(STOCKS_PATH, f"{symbol}_{data_type}.csv")
        df.to_csv(file_path)
        print(f"Finnhub Spider: {symbol} {data_type} data saved to {file_path}")
