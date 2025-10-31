import pandas as pd
from datetime import datetime, timedelta
from db import DB
from utils.time import *
from utils.logger import logger

class Dragon:
    def __init__(self, db_path = "./data/quant_data.db"):
        self.db = DB(db_path)
        
        table_ddl = [
          """
            CREATE TABLE IF NOT EXISTS dragon_growth (
                symbol TEXT,
                latest_date TEXT,
                prev_date TEXT,
                flag INTEGER,
                prev_close DOUBLE,
                latest_close DOUBLE,
                pct_change DOUBLE,
                UNIQUE(date, flag, symbol)
            )
            """,
        ]
        self.db.ddl(table_ddl)
 
    def run_growth(self, date:str, top_k:int=10, days:int=5):
        full_datetime = datetime.strptime(date, "%Y-%m-%d")
        start_datetime = full_datetime - timedelta(days=days)
        sql = f"DELETE FROM dragon_growth WHERE date = '{date}'"
        rows = self.db.update_sql(sql)
        if rows > 0:
            logger.info(f"Delete exists date: {rows}.")
        sql = f"""
WITH daily_with_prev AS (
    SELECT 
        symbol,
        SUBSTR(date, 1, 10) AS date,
        close,
        LAG(close) OVER (PARTITION BY symbol ORDER BY date) AS prev_close
    FROM stock_price
    WHERE interval = 'daily' AND date >= '{start_datetime}' AND date <= '{full_datetime}'
),
calc AS (
    SELECT
        date,
        symbol,
        prev_close,
        close AS latest_close,
        ROUND((close / prev_close - 1) * 100, 2) AS pct_change
    FROM daily_with_prev
    WHERE date = '{date}' AND prev_close IS NOT NULL
)
SELECT * FROM (
    SELECT 'TopGainers' AS flag, * FROM (
        SELECT * FROM calc ORDER BY pct_change DESC LIMIT {top_k}
    )
    UNION ALL
    SELECT 'TopLosers' AS flag, * FROM (
        SELECT * FROM calc ORDER BY pct_change ASC LIMIT {top_k}
    )
)
ORDER BY flag DESC, pct_change DESC;
"""
        df = self.db.query(sql)
        if len(df) > 0:
            self.db.update(df, "dragon_growth")
            logger.info(f"Dragon finished {df['date'].iloc[-1]}.")

    def get_growth(self, date:str=None, flag:str=None) -> pd.DataFrame:
        sql = f"SELECT * FROM dragon_growth"
        conditions = []
        if flag:
            conditions.append(f" flag ='{flag}'")
        if date:
            conditions.append(f" date = '{date}'")
        else:
            conditions.append(f" date = (SELECT max(date) FROM dragon_growth)")
        condition = "" if len(conditions) == 0 else " AND ".join(conditions)
        sql = sql if condition == "" else sql + " WHERE " + condition
        sql += f" ORDER BY date DESC"
        if flag is not None:
            sql += f", pct_change {'DESC' if flag == 'TopGainers' else 'ASC'}"  
        df = self.db.query(sql) 
        df['pct_change'] = df['pct_change'].apply(lambda x: f"{x:.2f}%")
        return df



if __name__ == '__main__':
    dragon = Dragon()
    date = days_delta(today_str(), -1)
    dragon.run_growth(date)
    df = dragon.get_growth(flag="TopGainers", date=date)   
    print(df.head)


