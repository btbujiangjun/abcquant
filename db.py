import io
import os
import json
import sqlite3
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Any, Optional
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy import (
    create_engine, 
    Table, 
    MetaData, 
    UniqueConstraint
)
from utils.time import str2date
from utils.logger import logger
from core.interval import DAY_INTERVAL 

class DB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        self.metadata = MetaData()
        # 初始化反射，用于获取表约束
        self.metadata.reflect(bind=self.engine)
        self._table_cache = {}

    def _get_table(self, table_name: str) -> Table:
        """获取并缓存 Table 对象，提高 Upsert 性能"""
        if table_name not in self._table_cache:
            table = self.metadata.tables.get(table_name)
            if table is None:
                # 动态刷新元数据以防新表创建
                self.metadata.reflect(bind=self.engine, only=[table_name])
                table = self.metadata.tables.get(table_name)
            self._table_cache[table_name] = table
        return self._table_cache[table_name]

    def create_connection(self):
        """创建并返回数据库连接"""
        return sqlite3.connect(self.db_path)

    def ddl(self, ddl: Any):
        """执行 DDL 语句（创建/修改表）"""
        with self.create_connection() as conn:
            try:
                cursor = conn.cursor()
                statements = ddl if isinstance(ddl, list) else [ddl]
                for d in statements:
                    cursor.execute(d)
                conn.commit()
                logger.info("DDL 语句执行成功")
            except Exception as e:
                logger.error(f"DDL 执行错误: {e}")
                raise

    def query(self, sql: str, params: Tuple = ()) -> pd.DataFrame:
        """参数化查询数据库并将结果保存到 DataFrame"""
        with self.create_connection() as conn:
            try:
                return pd.read_sql(sql, conn, params=params)
            except Exception as e:
                logger.error(f"Query Error: {sql} | {e}")
                return pd.DataFrame()

    def update_sql(self, sql: str, params: Tuple = ()) -> int:
        """执行 SQL 更新/删除"""
        with self.create_connection() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                affected_rows = cursor.rowcount
                conn.commit()
                return affected_rows
            except Exception as e:
                logger.error(f"SQL Update Error: {sql} | {e}")
                raise

    def update_sql_params(self, sql: str, values: Tuple[Any]) -> int:
        """单条带参数的 SQL 更新（支持 JSON 自动转换）"""
        safe_values = tuple(
            json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
            for v in values
        )
        return self.update_sql(sql, safe_values)

    def update_sql_params_many(self, sql: str, values_list: List[Tuple[Any]]) -> int:
        """批量带参数的 SQL 更新（支持 JSON 自动转换）"""
        with self.create_connection() as conn:
            try:
                cursor = conn.cursor()
                safe_values_list = [
                    tuple(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for v in values)
                    for values in values_list
                ]
                cursor.executemany(sql, safe_values_list)
                affected_rows = cursor.rowcount
                conn.commit()
                return affected_rows
            except Exception as e:
                logger.error(f"Batch SQL Error: {sql} | {e}")
                raise

    def update(self, df: pd.DataFrame, table_name: str):
        """通用 Upsert 逻辑：有唯一约束则更新，无则追加"""
        if df is None or df.empty:
            return

        table = self._get_table(table_name)
        conflict_cols = []
        for c in table.constraints:
            if isinstance(c, UniqueConstraint):
                conflict_cols = [col.name for col in c.columns]
                break

        if conflict_cols:
            # 引擎模式：使用 ON CONFLICT DO UPDATE
            with self.engine.begin() as conn:
                try:
                    rows = df.to_dict(orient="records")
                    stmt = insert(table)
                    update_cols = {c.name: stmt.excluded[c.name] for c in table.columns if c.name not in conflict_cols}
                    
                    if update_cols:
                        upsert_stmt = stmt.on_conflict_do_update(index_elements=conflict_cols, set_=update_cols)
                    else:
                        upsert_stmt = stmt.on_conflict_do_nothing(index_elements=conflict_cols)
                    
                    conn.execute(upsert_stmt, rows)
                    logger.info(f"Table {table_name} upsert {len(df)} rows.")
                except Exception as e:
                    logger.error(f"Upsert {table_name} error: {e}")
                    raise
        else:
            # 无约束模式：直接替换（保持原逻辑）
            with self.create_connection() as conn:
                try:
                    df.to_sql(table_name, conn, if_exists='replace', index=False, method='multi')
                    logger.info(f"Table {table_name} replaced with {len(df)} rows.")
                except Exception as e:
                    logger.error(f"Save {table_name} error: {e}")
                    raise

class QuantDB:
    def __init__(self, db_path="./data/quant_data.db"):
        self.db = DB(db_path)

    def init_db(self):
        table_ddl = [
            """
            CREATE TABLE IF NOT EXISTS stock_price (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                interval TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL,
                volume INTEGER, amount REAL,
                UNIQUE(symbol, date, interval)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY,
                symbol TEXT, title TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                source TEXT, publish_date TEXT
            )   
            """,
            """
            CREATE TABLE IF NOT EXISTS stock_base (
                id INTEGER PRIMARY KEY,
                symbol TEXT, name TEXT, exchange TEXT, status TEXT,
                UNIQUE(symbol, exchange)
            )   
            """,
            """
            CREATE TABLE IF NOT EXISTS stock_info (
                symbol TEXT, status TEXT, market_cap DOUBLE,
                current_price DOUBLE, fifty_two_week_high DOUBLE, fifty_two_week_low DOUBLE,
                all_time_high DOUBLE, all_time_low DOUBLE, short_ratio DOUBLE,
                country TEXT, industry TEXT, sector TEXT, quote_type TEXT,
                recommendation TEXT, info TEXT, update_time TEXT,
                UNIQUE(symbol)
            )           
            """,
            """
            CREATE TABLE IF NOT EXISTS analysis_report (
                symbol TEXT, date TEXT,
                three_filters_score double, three_filters_report TEXT,
                double_bottom_score double, double_bottom_report TEXT,
                double_top_score double, double_top_report TEXT,
                cup_handle_score double, cup_handle_report TEXT,
                update_time TEXT,
                UNIQUE(symbol, date)
            )   
            """,
            """
            CREATE TABLE IF NOT EXISTS strategy_pool (
                id INTEGER PRIMARY KEY,
                strategy_name TEXT, strategy_class TEXT, param_configs TEXT,
                UNIQUE(strategy_class, param_configs)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS strategy_signal (
                symbol TEXT, strategy_name TEXT, strategy_class TEXT,
                param_config TEXT, perf TEXT, equity_df TEXT,
                UNIQUE(symbol, strategy_class)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS strategy_report(
                symbol TEXT, report TEXT,
                UNIQUE(symbol)
            )
            """,
        ]
        try:
            self.db.ddl(table_ddl)
        except Exception as e:
            print(f"init_db error:{str(e)}")

    def refresh_stock_base(self, df, exchange: str = None):
        if isinstance(df, pd.DataFrame) and not df.empty:
            table_name = "stock_base"
            sql = f"DELETE FROM {table_name}"
            params = ()
            if exchange:
                sql += " WHERE exchange = ?"
                params = (exchange,)
            
            rows = self.db.update_sql(sql, params)
            if rows > 0:
                logger.info(f"Deleted {rows} old rows for {exchange or 'all'}.")
            self.db.update(df, table_name)
        else:
            logger.error("Refresh stock base error: invalid data.")

    def update_stock_status(self, symbol: str, status: str):
        sql = "UPDATE stock_base SET status = ? WHERE symbol = ?"
        self.db.update_sql(sql, (status, symbol))

    def query_stock_base(self, exchange: str = None, top_k: int = None):
        sql = "SELECT a.symbol, a.name, b.market_cap FROM stock_base a LEFT JOIN stock_info b ON a.symbol = b.symbol WHERE a.symbol IS NOT NULL AND a.status != '0'"
        params = []
        if exchange:
            sql += " AND a.exchange = ?"
            params.append(exchange)
        sql += " ORDER BY CAST(b.market_cap AS FLOAT) ASC"
        if top_k:
            sql += f" LIMIT {int(top_k)}"
        
        df = self.db.query(sql, tuple(params))
        if not df.empty and "market_cap" in df.columns:
            df["market_cap"] = df["market_cap"].apply(lambda x: f"{float(x):.0f}" if pd.notnull(x) else "0")
        return df

    def update_stock_info(self, keyvalues: Dict[str, Any]) -> int:
        keys = keyvalues.keys()
        sql = f"INSERT OR REPLACE INTO stock_info ({','.join(keys)}) VALUES ({','.join(['?']*len(keys))})"
        return self.db.update_sql_params(sql, tuple(keyvalues.values()))

    def update_stock_info_batch(self, records: List[dict]) -> int:
        if not records: return 0
        keys = list(records[0].keys())
        sql = f"INSERT OR REPLACE INTO stock_info ({','.join(keys)}) VALUES ({','.join(['?']*len(keys))})"
        values_list = [tuple(r[k] for k in keys) for r in records]
        return self.db.update_sql_params_many(sql, values_list)

    def query_stock_info(self, symbol: str):
        sql = "SELECT a.*, b.name FROM stock_info a LEFT JOIN stock_base b ON a.symbol = b.symbol WHERE a.symbol = ?"
        return self.db.query(sql, (symbol,))

    def update_stock_price(self, df):
        if isinstance(df, pd.DataFrame) and not df.empty:
            df = df.round(2)
            self.db.update(df, "stock_price")
        else:
            logger.error("Update stock price error: empty or invalid dataframe.")

    def query_stock_price(self, symbol: str, interval: str = 'daily', date: str = None, top_k: int = None, start_date: str = None, end_date: str = None):
        sql = """
            SELECT a.*, b.current_price, b.fifty_two_week_high, b.fifty_two_week_low, 
                   b.short_ratio, b.country, b.industry, b.sector, b.recommendation 
            FROM stock_price a LEFT JOIN stock_info b ON a.symbol = b.symbol WHERE 1=1
        """
        params = []
        if symbol:
            sql += " AND a.symbol = ?"; params.append(symbol)
        if interval:
            sql += " AND a.interval = ?"; params.append(interval)
        if date:
            sql += " AND SUBSTR(a.date, 1, 10) <= ?"; params.append(date)
        if start_date:
            sql += " AND SUBSTR(a.date, 1, 10) >= ?"; params.append(start_date)
        if end_date:
            sql += " AND SUBSTR(a.date, 1, 10) <= ?"; params.append(end_date)
        
        sql += " ORDER BY a.date DESC"
        if top_k:
            sql += f" LIMIT {int(top_k)}"

        df = self.db.query(sql, tuple(params))
        if df.empty: return df
        
        df = df.sort_values(by="date", ascending=True).reset_index(drop=True)
        if interval in DAY_INTERVAL:
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        if "id" in df.columns:
            df.drop(columns=['id'], inplace=True)
        return df.round(2)

    def latest_stock_price(self, symbol: str, interval: str) -> pd.DataFrame:
        sql = "SELECT date FROM stock_price WHERE symbol = ? AND interval = ? ORDER BY date DESC LIMIT 1"
        return self.db.query(sql, (symbol, interval))

    def query_analysis_report(self, symbol: str, date: str = None, top_k: int = 20, start_date: str = None, end_date: str = None, score_only: bool = True) -> pd.DataFrame:
        fields = "a.symbol, a.date, b.open, b.high, b.low, b.close, b.volume, three_filters_score, double_bottom_score, double_top_score, cup_handle_score, update_time" if score_only else "a.*, b.open, b.high, b.low, b.close, b.volume"
        sql = f"SELECT {fields} FROM analysis_report a LEFT JOIN stock_price b ON a.symbol = b.symbol WHERE a.symbol = ? AND a.date = SUBSTR(b.date, 1, 10) AND b.interval = 'daily'"
        params = [symbol]
        
        if date:
            sql += " AND a.date = ?"; params.append(date)
        if start_date:
            sql += " AND a.date >= ?"; params.append(start_date)
        if end_date:
            sql += " AND a.date <= ?"; params.append(end_date)
        
        sql += " ORDER BY a.date DESC"
        if (not start_date and not end_date) and top_k:
            sql += f" LIMIT {int(top_k)}"
            
        df = self.db.query(sql, tuple(params))
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%Y-%m-%d')
        return df

    def fetch_analysis_report(self, start_date: str, end_date: str) -> pd.DataFrame:
        sql = "SELECT symbol, date, three_filters_score as score FROM analysis_report WHERE date >= ? AND date <= ? ORDER BY date ASC, three_filters_score DESC"
        df = self.db.query(sql, (start_date, end_date))
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%Y-%m-%d') 
        return df

    def update_analysis_report(self, df: pd.DataFrame):
        if isinstance(df, pd.DataFrame) and not df.empty:
            self.db.update(df, "analysis_report")
        else:
            logger.error("Update analysis report error: invalid dataframe.")

    def fetch_strategy_pool(self) -> pd.DataFrame:
        return self.db.query("SELECT id, strategy_name, strategy_class, param_configs FROM strategy_pool ORDER BY id ASC")

    def add_strategy_pool(self, strategy_name: str, strategy_class: str, param_configs: str) -> int:
        sql = "INSERT INTO strategy_pool (strategy_name, strategy_class, param_configs) VALUES (?, ?, ?)"
        return self.db.update_sql(sql, (strategy_name, strategy_class, param_configs))

    def del_strategy_pool(self, id: int) -> int:
        return self.db.update_sql("DELETE FROM strategy_pool WHERE id = ?", (id,)) 

    def fetch_strategy_signal(self, symbol: str):
        sql = "SELECT symbol, strategy_name, strategy_class, param_config, perf, equity_df FROM strategy_signal WHERE symbol = ?"
        df = self.db.query(sql, (symbol,))
        results = []
        for _, row in df.iterrows():
            try:
                results.append({
                    "symbol": row["symbol"], 
                    "strategy_name": row["strategy_name"], 
                    "strategy_class": row["strategy_class"], 
                    "param_config": json.loads(row["param_config"]),
                    "perf": json.loads(row["perf"]),
                    "equity_df": pd.read_json(io.StringIO(row["equity_df"]), orient='split').replace([np.inf, -np.inf], np.nan).fillna(0).reset_index().to_dict(orient='records')
                })
            except Exception as e:
                logger.error(f"Error parsing strategy signal for {symbol}: {e}")
        return results

    def update_strategy_signal(self, keyvalues) -> int:
        """高性能批量 Upsert 优化"""
        if isinstance(keyvalues, dict):
            keyvalues = list(keyvalues.values()) 
        if not keyvalues: return 0

        fields = ['symbol', 'strategy_name', 'strategy_class', 'param_config', 'perf', 'equity_df']
        # 按年化收益排序
        keyvalues = sorted(keyvalues, key=lambda x: x.get('perf', {}).get('annual_return', 0), reverse=True)
        
        batch_data = []
        for kv in keyvalues:
            row = kv.copy()
            if isinstance(row.get("param_config"), dict):
                row["param_config"] = json.dumps(row["param_config"])
            if isinstance(row.get("perf"), dict):
                row["perf"] = json.dumps(row["perf"])
            if isinstance(row.get("equity_df"), pd.DataFrame):
                row["equity_df"] = row["equity_df"].sort_values(by='date', ascending=False).to_json(orient='split')
            
            batch_data.append(tuple(row.get(f) for f in fields))

        sql = f"INSERT OR REPLACE INTO strategy_signal ({','.join(fields)}) VALUES ({','.join(['?']*len(fields))})"
        return self.db.update_sql_params_many(sql, batch_data)

    def fetch_strategy_report(self, symbol: str):
        sql = "SELECT report FROM strategy_report WHERE symbol = ?"
        df = self.db.query(sql, (symbol,))
        return json.loads(df['report'].iloc[-1]) if not df.empty else {}

    def update_strategy_report(self, symbol: str, report: dict) -> int:
        report_str = json.dumps(report, ensure_ascii=False)
        sql = "INSERT OR REPLACE INTO strategy_report(symbol, report) VALUES (?, ?)"
        return self.db.update_sql_params(sql, (symbol, report_str))

if __name__ == '__main__':
    pd.set_option('display.max_columns', None)
    db = QuantDB()
    db.init_db()
    # 示例查询
    df = db.db.query("SELECT * FROM strategy_signal LIMIT 5")
    print(f"Loaded {len(df)} rows.")
