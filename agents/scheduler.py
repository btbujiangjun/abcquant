# agents/scheduler.py
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from utils.logger import logger
from config import CRITICAL_STOCKS_US 
from quant.strategy import StrategyHelper
from spiders.stock_spider import BaseStockSpider, YF_US_Spider

def us_spider_job(name:str="YF_US_Spider"):
    spider = YF_US_Spider()
    logger.info(f"⚠️  job {name} starting...")
    spider.update_latest()
 
def strategy_job(name:str="LLMStrategy"):
    logger.info(f"⚠️  job {name} starting...")
    strategy = StrategyHelper()
    strategy.update_latest()

def hour_job(name:str="hour job for ctritical stock"):
    logger.info(f"⚠️  {name} 执行中... ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    spider = YF_US_Spider()
    spider.update_latest(symbols=CRITICAL_STOCKS_US)
    strategy = StrategyHelper()
    strategy.update_latest(symbols=CRITICAL_STOCKS_US, days=2, update=True)

class Scheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()

    def start(self, hour:int=9, minute:int=0):
        """启动调度器"""
        # 每天早上9点执行一次
        #self.scheduler.add_job(daily_job, 'cron', hour=hour, minute=minute)
        #self.scheduler.add_job(daily_job, 'interval', seconds=5, kwargs={'name':'Bob'})
        self.scheduler.add_job(
            hour_job, 
            'interval', 
            seconds=3600,
            #run_date=datetime.now(),
            kwargs={"name":"Hour job for critical stocks"}
        )
        self.scheduler.add_job(
            us_spider_job, 
            "date",
            run_date=datetime.now(),
            #"cron",
            #hour=12,
            #minute=0,
            kwargs={"name":"Yfinance US spider price"}
        )
        """
        self.scheduler.add_job(
            strategy_job, 
            "date",
            run_date=datetime.now(),
            kwargs={"name":"LLM Strategy"}
        )
        """
        logger.info("Scheduler Agent: Scheduler started.")
        self.scheduler.start()
 
    def shutdown(self, wait:bool=True):
        logger.info("Scheduler Agent: Scheduler shutdown...")
        self.scheduler.shutdown(wait=wait)
