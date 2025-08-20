# agents/storage_agent.py
from utils.logger import log
from db import save_dataframe_to_db

class StorageAgent:
    def save_stock_data(self, df):
        """保存股票历史数据到数据库"""
        log.info("Storage Agent: Saving stock prices to DB")
        # 转换列名以匹配数据库表
        df.rename(columns={'Date': 'date', 'Open': 'open', 'High': 'high', 
                           'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)
        # 添加 ticker 列
        if not 'ticker' in df.columns:
            # 这里的 ticker 需要从调用者传递过来
            pass # 实际项目中需要从上游 agent 获取
        save_dataframe_to_db(df, 'stock_prices')

    def save_news_data(self, df):
        """保存新闻数据到数据库"""
        log.info("Storage Agent: Saving news to DB")
        save_dataframe_to_db(df, 'news')
