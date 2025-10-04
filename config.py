# config.py
import os

# Finnhub API Key
FINNHUB_API_KEY = "YOUR_FINNHUB_API_KEY"

# 爬取股票列表
STOCK_TICKERS = ["XPEV", "TSLA", "AAPL", "MSFT"]

# 数据保存路径
DATA_PATH = "data"
STOCKS_PATH = os.path.join(DATA_PATH, "stocks")
NEWS_PATH = os.path.join(DATA_PATH, "news")

os.makedirs(STOCKS_PATH, exist_ok=True)
os.makedirs(NEWS_PATH, exist_ok=True)

# --- 反爬策略配置 ---
# 代理池配置 (免费或付费代理服务)
PROXY_POOL = [
    "http://user:pass@123.45.67.89:8080",
    "http://user:pass@98.76.54.32:8080",
    # 可以添加更多代理IP
]

# 请求头配置，伪造User-Agent
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

OpenAI_CONFIG = {
    "model": "gpt-4o-mini",
    "base_url": "https://free.v36.cm/v1/",    
    "api_key": "sk-p1JBAYtwircCFdGP407a6185DdA64878BaF9F1Bd731349F6"
}

# 随机延迟范围 (秒)
DELAY_RANGE = (1, 5)

# 请求失败重试次数
RETRY_COUNT = 3
