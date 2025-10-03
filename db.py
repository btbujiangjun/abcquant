# db.py
import os
from typing import Dict, Tuple, Any
import sqlite3
import pandas as pd
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy import create_engine, Table, MetaData,UniqueConstraint
from utils.logger import logger

class DB:
    def __init__(self, db_path):
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)
 
    def create_connection(self):
        """创建并返回数据库连接"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        return sqlite3.connect(self.db_path)

    def ddl(self, ddl):
        """创建数据库表"""
        conn = self.create_connection()
        cursor = conn.cursor()
        if isinstance(ddl,list):
            [cursor.execute(d) for d in ddl]
        else:
            cursor.execute(ddl)
        conn.commit()
        conn.close()
        logger.info(f"创建数据表成功")
         
 
    def query(self, sql:str):
        """查询数据库并将结果保存到 pandas DataFrame"""
        conn = self.create_connection()
        df = None
        try:
            df = pd.read_sql(sql, conn)
        except Exception as e:
            logger.error(f"Query {sql} error:{e}")
        finally:
            conn.close()
        return df
        
    def update_sql(self, sql:str) -> int:
        affected_rows = 0
        with self.create_connection() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(sql)
                affected_rows = cursor.rowcount
                conn.commit()
                cursor.close()
            except Exception as e:
                logger.error(f"Error {sql}:{e}")
                raise
        return affected_rows

    def update_sql_params(self, sql:str, values: Tuple[Any]) -> int:
        import json
        safe_values = tuple(
            json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
            for v in values
        )
        affected_rows = 0
        with self.create_connection() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(sql, safe_values)
                affected_rows = cursor.rowcount
                conn.commit()
                cursor.close()
            except Exception as e:
                logger.error(f"Error {sql}:{e}")
                raise
        return affected_rows
 
    def update(self, df:pd.DataFrame, table_name:str):
        table = self.metadata.tables.get(table_name)
        
        # 获取表的唯一约束列
        for c in table.constraints:
            if isinstance(c, UniqueConstraint):
                conflict_cols = [col.name for col in c.columns]
                break

        if conflict_cols:
            # 循环插入每条记录，并冲突时更新
            with self.engine.begin() as conn:
                try:
                    rows = df.to_dict(orient="records")
                    if rows:
                        stmt = insert(table)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=conflict_cols,
                            set_={c.name: stmt.excluded[c.name] for c in table.columns if c.name not in conflict_cols}
                        )   
                        conn.execute(stmt, rows)
                    logger.info(f"Engine mode: table {table_name} upsert {len(df)} rows.")
                except Exception as e:
                    logger.error(f"Error save to {table_name}: {e}")
                    raise

            """
            with self.engine.begin() as conn:
                try:
                    for row in df.to_dict(orient='records'):
                        stmt = insert(table).values(**row)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=conflict_cols,
                            set_={k: v for k, v in row.items() if k not in conflict_cols}
                        )
                        conn.execute(stmt)
                    logger.info(f"Engine mode: table {table_name} upsert {len(df)} rows.")
                except Exception as e:
                    logger.error(f"Error save to {table_name}:{e}")
                    raise
            """
        else:
            """无唯一约束键模式, 将 pandas DataFrame 保存到数据库"""
            with self.create_connection() as conn:
                try:
                    # 使用 replace 模式，并处理重复数据
                    df.to_sql(table_name, conn, if_exists='replace', index=False, method='multi')
                    logger.info(f"df mode: table {table_name} insert {len(df)} rows.")
                except Exception as e:
                    logger.error(f"Error saving to {table_name}: {e}")
                    raise

class QuantDB:
    def __init__(self, db_path = "./data/quant_data.db"):
        self.db = DB(db_path)

    def init_db(self):
        table_ddl = [
            """
            CREATE TABLE IF NOT EXISTS stock_price (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                interval TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                amount REAL,
                UNIQUE(symbol, date, interval)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY,
                symbol TEXT,
                title TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                source TEXT,
                publish_date TEXT
            )   
            """,
            """
            CREATE TABLE IF NOT EXISTS stock_base (
                id INTEGER PRIMARY KEY,
                symbol TEXT,
                name TEXT,
                exchange TEXT,
                status TEXT,
                UNIQUE(symbol, exchange)
            )   
            """,
            """
            CREATE TABLE IF NOT EXISTS stock_info (
                symbol TEXT,
                status TEXT,
                market_cap DOUBLE,
                current_price DOUBLE,
                fifty_two_week_high DOUBLE,
                fifty_two_week_low DOUBLE,
                all_time_high DOUBLE,
                all_time_low DOUBLE,
                short_ratio DOUBLE,
                country TEXT,
                industry TEXT,
                sector TEXT,
                quote_type TEXT,
                recommendation TEXT,
                info TEXT,
                UNIQUE(symbol)
            )            
            """,
            """
            CREATE TABLE IF NOT EXISTS analysis_report (
                symbol TEXT,
                date TEXT,
                three_filters_score double,
                three_filters_report TEXT,
                double_bottom_score double,
                double_bottom_report TEXT,
                double_top_score double,
                double_top_report TEXT,
                cup_handle_score double,
                cup_handle_report TEXT,
                UNIQUE(symbol, date)
            )   
            """,
        ]
        self.db.ddl(table_ddl)

    def refresh_stock_base(self, df):
        if isinstance(df, pd.DataFrame) and not df.empty:
            self.db.update(df, "stock_base")
        else:
            logger.error("Refresh stock base error: data is not data frame.")

    def update_stock_status(self, symbol:str, status:str):
        sql = f"UPDATE stock_base SET status = '{status}' WHERE symbol='{symbol}'"
        self.db.update_sql(sql)

    def query_stock_base(self, exchange: str=None, top_k: int=None):
        sql = "SELECT a.symbol, a.name, b.market_cap FROM stock_base a left join stock_info b on a.symbol = b.symbol "
        if exchange is not None:
            sql += f" WHERE a.status != '0' AND a.exchange = '{exchange}'"
        sql += " ORDER BY b.market_cap DESC"
        if top_k is not None:
            sql += f" Limit {top_k}" 
        df = self.db.query(sql)
        df["market_cap"] = df["market_cap"].apply(
            lambda x: f"{float(x):.0f}" if pd.notnull(x) else "0"
        )
        return df

    def update_stock_info(self, keyvalues:Dict[str, Any]):
        sql = f"INSERT or REPLACE INTO stock_info({','.join(keyvalues.keys())})VALUES({','.join(['?']*len(keyvalues))})"
        self.db.update_sql_params(sql, keyvalues.values())

    def query_stock_info(self, symbol:str):
        sql = f"SELECT * FROM stock_info WHERE symbol = '{symbol}'"
        return self.db.query(sql)

    def update_stock_price(self, df):
        if isinstance(df, pd.DataFrame) and not df.empty:
            self.db.update(df, "stock_price")
        else:
            logger.error("Update stock price error: not data frame or empty.")

    def query_stock_price(self, 
            symbol: str, 
            interval: str=None,
            date: str=None, 
            top_k:int=None
        ):
        sql = "SELECT a.*, b.current_price, b.fifty_two_week_high, b.fifty_two_week_low, b.short_ratio, b.country, b.industry, b.sector, b.recommendation FROM stock_price a LEFT JOIN stock_info b ON a.symbol = b.symbol" 
        if symbol is not None:
            sql += f" WHERE a.symbol = '{symbol}'"
        if interval is not None:
            sql += f" AND a.interval = '{interval}'"
        if date is not None:
            sql += f" AND a.date <= '{date}'"
        sql += " ORDER BY a.date DESC"
        if top_k:
            sql += f" LIMIT {top_k}"

        df = self.db.query(sql).sort_values(
            by="date", 
            ascending=True
        ).reset_index(drop=True)

        return df

    def lastest_stock_price(self, symbol: str, interval=str) -> str:
        sql = f"SELECT date FROM stock_price WHERE symbol = '{symbol}' AND interval = '{interval}' ORDER BY date DESC LIMIT 1"
        return self.db.query(sql)

    def query_analysis_report(self, 
            symbol: str, 
            date: str=None,
            top_k: int=20,
            score_only: bool=True,
        ) -> pd.DataFrame:
        fields = "symbol, date, three_filters_score, double_bottom_score, double_top_score, cup_handle_score" if score_only else "*"
        sql = f"SELECT {fields} FROM analysis_report WHERE symbol = '{symbol}'"
        if date is not None:
            sql += f" AND date = '{date}'"
        sql += " ORDER BY date DESC"
        if top_k is not None:
            sql += f" LIMIT {top_k}"
        return self.db.query(sql)
    
    def update_analysis_report(self, df:pd.DataFrame):
        if isinstance(df, pd.DataFrame) and not df.empty:
            self.db.update(df, "analysis_report")
        else:
            logger.error("Update analysis report error: not data frame or empty.")


if __name__ == '__main__':
    db = QuantDB()
    symbol = "XPEV"
   
    #db.init_db()
    """
    logger.info("Database and tables created successfully.")
    df= db.query_stock_price("XPEV", "1min")
    pd.set_option('display.max_columns', None)  # 显示所有列
    pd.set_option('display.max_rows', None) 
    print(df)
    """
    #database = DB("./data/quant_data.db")
    #database.update_sql(f"DELETE FROM stock_base where exchange != 'us'")
    #print(db.query_stock_base(exchange="cn"))
    df = db.query_analysis_report(symbol)
    #print(df["info"])
    #df = db.query_stock_base("us")
    print(df)
