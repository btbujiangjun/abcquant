# spiders/stock_spider
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
from utils.time import *
from utils.logger import logger
from config import CRITICAL_STOCKS_US
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
        self.today = today_str()

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
            #except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            except Exception as e:
                wait = self.pause * attempt
                logger.error(f"[Retry {attempt}/{self.max_retries}] {func.__name__} failed: {e}, wait {wait}s")
                time.sleep(wait)
        logger.error(f"[FAIL] {func.__name__} all retries failed.")
        return None

    # ========= DB操作 =========
    def _local_stock_base(self, exchange: str=None) -> List[str]:
        df = self.db.query_stock_base(exchange)
        return [] if df is None else df['symbol'].dropna().tolist()

    def refresh_stock_base(self, df: pd.DataFrame, exchange:str=None) -> bool:
        if not isinstance(df, pd.DataFrame) or df.empty:
            logger.error("Refresh stock base error: DataFrame invalid.")
            return False
        try:
            self.db.refresh_stock_base(df, exchange)
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
        #try:
        self.db.update_stock_price(df)
        #    return True
        #except Exception as e:
        #    logger.error(f"🚫Update stock price error: {e}")
        #    return False

    def latest_stock_data(self, symbol:str):
        """获取某个股票所有 interval 的最新数据"""
        dfs = []
        for interval in self.intervals:
            df = self.db.latest_stock_price(symbol, interval)
            if df.empty: 
                latest_date = "1970-01-01" 
            else:
                if interval in MIN_INTERVAL:
                    latest_date = df.at[0, "date"].split()[0]
                else:
                    latest_date = days_delta(df.at[0, "date"].split()[0], 1)
            if latest_date >= self.today:
                logger.info(f"{interval} price data is latest.")
                continue
            df = self.fetch_stock_data(symbol, interval, latest_date, self.today)
            if len(df) > 0:
                dfs.append(df)
        self.update_stock_price(pd.concat(dfs, ignore_index=True))

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
                    logger.info(f"✅ [{done_count}/{total}] DONE: {sym}")
                except Exception as e:
                    done_count += 1
                    logger.error(f"❌ [{done_count}/{total}] FAIL: {sym} ({e})")

    def update_latest_batch(self, symbols:list[str]=None, period:int=3, batch_size:int=1000):
        end = today_str()
        start = days_delta(end, -period)
        symbols = symbols or self.query_stock_base()
        logger.info(f"[{self.__class__.__name__}] {len(symbols)} stocks in queue...")
        self.update_stock_data_batch(symbols, self.intervals, start, end, batch_size)  

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

    
    @abstractmethod
    def update_stock_data_batch(self, 
            symbols: list[str],
            intervals: list[str], 
            start:str=days_delta(today_str(), -3),
            end:str=today_str(),
            batch_size:int=50): ...

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
        self.stock_info_field_map = {
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
        self.TICKER_ALIAS = {
            "IXIC": "^IXIC",   # 纳指
            "DJI": "^DJI",     # 道指
            "SPX": "^GSPC",    # 标普500
            "VIX": "^VIX",    # 标普500波动率
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
        others = others[['ACT Symbol', 'Security Name', 'exchange']]
        others = others.rename(columns={
            'ACT Symbol': 'symbol',
            'Security Name': 'name',
        })

        df = pd.concat([nasdaq, others], ignore_index=True)
        df = df.drop_duplicates(subset='symbol', keep='first').reset_index(drop=True)
        exchange = "us"
        df['exchange'], df["status"] = exchange, 1
        df['symbol'] = df['symbol'].astype(str)
        df = df[~df['symbol'].str.contains(r'[.$]', regex=True, na=False)]
        super().refresh_stock_base(df, exchange)
        logger.info(f"Refresh stock base: US market, total symbols:{len(df)}")
        return df

    def query_stock_base(self) -> List[str]:
        symbols = self.extend_symbols.copy()
        symbols.extend(self._local_stock_base(exchange="us"))        
        return symbols

    def update_stock_info(self, symbols:list[str]=None, batch_size: int=500):
        symbols = symbols or self.query_stock_base()
        self.fetch_stock_info(symbols, batch_size=batch_size)

    def fetch_stock_info(self, symbols:list[str], batch_size:int=500):

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
                kv_list = []
                update_time = today_str(get_format("YYMMDDHHMMSS"))
                for idx in range(len(batch)):
                    s = batch[idx]
                    try:
                        info = tickers.tickers[self._ticker_alias(s)].info
                    except Exception as e:
                        logger.error(f"🚫Update {s} info error: {e}")
                        continue

                    keyvalues = {"symbol": s, "info": info, "update_time": update_time}
                    for key, data_type in self.stock_info_field_map.items():
                        keyvalues[key] = info.get(data_type, 0)
                    kv_list.append(keyvalues) 
                row_count = self.db.update_stock_info_batch(kv_list)
                logger.info(f"✅Update stock info: {i+batch_size}/{len(symbols)}")
            except Exception as e:
                logger.error(f"🚫Update info error: {e}")

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

        return self._retry(_do_download)

    def fetch_stock_data(self,
            symbol: str, 
            interval: str, 
            start: str, 
            end: str) -> pd.DataFrame:
        start, end = self._period_adjust(interval, start, end)
        df = self._safe_download(symbol, start, end, interval)
        if not df.empty:
            if symbol == "BTC-USD":
                df.columns = df.columns.droplevel(1)
            df["symbol"] = symbol
            df["interval"] = interval
            df["amount"] = df["Close"] * df["Volume"]
            df = df.reset_index()

            if interval in self.day_intervals:
                df["date"] = df["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                df["date"] = df["Datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
                
            df = df[["symbol", "interval", "date", "Open", "High", "Low", "Close", "Volume", "amount"]]
            df.columns = self.data_format
            latest_date = df["date"].iat[-1] 
            logger.info(f"Get price: {symbol}/{interval}/[{latest_date}] {len(df)} rows")
        else:
            logger.error(f"Not found data: {symbol} / {interval}, from {start} to {end}")
            return pd.DataFrame()
        return df

    def update_stock_data_batch(self,
            symbols: list[str],
            intervals: list[str],
            start:str=days_delta(today_str(), -3),
            end:str=today_str(),
            batch_size:int=1000):
        date_format = get_format("YYMMDDHHMMSS") 

        def _do_download(symbols=symbols):
            with self._lock:
                return yf.Tickers(symbols)

        def _get_tickers_info(batch):
            try:
                return self._retry(_do_download, symbols=" ".join([self._ticker_alias(b) for b in batch]))
            except Exception as e:
                logger.error(f"🚫Error fetching tickers info: {e}")
                raise

        def _get_info_kv_list(batch, tickers):
            kv_list = []
            for s in batch:
                info = tickers.tickers.get(self._ticker_alias(s), {}).info
                if not info:
                    logger.error(f"🚫Error: No info found for {s}")
                    continue
                kv_entry = {
                    "symbol": s,
                    "info": info,
                    "update_time": datetime.now().strftime(date_format),
                    **{key: info.get(data_type, 0) for key, data_type in self.stock_info_field_map.items()}
                }
                kv_list.append(kv_entry)
            return kv_list

        def _get_stock_data(tickers, batch):
            dfs = []
            for interval in intervals:
                for symbol in batch:
                    df = _get_interval_data(tickers, symbol, interval)
                    if df.empty:
                        continue
                    if symbol == "BTC-USD" and df.columns.nlevels > 1:
                        df.columns = df.columns.droplevel(1)
                    df["symbol"], df["interval"], df["amount"] = symbol, interval, df["Close"] * df["Volume"]
                    df = _process_data(df, interval)
                    logger.info(f"Get price: {symbol}/{interval}/[{df['date'].iat[-1]}] {len(df)} rows")
                    dfs.append(df)
            return pd.concat(dfs, ignore_index=True) if len(dfs) > 0 else pd.DataFrame()

        def _get_interval_data(tickers, symbol, interval):
            try:
                return tickers.tickers[self._ticker_alias(symbol)].history(
                    start=start,
                    end=end,
                    interval=self.yf_interval_map[interval]["code"]
                )
            except Exception as e:
                logger.error(f"🚫Error fetching data for {symbol} at interval {interval}: {e}")
                return pd.DataFrame()
    
        def _process_data(df, interval):
            df = df.reset_index()
            date_field = "Datetime" if interval in self.min_intervals else "Date"
            df["date"] = df[date_field].dt.strftime(date_format)
            df = df[["symbol", "interval", "date", "Open", "High", "Low", "Close", "Volume", "amount"]]
            df.columns = self.data_format
            return df

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            try:
                tickers = _get_tickers_info(batch)
                kv_list = _get_info_kv_list(batch, tickers)
                df = _get_stock_data(tickers, batch)
                if kv_list:
                    self.db.update_stock_info_batch(kv_list)
                    logger.info(f"✅Update stock info: {min(i + batch_size, len(symbols))}/{len(symbols)}")
                if not df.empty:
                    self.update_stock_price(df)
                    logger.info(f"✅Update price: {df['date'].iat[-1]} {len(df)} rows") 
            except Exception as e:
                err_msg = str(e)
                if "Too Many Requests" in err_msg or "429" in err_msg:
                    logger.warning(f"⚠️ Hit rate limit! Sleeping 10s...")
                    time.sleep(10)
                elif "Connection" in err_msg or "timed out" in err_msg:
                    logger.warning(f"⚠️ Connection error! Sleeping 5s ...")
                    time.sleep(5)
                else:
                    logger.error(f"🚫Unexpected error: {e}")

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
 
        super().refresh_stock_base(df, exchange) 
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
        super().refresh_stock_base(df, exchange) 
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

    def fetch_stock_info(self, symbols:list[str], batch_size:int=50):
        return ak.stock_hk_company_profile_em(symbols[0])

if __name__ == "__main__":
    #a_spider = AK_A_Spider()
    #hk_spider = AK_HK_Spider()
    #df = a_spider.fetch_stock_data("000001", "5min", "20250901", "20250902")
    #symbol = "BTC-USD"
    #df = hk_spider.fetch_stock_data(symbol, "daily", "20250901", "20250902")
    #print(df.head())
    #print([attr for attr in dir(ak) if 'hk' in attr])
    #info = hk_spider.fetch_stock_info([symbol])
    #print(info) 
    #a_spider.refresh_stock_base() 
    #hk_spider.refresh_stock_base() 
    
    #a_spider.update_latest()
    #hk_spider.update_latest()

    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_colwidth', None)
    pd.set_option('display.max_rows', None)    
    
    us = YF_US_Spider()
    #df = us.refresh_stock_base()
    #df.to_csv("data.csv", index=False, encoding="utf-8")
    #print(df)

    #us.update_stock_info()
    #us.update_latest()
    """
    us.refresh_stock_base()
    df = us.query_stock_base(exchange="nasdaq")
    """
    
    ticker = "BTC-USD"
    ticker = "MSTZ"

    #df = us.query_stock_price(ticker, "1min", 360)    
    #print(df)
    df = us.latest_stock_data(ticker)
    print(df)
    df = us.query_stock_price(ticker, "daily")    
    print(df)



