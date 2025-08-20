# utils/request_helper.py
import requests
import random
import time
from config import PROXY_POOL, USER_AGENTS, DELAY_RANGE, RETRY_COUNT

def get_request_with_retry(url, method='get', **kwargs):
    """
    封装带重试和反爬策略的 HTTP 请求
    """
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    proxies = None
    if PROXY_POOL:
        proxies = {'http': random.choice(PROXY_POOL), 'https': random.choice(PROXY_POOL)}

    for i in range(RETRY_COUNT):
        try:
            time.sleep(random.uniform(*DELAY_RANGE)) # 随机延迟
            print(f"Requesting {url} with attempt {i+1}...")
            
            if method == 'get':
                response = requests.get(url, headers=headers, proxies=proxies, **kwargs)
            else:
                response = requests.post(url, headers=headers, proxies=proxies, **kwargs)

            response.raise_for_status() # 如果请求失败 (4xx 或 5xx)，抛出异常
            return response
        except requests.exceptions.RequestException as e:
            print(f"Request to {url} failed: {e}")
            if i < RETRY_COUNT - 1:
                print(f"Retrying in {DELAY_RANGE[0]} seconds...")
                time.sleep(DELAY_RANGE[0])
            else:
                print("Max retries exceeded.")
                return None
