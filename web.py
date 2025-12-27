import json
import pandas as pd
from fastapi import Request
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import QuantDB
from utils.logger import logger
from core.interval import DAY_INTERVAL
from config import CRITICAL_STOCKS_US
from analysis.dragon import Dragon
from utils.time import today_str, days_delta
from backtest.worker import DefaultWorker


app = FastAPI()
db_path = "./data/quant_data.db"
db = QuantDB(db_path=db_path)
dragon = Dragon(db_path=db_path)
worker = DefaultWorker()

# 绑定模板目录
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
# ===================
# 前端页面
# ===================
@app.get("/", response_class=HTMLResponse)
def get_index(request: Request):
    """返回前端页面"""
    return templates.TemplateResponse("stock.html", {"request": request, "page":"stock", "title":"💹股票分析 - LLM K线系"})

@app.get("/dragon")
async def dragon_page(request: Request):
    return templates.TemplateResponse("dragon.html", {"request": request, "page":"dragon", "title":"🐲龙虎榜🐯"})

@app.get("/report")
async def report_page(request: Request):
    return templates.TemplateResponse("report.html", {"request": request, "page":"report", "title":"📊分析报告"})

@app.get("/backtest")
async def backtest_page(request: Request):
    return templates.TemplateResponse("backtest.html", {"request": request, "page":"backtest", "title":"📊分析报告"})

@app.get("/api/dragon")
async def get_dragon_data(date: str = None):
    rise_df = dragon.get_growth(flag="TopGainers", date=date)
    fall_df = dragon.get_growth(flag="TopLosers", date=date)
    top_report_df = dragon.get_report(flag="TopReports", date=date)
    bottom_report_df = dragon.get_report(flag="BottomReports", date=date)
    return {
        "Top_Gainers": [{"date": row["date"], "symbol": row["symbol"], "prev_close": row["prev_close"], "latest_close": row["latest_close"], "pct": row["pct_change"]} for _, row in rise_df.iterrows()],
        "Top_Losers": [{"date": row["date"], "symbol": row["symbol"], "prev_close": row["prev_close"], "latest_close": row["latest_close"], "pct": row["pct_change"]} for _, row in fall_df.iterrows()],
        "Top_Report": [{"date": row["date"], "symbol": row["symbol"], "prev_score": row["prev_score"], "score": row["score"]} for _, row in top_report_df.iterrows()],
        "Bottom_Report": [{"date": row["date"], "symbol": row["symbol"], "prev_score": row["prev_score"], "score": row["score"]} for _, row in bottom_report_df.iterrows()],
    }


#对评分赋予不同的颜色
def colorize(val):
    if val == '-' or val is None: return '<span class="score-missing">-</span>'
    try:
        v = float(val)
    except Exception:
        return val

    def fmt(v): return f"{v:.6f}".rstrip('0').rstrip('.')
    text = fmt(v)    
    cls = ""
    if v <= -0.7: cls = "score-negative-strong blink-soft"  # 深红 + 强闪
    elif v < 0: cls = "score-negative-weak"                 # 浅红
    elif v < 0.5: cls = "score-neutral"
    elif v <= 0.7: cls = "score-positive-weak"                 # 浅绿
    else: cls = "score-positive-strong blink-soft"    # 深绿 + 轻闪

    return f'<span class="{cls}">{text}</span>'


@app.get("/api/report")
async def get_report(date:str = None, interval:int = 30):
    end = date or today_str()
    start = days_delta(end, -(interval or 30))
    df = db.fetch_analysis_report(start, end) 
    table = (
        df.pivot(
            index='date',
            columns='symbol',
            values='score'
        ).sort_index(ascending=False).reset_index().fillna('-') 
    )
    table.columns.name = None

    # 将 symbol 列转换为超链接
    def symbol_link(col_name):
        return [
            f'<a href="/?symbol={symbol}">{symbol}</a>'
            for symbol in col_name
        ]

    # 更新列名为 HTML 超链接
    table.columns = ['date'] + symbol_link(table.columns[1:])

    for col in table.columns:
        if col != 'date':
            table[col] = table[col].apply(colorize)
    
    return {"data": table.to_html(index=False, escape=False)}


@app.get("/backtest/{symbol}")
async def backtest(symbol:str, start:str, end:str):
    json_obj = {}
    json_obj["symbol"] = symbol
    i, summary_table = 0, ""

    results = worker.backtest(symbol, start, end)
    for key, result in results.items():
        df = result["equity_df"]
        df['equity'] = df['equity'].round(2)
        equity = [row["equity"] for _, row in df.iterrows()]
        position = [row["position"] for _, row in df.iterrows()]
        signals = [
            {"date": row["date"], "type":row["ops"], "equity":row["equity"]} 
            for _, row in df.iterrows()
            if row["ops"] in ["BUY", "SELL"]
        ]
        if key == "LongTermValueStrategy":
            json_obj["dates"] = [row["date"] for _, row in df.iterrows()]
            json_obj["benchmark"] = equity
            json_obj["name"] = key
        else:
            if "strategies" not in json_obj:
                json_obj["strategies"] = []
            json_obj["strategies"].append({
                "name": key,
                "equity": equity,
                "signals": signals,
            })
        metrics = result["perf"]
        i += 1
        summary_table += f"<tr><td>{i}</td><td>{key}</td><td>{metrics['total_return']:.2%}</td><td>{metrics['max_drawdown']:.2%}</td><td>{metrics['win_rate']:.2%}</td><td>{df.iloc[0]['date']}-{df.iloc[-1]['date']}</td></tr>"
    json_obj["summary_table"] = summary_table
    return json.dumps(json_obj, ensure_ascii=False)

# ===================
# 后端接口
# ===================
@app.get("/stocks")
def get_us_stocks():
    """获取股票列表"""
    return [{"symbol": symbol, "name": symbol} for symbol in CRITICAL_STOCKS_US]

@app.get("/klines/{symbol}")
def get_klines(symbol: str, interval: str = "daily", start_date: str = None, end_date: str = None):
    """获取K线数据"""
    df = db.query_stock_price(symbol, interval=interval, start_date=start_date, end_date=end_date)
    if df.empty:
        raise HTTPException(status_code=404, detail="未找到该股票的K线数据")

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
def get_analysis_report(symbol: str, start_date: str = None, end_date: str = None):
    """获取量化分析报告"""
    df = db.query_analysis_report(symbol, top_k=None, start_date = start_date, end_date = end_date, score_only=False)
    if df.empty:
        raise HTTPException(status_code=404, detail="未找到该股票分析报告")

    df = df.sort_values("date", ascending=False)
    return [
        {
            "symbol": row["symbol"],
            "date": row["date"].split()[0],
            "price": row["close"],
            "update_time": row["update_time"],
            "three_filters_score": safe_get(row, "three_filters_score"),
            "three_filters_report": row.get("three_filters_report"),
            "double_bottom_score": safe_get(row, "double_bottom_score"),
            "double_bottom_report": row.get("double_bottom_report"),
            "double_top_score": safe_get(row, "double_top_score"),
            "double_top_report": row.get("double_top_report"),
            "cup_handle_score": safe_get(row, "cup_handle_score"),
            "cup_handle_report": row.get("cup_handle_report"),
        }
        for _, row in df.iterrows()
    ]
    return data

def safe_get(row, key, default=None):
    val = row.get(key, default)
    if pd.isna(val):
        return default
    return val


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

