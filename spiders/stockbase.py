import pandas as pd
import akshare as ak
import json
import re
import io
import requests
import time
from pypinyin import pinyin, Style
from typing import List, Dict
from db import QuantDB
from utils.logger import logger


class StockBaseManager:
    """
    全球股票代码管理器
    支持：A股 (CN), 港股 (HK), 美股 (US) 全量代码抓取与 yfinance 格式化
    """
    def __init__(self):
        self.us_nasdaq_url = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
        self.us_other_url = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
        self.db = QuantDB()

    def list2df(self, data:List[Dict])->pd.DataFrame:
        columns = ["symbol", "name", "pinyin", "mkt_cap", "exchange", "status"]
        return pd.DataFrame(columns=columns) if not data else pd.DataFrame(data)[columns]

    def get_pure_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗非正股"""
        if df.empty: return df
        # 1. 基础去重
        df = df.drop_duplicates(subset=['symbol'])
        # 2. 港股逻辑
        mask_hk = df['exchange'] == 'HK'
        hk_exclude = (
            df['name'].str.contains(r'-R|人民币|购|沽|牛|熊', na=False) |
            df['name'].str.contains(r'[A-Z]+\s[A-Z0-9]+', regex=True, na=False)
        )
        # 3. 美股逻辑 (剔除权证/单元/优先股)
        mask_us = df['exchange'] == 'US'
        us_exclude = (
            (df['symbol'].str.len() > 4) & df['symbol'].str.get(-1).isin(['L', 'M','U', 'R', 'W', 'N', 'O' , 'P' , 'Q']) |
            df['name'].str.contains(r'Unit|Warrant|Right|Preferred', case=False, na=False)
        )
        # 执行过滤
        df = df[~((mask_hk & hk_exclude) | (mask_us & us_exclude))]
        return df.reset_index(drop=True)

    @staticmethod
    def get_pinyin_initials(name: str) -> str:
        """提取中文拼音首字母"""
        if not name: return ""
        # 仅保留中文字符
        clean_name = re.sub(r'[^\u4e00-\u9fa5]', '', str(name))
        if not clean_name: return ""
        initials = pinyin(clean_name, style=Style.FIRST_LETTER)
        return "".join([i[0] for i in initials]).lower()

    def fetch_cn_stocks(self)->pd.DataFrame:
        """抓取 A 股数据 (沪深京)"""
        logger.info("🚀 正在抓取 A 股全量数据...")
        data = [] 
        try:
            df = ak.stock_zh_a_spot_em()
            for _, row in df.iterrows():
                code, name = str(row['代码']), str(row['名称'])
                # 根据代码前缀分配 yfinance 后缀
                if code.startswith(('60', '68', '90')): suffix = "SS"
                elif code.startswith(('00', '30', '20')): suffix = "SZ"
                elif code.startswith(('43', '83', '87', '88')): suffix = "BJ"
                else: continue
                data.append({
                    "symbol": f"{code}.{suffix}",
                    "name": name,
                    "pinyin": self.get_pinyin_initials(name),
                    "mkt_cap": row.get('总市值', 0),
                    "exchange": "CN",
                    "status": "1",
                })
        except Exception as e:
            logger.error(f"❌ A 股抓取失败: {e}")
        return self.list2df(data)

    def _patch_hk_mkt_cap(self, df: pd.DataFrame, batch_size: int = 500) -> pd.DataFrame:
        """
        利用 yfinance 批量补全港股市值
        :param df: 传入的港股 DataFrame
        :param batch_size: 每批次请求的代码数量
        """
        import yfinance as yf
        logger.info(f"🧬 开始补全港股市值，总计需处理 {len(df)} 条数据...")
        symbols = df['symbol'].tolist()
        for i in range(0, len(symbols), batch_size):
            batch_symbols = symbols[i : i + batch_size]
            batch_str = " ".join(batch_symbols)
            try:
                tickers = yf.Tickers(batch_str)
                for sym in batch_symbols:
                    try:
                        # 获取 marketCap (yfinance 字段名为 marketCap)
                        info = tickers.tickers[sym].info
                        mkt_cap = info.get('marketCap') or info.get('previousClose', 0) * info.get('sharesOutstanding', 0)
                        if mkt_cap:
                            df.loc[df['symbol'] == sym, 'mkt_cap'] = float(mkt_cap)
                    except Exception:
                        # 单只股票失败跳过，不影响整批
                        continue
                logger.info(f"✅ 已完成批次: {i + len(batch_symbols)}/{len(symbols)}")
            except Exception as e:
                logger.error(f"❌ 批次 {i} 请求失败: {e}")
                continue
        return df

    def fetch_hk_stocks(self)->pd.DataFrame:
        """抓取港股数据"""
        logger.info("🚀 正在抓取港股数据...")
        data = []
        try:
            df = ak.stock_hk_spot_em()
            df['symbol'], df['name'], df['exchange'] = df['代码'], df['名称'], 'HK'
            df = self.get_pure_stocks(df)
            for _, row in df.iterrows():
                code, name = row['symbol'][-4:], row['name']
                data.append({
                    "symbol": f"{code}.HK",
                    "name": name,
                    "pinyin": self.get_pinyin_initials(name) or code,
                    "mkt_cap": row.get('总市值', 0),
                    "exchange": row.get('exchange', 'HK'),
                    "status": "1",
                })
        except Exception as e:
            logger.error(f"❌ 港股抓取失败: {e}")

        return self._patch_hk_mkt_cap(self.list2df(data))

    def _process_us_url(self, url: str, is_nasdaq: bool)->pd.DataFrame:
        """处理 Nasdaq FTP 的文本文件"""
        data = []
        try:
            response = requests.get(url, timeout=15)
            response = io.StringIO(response.text)
            df = pd.read_csv(response, sep="|")
            df = df.iloc[:-1]  # 移除文件末尾的生成时间行
            
            symbol_col = "ACT Symbol" if "ACT Symbol" in df.columns else "Symbol"
            name_col = "Security Name"
            
            for _, row in df.iterrows():
                symbol = str(row[symbol_col])
                name = str(row[name_col]).split(' - ')[0] # 截断描述
                yf_symbol = symbol.replace('.', '-')
                
                data.append({
                    "symbol": yf_symbol,
                    "name": name,
                    "pinyin": yf_symbol.lower(), # 美股用代码作为搜索索引
                    "mkt_cap": 0,
                    "exchange": "US",
                    "status": "1",
                })
        except Exception as e:
            logger.error(f"⚠️ 美股数据源 {url} 读取失败: {e}")
        return self.list2df(data)        

    def fetch_us_stocks(self)->pd.DataFrame:
        """抓取美股全量数据"""
        logger.info("🚀 正在从 Nasdaq FTP 抓取美股数据...")
        df_nasdaq = self._process_us_url(self.us_nasdaq_url, True)
        df_other = self._process_us_url(self.us_other_url, False)
        return self.get_pure_stocks(pd.concat([df_nasdaq, df_other], ignore_index=True)) 

    def save(self, df:pd.DataFrame):
        self.db.refresh_stock_base(df)
        print(f"✅ Refresh stock base，总计 {len(df)} 条")

    def run(self):
        """运行完整抓取流程"""
        start_time = time.time()
        df = pd.concat([self.fetch_us_stocks(), self.fetch_cn_stocks(), self.fetch_hk_stocks()], ignore_index=True)
        self.save(df)
        logger.info(f"⏱️ 总耗时: {time.time() - start_time:.2f} 秒")

class StockBaseSearcher:
    def __init__(self, exchange=None):
        self.df = QuantDB().query_stock_base(exchange=exchange)
        self.df['symbol_lower'] = self.df['symbol'].str.lower()
        self.df['pinyin_lower'] = self.df['pinyin'].str.lower()
        self.df['name_lower'] = self.df['name'].str.lower()
        
    def search(self, query: str, limit: int = 25):
        if self.df.empty or not query:
            return []
        q = query.lower().strip()

        # 1. 构造多条件布尔掩码 (Mask)
        # 优先级：代码开头匹配 | 拼音包含 | 名称包含
        mask = (
            self.df['symbol_lower'].str.startswith(q) | 
            self.df['pinyin_lower'].str.contains(q, na=False) | 
            self.df['name_lower'].str.contains(q, na=False)
        )

        # 2. 执行过滤并取前 N 条
        matched_df = self.df[mask].copy()
        matched_df['exact_match'] = (matched_df['symbol_lower'] == q).astype(int)
        matched_df['mkt_cap'] = pd.to_numeric(matched_df['mkt_cap'], errors='coerce').fillna(0)
        matched_df = matched_df.sort_values(
            by=['exact_match', 'mkt_cap'], 
            ascending=[False, False]
        )

        return matched_df.head(limit)[['symbol', 'name', 'exchange', 'mkt_cap']].to_dict(orient='records')

# 使用示例
if __name__ == "__main__":
    manager = StockBaseManager()
    manager.run()
