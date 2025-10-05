# agents/scheduler.py
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from utils.logger import logger
from spiders.stock_spider import BaseStockSpider, YF_US_Spider
from quant.strategy import StrategyHelper

def us_spider_price_job(
        spider:BaseStockSpider, 
        name:str="YF_US_Spider_price"
    ):
    logger.info(f"job {name} starting...")
    spider.update_latest()
 
def us_spider_info_job(
        spider:BaseStockSpider, 
        name:str="YF_US_Spider_info"
    ):
    logger.info(f"job {name} starting...")
    spider.update_stock_info()
 
def strategy_job(name:str="LLMStrategy"):
    logger.info(f"job {name} starting...")
    strategy = StrategyHelper()
    strategy.update_latest()
 

class Scheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()

    def start(self, hour:int=9, minute:int=0):
        """启动调度器"""
        # 每天早上9点执行一次
        #self.scheduler.add_job(daily_job, 'cron', hour=hour, minute=minute)
        #self.scheduler.add_job(daily_job, 'interval', seconds=5, kwargs={'name':'Bob'})
        spider = YF_US_Spider()
        self.scheduler.add_job(
            us_spider_price_job, 
            "date",
            run_date=datetime.now(),
            kwargs={"spider":spider, "name":"Yfinance US spider price"}
        )
        self.scheduler.add_job(
            us_spider_info_job, 
            "date",
            run_date=datetime.now(),
            kwargs={"spider":spider, "name":"Yfinance US spider info"}
        )
        self.scheduler.add_job(
            strategy_job, 
            "date",
            run_date=datetime.now(),
            kwargs={"name":"LLM Strategy"}
        )

        logger.info("Scheduler Agent: Scheduler started.")
        self.scheduler.start()
 
    def shutdown(self, wait:bool=True):
        logger.info("Scheduler Agent: Scheduler shutdown...")
        self.scheduler.shutdown(wait=wait)
