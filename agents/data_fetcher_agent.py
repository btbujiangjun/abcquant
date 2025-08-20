# agents/data_fetcher_agent.py
from spiders.yfinance_spider import YFinanceSpider
from spiders.news_spider import NewsSpider
from utils.logger import log

class DataFetcherAgent:
    def __init__(self):
        self.yfinance_spider = YFinanceSpider()
        self.news_spider = NewsSpider()

    def fetch_stock_data(self, ticker, start_date, end_date):
        """获取股票历史数据"""
        log.info(f"Fetcher Agent: Fetching stock data for {ticker}")
        return self.yfinance_spider.get_stock_data(ticker, start_date, end_date)

    def fetch_news_data(self, ticker):
        """获取财经新闻"""
        log.info(f"Fetcher Agent: Fetching news for {ticker}")
        return self.news_spider.get_baidu_news(ticker)
