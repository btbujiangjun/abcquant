# spiders/base_spider.py

import requests
from utils.logger import log
from utils.request_helper import get_request_with_retry

class BaseSpider:
    def __init__(self):
        self.log = log

    def fetch_data(self, url, params=None, method='get', **kwargs):
        """通用的数据抓取方法"""
        self.log.info(f"Fetching data from {url}")
        response = get_request_with_retry(url, method=method, params=params, **kwargs)
        if response and response.status_code == 200:
            return response.text
        self.log.error(f"Failed to fetch data from {url}")
        return None
