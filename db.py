# db.py
import sqlite3
import pandas as pd
import os

DB_PATH = 'data/quant_data.db'

def create_connection():
    """创建并返回数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def create_tables():
    """创建数据库表"""
    conn = create_connection()
    cursor = conn.cursor()
    
    # 股票历史数据表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_prices (
            id INTEGER PRIMARY KEY,
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            UNIQUE(ticker, date)
        )
    """)
    
    # 财经新闻表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY,
            ticker TEXT,
            title TEXT NOT NULL,
            link TEXT NOT NULL UNIQUE,
            source TEXT,
            publish_date TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def save_dataframe_to_db(df, table_name):
    """将 pandas DataFrame 保存到数据库"""
    conn = create_connection()
    try:
        # 使用 append 模式，并处理重复数据
        df.to_sql(table_name, conn, if_exists='append', index=False, method='multi')
    except Exception as e:
        print(f"Error saving to {table_name}: {e}")
        # 这里可以添加更详细的错误处理，例如记录哪些行失败
    finally:
        conn.close()

if __name__ == '__main__':
    create_tables()
    print("Database and tables created successfully.")
