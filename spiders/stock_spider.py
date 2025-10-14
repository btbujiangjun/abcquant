# spiders/api_spider
import time
import requests
import threading
from io import StringIO
from typing import List, Dict, Callable
from abc import abstractmethod, ABC
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import akshare as ak
import yfinance as yf

from db import QuantDB
from config import CRITICAL_STOCKS_US
from utils.logger import logger
from core.interval import INTERVAL, MIN_INTERVAL, DAY_INTERVAL

# =====================
# 通用基类
# =====================
class BaseStockSpider(ABC):
    """抽象股票爬虫基类，封装通用逻辑"""
    
    def __init__(self, max_retries:int = 3, pause:float=0.5):
        self.max_retries = max_retries
        self.pause = pause
        self.db = QuantDB()
        self.today = datetime.today().strftime("%Y-%m-%d")

        # 统一的数据字段格式
        self.data_format = ["symbol", "interval", "date", "open", "high", "low", "close", "volume", "amount"]
        self.min_intervals = MIN_INTERVAL 
        self.day_intervals = DAY_INTERVAL
        self.intervals = INTERVAL 

    # ========= 基础工具 =========
    def ak_datestring_format(self, date_str:str) -> str:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d")

    def _retry(self, func: Callable, *args, **kwargs):
        """通用重试机制"""
        for attempt in range(1, self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                wait = self.pause * attempt
                logger.error(f"[Retry {attempt}/{self.max_retries}] {func.__name__} failed: {e}, wait {wait}s")
                time.sleep(wait)
        logger.error(f"[FAIL] {func.__name__} all retries failed.")
        return None

    # ========= DB操作 =========
    def _local_stock_base(self, exchange: str=None) -> List[str]:
        df = self.db.query_stock_base(exchange)
        return [] if df is None else df['symbol'].dropna().tolist()

    def refresh_stock_base(self, df: pd.DataFrame) -> bool:
        if not isinstance(df, pd.DataFrame) or df.empty:
            logger.error("Refresh stock base error: DataFrame invalid.")
            return False
        try:
            self.db.refresh_stock_base(df)
            return True
        except Exception as e:
            logger.error(f"Update stock base error: {e}")
            return False
   
    def query_stock_price(self, 
            symbol: str, 
            interval: str=None,
            date: str=None, 
            top_k:int=None
        ) -> pd.DataFrame:
        return self.db.query_stock_price(symbol, interval, date, top_k) 

    def update_stock_price(self, df: pd.DataFrame) -> bool:
        if not isinstance(df, pd.DataFrame) or df.empty:
            logger.warning("Update stock price skipped: no data.")
            return False
        try:
            self.db.update_stock_price(df)
            return True
        except Exception as e:
            logger.error(f"Update stock price error: {e}")
            return False

    def latest_stock_data(self, symbol:str):
        """获取某个股票所有 interval 的最新数据"""
        for interval in self.intervals:
            df = self.db.latest_stock_price(symbol, interval)
            latest_date = "1970-01-01" if df.empty else df.at[0, "date"].split()[0]
            df = self.fetch_stock_data(symbol, interval, latest_date, self.today)
            self.update_stock_price(df)

    def update_latest(self, symbols:list[str]=None, workers:int=1):
        """更新全部股票价格数据（支持并发）"""
        symbols = symbols or self.query_stock_base()
        logger.info(f"[{self.__class__.__name__}] {len(symbols)} stocks in queue...")
      
        def task(sym: str):
            """单个任务执行逻辑"""
            try:
                # ① 拉取基本信息
                self.fetch_stock_info([sym])
                # ② 更新最新价格数据
                self.latest_stock_data(sym)
                return (sym, True, None)
            except Exception as e:
                return (sym, False, str(e))
 
        done_count, total = 0, len(symbols) 
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(task, sym): sym for sym in symbols}
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    future.result()
                    done_count += 1
                    logger.info(f"[{done_count}/{total}] ✅ DONE: {sym}")
                except Exception as e:
                    done_count += 1
                    logger.error(f"[{done_count}/{total}] ❌ FAIL: {sym} ({e})")

    # ========= 抽象接口 ========= 
    @abstractmethod
    def query_stock_base(self) -> List[str]: ...

    @abstractmethod
    def update_stock_info(self, symbols:list[str]=None, batch_size: int = 50): ...
    
    @abstractmethod
    def fetch_stock_info(self, symbols:list[str], batch_size: int=50): ...
    
    @abstractmethod
    def fetch_stock_data(self, 
            symbol: str,
            interval: str, 
            start: str, 
            end: str) -> pd.DataFrame: ...


# =====================
# 美股爬虫（Yahoo Finance）
# =====================
class YF_US_Spider(BaseStockSpider):
    def __init__(self, max_retries:int = 3, pause:float=0.5):
        super().__init__(max_retries, pause)
        self._lock = threading.Lock()
        self.yf_interval_map = {
            "1min": {"code":"1m","valid": 8}, 
            "2min": {"code":"2m","valid": 59}, 
            "5min": {"code":"5m","valid": 59}, 
            "15min": {"code":"15m","valid": 59},
            "30min": {"code":"30m","valid": 59},
            "60min": {"code":"60m","valid": 729},
            "daily": {"code":"1d","valid": 729}, 
            "weekly": {"code":"1wk","valid": 729},
            "monthly": {"code":"1mo","valid": 729},
        }
        self.EXCHANGE_MAP = {
            'A': 'amex',
            'N': 'nyse',
            'P': 'nyse',
            'Z': 'bats',
            'Q': 'nasdaq'
        }
        self.TICKER_ALIAS = {
            "IXIC": "^IXIC",   # 纳指
            "DJI": "^DJI",     # 道指
            "SPX": "^GSPC",    # 标普500
        }
        self.extend_symbols = CRITICAL_STOCKS_US

    def _ticker_alias(self, ticker:str) -> str:
        return self.TICKER_ALIAS[ticker] if ticker in self.TICKER_ALIAS else ticker
   
    def _fetch_list(self, url, exchange_hint=None):
        """下载并解析 NASDAQ FTP 列表"""
        def _download_and_parse():
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            lines = resp.text.strip().split('\n')
            # 最后一行是 "File Creation Time: ..."，需要去掉
            data = "\n".join(lines[:-1])
            df = pd.read_csv(StringIO(data), sep='|')
            if exchange_hint:
                df['exchange'] = exchange_hint
            return df

        df = self._retry(_download_and_parse)
        if df is None:
            logger.error(f"[FAIL] fetch list from {url}")
            return pd.DataFrame()
        return df 

    def refresh_stock_base(self) -> bool:
        # 获取纳斯达克全部股票代码
        files = {
            "nasdaq": "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt",
            "others": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
        }
        
        nasdaq = self._fetch_list(files['nasdaq'], "nasdaq")
        nasdaq = nasdaq[['Symbol', 'Security Name', 'exchange']]
        nasdaq = nasdaq.rename(columns={
            'Symbol': 'symbol',
            'Security Name': 'name',
        })

        others = self._fetch_list(files['others'], "others")
        #others['exchange'] = others['Exchange'].map(lambda x: self.EXCHANGE_MAP.get(x, 'unknown'))
        others = others[['ACT Symbol', 'Security Name', 'exchange']]
        others = others.rename(columns={
            'ACT Symbol': 'symbol',
            'Security Name': 'name',
        })

        df = pd.concat([nasdaq, others], ignore_index=True)
        df = df.drop_duplicates(subset='symbol', keep='first').reset_index(drop=True)
        df['exchange'], df["status"] = "us", 1
        super().refresh_stock_base(df)
        exchanges = [str(exchange) for exchange in df['exchange'].unique()]
        logger.info(f"Refresh stock base:{','.join(exchanges)}, total symbols:{len(df)}")
        
        return True

    def query_stock_base(self) -> List[str]:
        symbols = self.extend_symbols.copy()
        symbols.extend(self._local_stock_base(exchange="us"))        
        return symbols

    def update_stock_info(self, symbols:list[str]=None, batch_size: int=50):
        symbols = symbols or self.query_stock_base()
        self.fetch_stock_info(symbols, batch_size=batch_size)

    def fetch_stock_info(self, symbols:list[str], batch_size:int=50):
        field_map = {
            "status": "marketState",
            "market_cap": "marketCap",
            "current_price": "currentPrice",
            "fifty_two_week_high": "fiftyTwoWeekHigh",
            "fifty_two_week_low": "fiftyTwoWeekLow",
            "all_time_high": "allTimeHigh",
            "all_time_low": "allTimeLow",
            "short_ratio": "shortRatio",
            "country": "country",
            "industry": "industry",
            "sector": "sector",
            "quote_type": "quoteType",
            "recommendation": "recommendationKey",
        }

        def _do_download(symbols=symbols):
            with self._lock:
                return yf.Tickers(symbols)

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            try:
                tickers = self._retry(
                    _do_download, 
                    symbols=" ".join([self._ticker_alias(b) for b in batch])
                )
                for idx in range(len(batch)):
                    s = batch[idx]
                    try:
                        info = tickers.tickers[self._ticker_alias(s)].info
                    except Exception as e:
                        logger.error(f"Update {s} info error: {e}")
                        break

                    keyvalues = {"symbol": s, "info": info, "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                    for key, data_type in field_map.items():
                        keyvalues[key] = info.get(data_type, 0) 
                    self.db.update_stock_info(keyvalues)
                    logger.info(f"✅Update {s} info: {i+idx+1}/{len(symbols)}")
            except Exception as e:
                logger.error(f"Update info error: {e}")

    def _period_adjust(self, interval, start, end):
        if interval in self.day_intervals:
            return start, end

        today_date = datetime.today() 
        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")
        lastest = today_date - timedelta(days=self.yf_interval_map[interval]["valid"]) 
        start_date, end_date = max(start_date, lastest), max(end_date, lastest)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    def _safe_download(self, 
        symbol, 
        start=None, 
        end=None, 
        interval="1d"):
        
        def _do_download():
            with self._lock:
                return yf.download(
                    self._ticker_alias(symbol),
                    start=start,
                    end=end,
                    interval=self.yf_interval_map[interval]["code"],
                    progress=False,
                    auto_adjust=False,
                    threads=False  # ✅ 避免多线程下载时难以捕获异常
                )
        
        df = self._retry(_do_download)
        if df is None:
            logger.warning(f"{symbol}: No data returned(无效代码或无数据区间)")
            self.db.update_stock_status(symbol, 2)
            return pd.DataFrame() 
        else:
            logger.info(f"{symbol}: {len(df)} rows downloaded")
            self.db.update_stock_status(symbol, 1)
            return df

    def fetch_stock_data(self,
            symbol: str, 
            interval: str, 
            start: str, 
            end: str) -> pd.DataFrame:
        start, end = self._period_adjust(interval, start, end)
        df = self._safe_download(symbol, start, end, interval)
        if not df.empty:
            df["symbol"] = symbol
            df["interval"] = interval
            df["amount"] = df["Close"] * df["Volume"]
            df = df.reset_index()

            if interval in self.min_intervals: 
                df["date"] = df["Datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                df["date"] = df["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
                
            df = df[["symbol", "interval", "date", "Open", "High", "Low", "Close", "Volume", "amount"]]
            df.columns = self.data_format
            latest_date = df["date"].iat[-1] 
            logger.info(f"Get price: {symbol}/{interval}/[{latest_date}] {len(df)} rows")
        else:
            logger.error(f"Not found data: {symbol} / {interval}, from {start} to {end}")
        return df

class AK_A_Spider(BaseStockSpider):

    def __init__(self, max_retries:int = 3, pause:float=0.5):
        super().__init__(max_retries, pause)
    
    def query_stock_base(self) -> List[str]:
        return self._local_stock_base(exchange="cn") 

    def update_stock_info(self, symbols:list[str]=None, batch_size: int = 50):
        raise NotImplementedError 

    def refresh_stock_base(self) -> bool:
        df = ak.stock_info_a_code_name()

        if not isinstance(df, pd.DataFrame) or df.empty:
            logger.error(f"Refresh AKShare A stock base error.")
            return False

        df = df.rename(columns={"code": "symbol"})
        exchange = "cn"
        df["exchange"], df["status"] = exchange, 1
 
        super().refresh_stock_base(df) 
        logger.info(f"Refresh {exchange} stock base, total symbols:{len(df)}")

        return True

    def fetch_stock_data(self, 
            symbol: str, 
            interval: str, 
            start_date: str, 
            end_date: str) -> pd.DataFrame:

        def _do_download(): 
            if interval in self.day_intervals: # 日/周/月级别数据
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period=interval,
                    start_date=self.ak_datestring_format(start_date),
                    end_date=self.ak_datestring_format(end_date),
                    adjust="qfq"  # 前复权，可选 'hfq' 或 ''
                )
                return df.rename(columns={"日期": "时间"})
            else: # 分钟级别数据
                return ak.stock_zh_a_hist_min_em(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=interval,
                    adjust="qfq"  # 同样支持 "qfq", "hfq"
                )
        
        if not interval in self.intervals:
           raise ValueError(f"Unsupported {interval}, valid interval: {self.intervals}")
        
        df = self._retry(_do_download)
        if df is None:
            logger.warning(f"{symbol}: No data returned(无效代码或无数据区间)")
            self.db.update_stock_status(symbol, 2)
            return pd.DataFrame() 
        
        logger.info(f"{symbol}: {len(df)} rows downloaded")
        self.db.update_stock_status(symbol, 1)
        df["symbol"], df["interval"] = symbol, interval
        df = df.rename(columns={
            "时间": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount"
        })
        return df[self.data_format]

class AK_HK_Spider(BaseStockSpider):

    def __init__(self, max_retries:int = 3, pause:float=0.5):
        super().__init__(max_retries, pause)
    
    def query_stock_base(self) -> List[str]:
        return self._local_stock_base(exchange="hk") 

    def update_stock_info(self, symbols:list[str]=None, batch_size: int = 50):
        raise NotImplementedError 
    
    def refresh_stock_base(self) -> bool:
        df = ak.stock_hk_spot()
        
        if not isinstance(df, pd.DataFrame):
            logger.error(f"Refresh AKShare HK stock base error.")            
            return False

        exchange = "hk"
        df = df[['代码','中文名称']]
        df.columns = ['symbol','name']
        df["exchange"], df["status"] = exchange, 1
        super().refresh_stock_base(df) 
        logger.info(f"Refresh {exchange} stock base, total symbols:{len(df)}")

        return True

    def fetch_stock_data(self,
            symbol: str, 
            interval: str, 
            start_date: str, 
            end_date: str) -> pd.DataFrame:
        
        def _do_download():
            if interval in self.day_intervals:
                df = ak.stock_hk_hist(
                    symbol=symbol,
                    period=interval,
                    start_date=start_date,
                    end_date=end_date,
                    adjust=""
                )
                return df.rename(columns={"日期": "时间"})
            else:
                return ak.stock_hk_hist_min_em(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=interval,
                    adjust=""
                )


        if not interval in self.intervals:
           raise ValueError(f"Unsupported {interval}, valid interval: {self.intervals}")
        
        df = self._retry(_do_download)    
        if df is None:
            logger.warning(f"{symbol}: No data returned(无效代码或无数据区间)")
            self.db.update_stock_status(symbol, 2)
            return pd.DataFrame() 
        
        logger.info(f"{symbol}: {len(df)} rows downloaded")
        self.db.update_stock_status(symbol, 1)
        df = df.rename(columns={
            "时间": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount"
        })
  
        df["symbol"], df["interval"] = symbol, interval
        return df[self.data_format]


if __name__ == "__main__":
    #a_spider = AK_A_Spider()
    #hk_spider = AK_HK_Spider()
    #df = a_spider.fetch_stock_data("000001", "5min", "20250901", "20250902")
    #df = hk_spider.fetch_stock_data("00700", "5min", "20250901", "20250902")
    
    #a_spider.refresh_stock_base() 
    #hk_spider.refresh_stock_base() 
    
    #a_spider.update_latest()
    #hk_spider.update_latest()

    
    
    us = YF_US_Spider()
    #us.refresh_stock_base()
    #us.update_stock_info()
    us.update_latest()
    """
    us.refresh_stock_base()
    df = us.query_stock_base(exchange="nasdaq")
    
    ticker = "XPEV"

    df = us.query_stock_price(ticker, "1min", 360)    
    print(df)
    df = us.latest_stock_data(ticker)
    print(df)
    df = us.query_stock_price(ticker, "1min")    
    print(df)
    
    """



