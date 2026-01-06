# agents/scheduler.py
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from db import QuantDB
from quant.llm import ModelScopeClinet, OllamaClient
from utils.time import *
from utils.logger import logger
from config import CRITICAL_STOCKS_US 
from analysis.dragon import Dragon
from quant.strategy import StrategyHelper
from backtest.worker import DynamicWorker
from spiders.stock_spider import BaseStockSpider, YF_US_Spider

def us_spider_job(name:str, spider, dragon):
    logger.info(f"⚠️  job {name} starting...")
    #spider.refresh_stock_base()
    #spider.update_latest()
    spider.update_latest_batch(period=20)
    dragon.run_growth(days_delta(today_str(), -1))
 
def strategy_job(name:str, strategy, dragon):
    logger.info(f"⚠️  job {name} starting...")
    strategy.update_latest()
    dragon.run_growth(days_delta(today_str(), -1))

def hour_job(name:str, spider, strategy, dragon, worker):
    logger.info(f"⚠️  {name} 执行中... ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    #CRITICAL_STOCKS_US = ["BTC-USD", "XPEV"]
    spider.update_latest_batch(symbols=CRITICAL_STOCKS_US)
    strategy.update_latest(symbols=CRITICAL_STOCKS_US, days=3, update=False)
    dragon.run_report(days_delta(today_str(), -1))
    
    #worker.backtest_daily("GOOG")

    for symbol in CRITICAL_STOCKS_US:
        worker.backtest_daily(symbol)

    logger.info("hour_job finished")

class Scheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.dragon = Dragon()
        self.spider = YF_US_Spider()
        self.worker = DynamicWorker()
        self.strategy = StrategyHelper(ModelScopeClinet(), QuantDB())
        self.strategy = StrategyHelper(OllamaClient(), QuantDB())

    def start(self, hour:int=9, minute:int=0):
        """启动调度器"""
        # 每天早上9点执行一次
        #self.scheduler.add_job(daily_job, 'cron', hour=hour, minute=minute)
        #self.scheduler.add_job(daily_job, 'interval', seconds=5, kwargs={'name':'Bob'})

        self.scheduler.add_job(
            hour_job, 
            'interval', 
            seconds=7200,
            next_run_time=datetime.now(),
            kwargs={
                "name":"Hour job for critical stocks", 
                "spider": self.spider, 
                "strategy": self.strategy,
                "dragon": self.dragon,
                "worker": self.worker,
            }
        )

        """
        self.scheduler.add_job(
            us_spider_job, 
            "date",
            run_date=datetime.now(),
            #"cron",
            #hour=12,
            #minute=0,
            kwargs={
                "name":"Yfinance US spider price",
                "spider": self.spider, 
                "dragon": self.dragon
            }
        )
        """

        """
        self.scheduler.add_job(
            strategy_job, 
            "date",
            run_date=datetime.now(),
            kwargs={
                "name":"LLM Strategy",
                "strategy": self.strategy,
                "dragon": self.dragon
            }
        )
        """
        logger.info("Scheduler Agent: Scheduler started.")
        self.scheduler.start()
 
    def shutdown(self, wait:bool=True):
        logger.info("Scheduler Agent: Scheduler shutdown...")
        self.scheduler.shutdown(wait=wait)
