# config.py
import os

# Finnhub API Key
FINNHUB_API_KEY = "YOUR_FINNHUB_API_KEY"

# 爬取股票列表
CRITICAL_STOCKS = [
    {"name":"NVDA", "exchange":"us"},
    {"name":"XPEV", "exchange":"us"},
    {"name":"LI", "exchange":"us"},
    {"name":"NIO", "exchange":"us"},
    #{"name":"NVDA", "exchange":"us"},
    {"name":"TSLA", "exchange":"us"},
    {"name":"BABA", "exchange":"us"},
    {"name":"MU", "exchange":"us"},
    {"name":"TQQQ", "exchange":"us"},
    {"name":"SQQQ", "exchange":"us"},
    {"name":"QQQ", "exchange":"us"},
    {"name":"PDD", "exchange":"us"},
    {"name":"NBIS", "exchange":"us"},
    {"name":"CRWV", "exchange":"us"},
    {"name":"MSTX", "exchange":"us"},
    {"name":"MSTZ", "exchange":"us"},
    {"name":"SE", "exchange":"us"},
    {"name":"HOOD", "exchange":"us"},
    {"name":"BILI", "exchange":"us"},
    {"name":"YINN", "exchange":"us"},
    {"name":"IXIC", "exchange":"us"},
    {"name":"AMD", "exchange":"us"},
    {"name":"INTC", "exchange":"us"},
    {"name":"META", "exchange":"us"},
    {"name":"GOOG", "exchange":"us"},
    {"name":"AMZN", "exchange":"us"},
    {"name":"TSM", "exchange":"us"},
    {"name":"AVGO", "exchange":"us"},
    {"name":"BIDU", "exchange":"us"},
    {"name":"EOSE", "exchange":"us"},
]

CRITICAL_STOCKS_US = [stock["name"] for stock in CRITICAL_STOCKS if stock["exchange"]=="us"]

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
    "api_key": "sk-lNnZ482Z77KMAdF32c6b686aE7824a0291097a438d7854B6"
}
"""
OpenAI_CONFIG = {
    "model": "gpt-4o-mini",
    "base_url": "https://api.chatanywhere.tech",    
    "api_key": "sk-EiUbTR3acpNJkHhPoQBz5E35YW1jOLJRt7yE8vhU3aQuSx32"
}
"""
OLLAMA_CONFIG = {
    #"model": "gpt-oss:20b",
    #"model": "gemma3:27b",
    "model": "qwen3:30b",
    #"model": "qwq:32b",
    "base_url": "http://localhost:11434/api/chat" 
}

# 随机延迟范围 (秒)
DELAY_RANGE = (1, 5)

# 请求失败重试次数
RETRY_COUNT = 3
