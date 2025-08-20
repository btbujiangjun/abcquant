# agents/scheduler_agent.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from utils.logger import log
from config import STOCK_TICKERS
from .storage_agent import StorageAgent
from .data_fetcher_agent import DataFetcherAgent

def daily_job():
    """每日执行的任务：爬取股票数据和新闻"""
    log.info("Scheduler Agent: Starting daily crawling job.")
    fetcher = DataFetcherAgent()
    storage = StorageAgent()
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    for ticker in STOCK_TICKERS:
        # 爬取股票数据
        stock_df = fetcher.fetch_stock_data(ticker, start_date, end_date)
        if stock_df is not None and not stock_df.empty:
            stock_df['ticker'] = ticker
            storage.save_stock_data(stock_df)
        
        # 爬取新闻数据
        news_df = fetcher.fetch_news_data(ticker)
        if news_df is not None and not news_df.empty:
            storage.save_news_data(news_df)

class SchedulerAgent:
    def __init__(self):
        self.scheduler = BackgroundScheduler()

    def start_scheduler(self):
        """启动调度器"""
        # 每天早上9点执行一次
        self.scheduler.add_job(daily_job, 'cron', hour=9, minute=0)
        # 也可以添加其他定时任务，例如每小时爬取一次实时数据
        
        log.info("Scheduler Agent: Scheduler started.")
        self.scheduler.start()
