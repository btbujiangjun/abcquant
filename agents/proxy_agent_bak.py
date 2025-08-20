# agents/proxy_agent.py
import requests
import time
import threading
import random
import json
from datetime import datetime
from utils.logger import log

class ProxyPool:
    def __init__(self, proxies, check_interval=300, timeout=5):
        """
        初始化代理池
        :param proxies: 代理列表，格式为 [{"url": "http://ip:port", "protocol": "HTTP/HTTPS"}, ...]
        :param check_interval: 检测间隔（秒），默认300秒（5分钟）
        :param timeout: 请求超时时间（秒），默认5秒
        """
        self.proxies = proxies
        self.valid_proxies = []  # 存储有效代理
        self.check_interval = check_interval
        self.timeout = timeout
        self.lock = threading.Lock()  # 线程锁，确保线程安全
        self.running = False  # 控制定时检测线程
        self.output_file = "valid_proxies.json"  # 有效代理保存文件

    def test_proxy(self, proxy_url, protocol):
        """
        测试单个代理的可用性
        :param proxy_url: 代理URL (http://ip:port 或 https://ip:port)
        :param protocol: 协议 (HTTP 或 HTTPS)
        :return: (status_code, error_message) - 200表示成功，其他为失败
        """
        try:
            proxy_dict = {"http": proxy_url, "https": proxy_url}
            test_url = "https://httpbin.org/ip" if protocol == "HTTPS" else "http://httpbin.org/ip"
            response = requests.get(test_url, proxies=proxy_dict, timeout=self.timeout)
            return response.status_code, None
        except Exception as e:
            return None, f"{proxy_url} ({protocol}) failed: {str(e)}"

    def check_proxies(self):
        """
        检查所有代理的可用性，更新有效代理列表
        """
        while True:
            if self.running:
                new_valid_proxies = []
                log.info(f"[{datetime.now()}] 开始检查代理池...")
                for proxy in self.proxies:
                    status_code, error = self.test_proxy(proxy["url"], proxy["protocol"])
                    if status_code == 200:
                        new_valid_proxies.append(proxy)
                        log.info(f"{proxy['url']} ({proxy['protocol']}) status: 200")
                    else:
                        log.info(error or f"{proxy['url']} ({proxy['protocol']}) status: {status_code}")
                        time.sleep(1)  # 避免请求过于频繁

                # 更新有效代理列表（线程安全）
                with self.lock:
                    self.valid_proxies = new_valid_proxies
                    self.save_valid_proxies()
                log.info(f"[{datetime.now()}] 检查完成，有效代理数: {len(self.valid_proxies)}")
            time.sleep(10)

    def save_valid_proxies(self):
        """
        将有效代理保存到文件
        """
        with self.lock:
            with open(self.output_file, "w") as f:
                json.dump(self.valid_proxies, f, indent=4)
            log.info(f"[{datetime.now()}] 有效代理已保存到 {self.output_file}")

    def get_proxy(self, random_select=True):
        """
        对外接口：获取一个有效代理
        :param random_select: 是否随机选择代理，默认为True
        :return: 代理字典 {"url": "http://ip:port", "protocol": "HTTP/HTTPS"} 或 None
        """
        with self.lock:
            if not self.valid_proxies:
                log.info("无有效代理可用")
                return None
            if random_select:
                return random.choice(self.valid_proxies)
            return self.valid_proxies[0]  # 返回第一个有效代理

    def get_all_valid_proxies(self):
        """
        对外接口：获取所有有效代理
        :return: 有效代理列表
        """
        with self.lock:
            return self.valid_proxies.copy()

    def start_periodic_check(self):
        """
        启动定期检测线程
        """
        self.running = True
        def periodic_task():
            while self.running:
                self.check_proxies()
                time.sleep(self.check_interval)

        check_thread = threading.Thread(target=periodic_task, daemon=True)
        check_thread.start()
        log.info(f"[{datetime.now()}] 定期检测已启动，检测间隔: {self.check_interval}秒")

    def stop_periodic_check(self):
        """
        停止定期检测
        """
        self.running = False
        log.info(f"[{datetime.now()}] 定期检测已停止")

# 代理列表（从你的数据中获取）
proxies = [
    {"url": "https://47.92.248.86:10000", "protocol": "HTTPS"},
    {"url": "http://47.92.242.45:8999", "protocol": "HTTP"},
    {"url": "http://8.219.167.110:8082", "protocol": "HTTP"},
    {"url": "http://8.130.34.237:8080", "protocol": "HTTP"},
    {"url": "http://101.200.187.233:41890", "protocol": "HTTP"},
    {"url": "http://122.136.212.132:53281", "protocol": "HTTP"},
    {"url": "http://124.71.157.181:8020", "protocol": "HTTP"},
    {"url": "https://114.115.130.225:3128", "protocol": "HTTPS"},
    {"url": "http://36.6.144.96:8089", "protocol": "HTTP"},
    {"url": "http://121.43.233.77:80", "protocol": "HTTP"},
    {"url": "http://8.140.199.37:7890", "protocol": "HTTP"},
    {"url": "http://175.24.164.254:80", "protocol": "HTTP"},
    {"url": "http://101.133.138.238:8118", "protocol": "HTTP"},
    {"url": "http://47.93.249.121:8118", "protocol": "HTTP"},
    {"url": "http://121.43.102.172:80", "protocol": "HTTP"},
    {"url": "http://43.243.234.21:8000", "protocol": "HTTP"},
    {"url": "http://121.40.101.174:80", "protocol": "HTTP"},
    {"url": "http://121.41.96.82:80", "protocol": "HTTP"},
    {"url": "http://47.98.240.73:80", "protocol": "HTTP"},
    {"url": "https://124.70.205.56:8089", "protocol": "HTTPS"},
    {"url": "http://47.96.252.95:80", "protocol": "HTTP"},
    {"url": "http://121.40.101.10:80", "protocol": "HTTP"},
    {"url": "http://47.96.39.52:80", "protocol": "HTTP"},
    {"url": "http://47.99.73.126:80", "protocol": "HTTP"},
    {"url": "http://118.31.40.222:80", "protocol": "HTTP"},
    {"url": "http://121.43.232.142:80", "protocol": "HTTP"},
    {"url": "http://121.41.59.152:80", "protocol": "HTTP"},
    {"url": "http://121.199.29.75:80", "protocol": "HTTP"},
    {"url": "http://47.99.73.79:80", "protocol": "HTTP"},
    {"url": "http://47.99.151.66:80", "protocol": "HTTP"},
    {"url": "http://121.40.240.189:80", "protocol": "HTTP"},
    {"url": "http://101.37.22.158:80", "protocol": "HTTP"},
    {"url": "http://101.37.21.202:80", "protocol": "HTTP"},
    {"url": "http://121.40.249.227:80", "protocol": "HTTP"},
    {"url": "http://121.40.217.37:80", "protocol": "HTTP"},
    {"url": "http://121.43.33.29:80", "protocol": "HTTP"},
    {"url": "http://121.43.59.220:80", "protocol": "HTTP"},
    {"url": "http://116.62.136.190:80", "protocol": "HTTP"},
    {"url": "http://47.106.208.135:7777", "protocol": "HTTP"},
    {"url": "https://8.219.5.240:9992", "protocol": "HTTPS"},
    {"url": "https://8.134.140.97:443", "protocol": "HTTPS"},
    {"url": "https://39.104.79.145:50001", "protocol": "HTTPS"},
    {"url": "http://222.89.237.101:9002", "protocol": "HTTP"},
    {"url": "http://111.3.102.207:30001", "protocol": "HTTP"},
    {"url": "http://114.231.42.178:8888", "protocol": "HTTP"},
    {"url": "http://114.231.45.164:8888", "protocol": "HTTP"},
    {"url": "http://42.193.179.113:8118", "protocol": "HTTP"},
    {"url": "http://114.231.41.81:8888", "protocol": "HTTP"},
    {"url": "https://121.5.130.51:8899", "protocol": "HTTPS"},
    {"url": "https://8.219.208.252:10028", "protocol": "HTTPS"},
    {"url": "http://39.99.54.91:80", "protocol": "HTTP"},
    {"url": "http://183.234.218.201:9002", "protocol": "HTTP"},
    {"url": "http://58.254.141.70:8998", "protocol": "HTTP"},
    {"url": "http://218.75.102.198:8000", "protocol": "HTTP"},
    {"url": "http://118.190.142.208:80", "protocol": "HTTP"},
    {"url": "http://47.94.207.215:3128", "protocol": "HTTP"},
    {"url": "http://223.123.100.138:8080", "protocol": "HTTP"},
    {"url": "http://139.227.214.142:3128", "protocol": "HTTP"},
    {"url": "http://183.234.218.205:9002", "protocol": "HTTP"},
    {"url": "http://120.232.194.134:8998", "protocol": "HTTP"},
    {"url": "http://182.44.32.239:7890", "protocol": "HTTP"},
    {"url": "http://183.214.203.219:8060", "protocol": "HTTP"},
    {"url": "http://120.205.70.102:8060", "protocol": "HTTP"},
    {"url": "http://8.134.115.2:8123", "protocol": "HTTP"},
    {"url": "http://183.240.23.105:8080", "protocol": "HTTP"},
    {"url": "https://39.106.60.216:3128", "protocol": "HTTPS"},
    {"url": "http://106.54.88.99:8888", "protocol": "HTTP"},
    {"url": "http://61.186.204.158:7001", "protocol": "HTTP"},
    {"url": "http://58.214.243.91:80", "protocol": "HTTP"},
    {"url": "http://47.97.16.1:80", "protocol": "HTTP"},
    {"url": "http://39.108.254.31:80", "protocol": "HTTP"},
    {"url": "http://39.101.206.0:8080", "protocol": "HTTP"},
    {"url": "http://47.96.255.189:80", "protocol": "HTTP"},
    {"url": "http://101.43.178.227:7890", "protocol": "HTTP"},
    {"url": "http://47.98.112.38:80", "protocol": "HTTP"}
]

def main():
    # 初始化代理池
    proxy_pool = ProxyPool(proxies, check_interval=300, timeout=5)
    
    # 启动定期检测
    proxy_pool.start_periodic_check()
    
    # 示例：获取有效代理
    try:
        while True:
            # 获取一个随机有效代理
            proxy = proxy_pool.get_proxy(random_select=True)
            if proxy:
                print(f"获取到有效代理: {proxy}")
            else:
                print("当前无有效代理")
            
            # 获取所有有效代理
            all_proxies = proxy_pool.get_all_valid_proxies()
            print(f"所有有效代理: {all_proxies}")
            
            time.sleep(10)  # 每10秒获取一次，模拟使用
    except KeyboardInterrupt:
        # 捕获Ctrl+C，停止定期检测
        proxy_pool.stop_periodic_check()
        print("程序退出")

if __name__ == "__main__":
    main()
