# spiders/news_spider.py
from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd
from .base_spider import BaseSpider

class NewsSpider(BaseSpider):
    def get_baidu_news(self, query):
        """爬取百度财经新闻"""
        url = f"https://www.baidu.com/s?tn=news&rtt=1&bsst=1&wd={query}&cl=2"
        html = self.fetch_data(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'lxml')
        news_items = []
        items = soup.select('.news-list > .result')
        
        for item in items:
            title_tag = item.select_one('h3.c-title a')
            link_tag = item.select_one('h3.c-title a')
            source_time_tag = item.select_one('.c-summary .c-info span.c-info')

            if title_tag and link_tag and source_time_tag:
                news_items.append({
                    "ticker": query,
                    "title": title_tag.text.strip(),
                    "link": link_tag['href'],
                    "source": source_time_tag.text.strip().split(' ')[0],
                    "publish_date": self._parse_date(source_time_tag.text.strip())
                })
        
        return pd.DataFrame(news_items)

    def _parse_date(self, date_str):
        """解析日期字符串，例如 '新华网 10分钟前' -> YYYY-MM-DD HH:MM:SS"""
        if '分钟前' in date_str:
            minutes_ago = int(date_str.split(' ')[-2])
            return (datetime.now() - pd.Timedelta(minutes=minutes_ago)).strftime('%Y-%m-%d %H:%M:%S')
        # 可以添加更多解析规则
        return date_str

if __name__ == '__main__':
    spider = NewsSpider()
    result = spider.get_baidu_news("TSLA财报+股价")
    print(result)
