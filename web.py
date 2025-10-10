import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from db import QuantDB
from utils.logger import logger
from core.interval import DAY_INTERVAL
from config import CRITICAL_STOCKS_US

app = FastAPI()
db = QuantDB()

# 绑定模板目录
templates = Jinja2Templates(directory="templates")

# ===================
# 前端页面
# ===================
@app.get("/", response_class=HTMLResponse)
def get_index(request: Request):
    """返回前端页面"""
    return templates.TemplateResponse("index.html", {"request": request})


# ===================
# 后端接口
# ===================
@app.get("/stocks")
def get_us_stocks():
    """获取股票列表"""
    return [{"symbol": symbol, "name": symbol} for symbol in CRITICAL_STOCKS_US]
    df = db.query_stock_base(exchange="us", top_k=500)
    if df.empty:
        return []
    return [{"symbol": row["symbol"], "name": row["name"]} for _, row in df.iterrows()]


@app.get("/klines/{symbol}")
def get_klines(symbol: str, interval: str = "daily"):
    """获取K线数据"""
    df = db.query_stock_price(symbol, interval=interval)
    if df.empty:
        raise HTTPException(status_code=404, detail="未找到该股票的K线数据")

    print(df.head())

    # 自动补成交额 amount 字段
    if "amount" not in df.columns:
        df["amount"] = df["close"] * df.get("volume", 0)

    return [
        {
            "date": row["date"].split()[0] if interval in DAY_INTERVAL else row["date"].replace(" ", "T"),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row.get("volume", 0)),
            "amount": float(row.get("amount", 0)),
        }
        for _, row in df.iterrows()
    ]


@app.get("/quant_report/{symbol}")
def get_analysis_report(symbol: str):
    """获取量化分析报告"""
    df = db.query_analysis_report(symbol, score_only=False)
    if df.empty:
        raise HTTPException(status_code=404, detail="未找到该股票分析报告")

    df = df.sort_values("date", ascending=False)
    return [
        {
            "symbol": row["symbol"],
            "date": row["date"].split()[0],
            "price": row["close"],
            "update_time": row["update_time"],
            "three_filters_score": row.get("three_filters_score"),
            "three_filters_report": row.get("three_filters_report"),
            "double_bottom_score": row.get("double_bottom_score"),
            "double_bottom_report": row.get("double_bottom_report"),
            "double_top_score": row.get("double_top_score"),
            "double_top_report": row.get("double_top_report"),
            "cup_handle_score": row.get("cup_handle_score"),
            "cup_handle_report": row.get("cup_handle_report"),
        }
        for _, row in df.iterrows()
    ]


@app.get("/stock_info/{symbol}")
def get_stock_info(symbol: str):
    """获取单只股票的基本信息"""
    df = db.query_stock_info(symbol)
    if df.empty:
        raise HTTPException(status_code=404, detail="未找到该股票信息")
    row = df.iloc[0]
    return {
        "symbol": row["symbol"],
        "name": row["name"],
        "industry": row.get("industry"),
        "market_cap": row.get("market_cap"),
        "info": row.get("info"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

