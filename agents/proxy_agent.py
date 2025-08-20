# proxy_agent.py

import asyncio
import aiohttp
import time
import threading
from typing import List, Dict, Optional
from dataclasses import dataclass
from random import choice
from aiohttp import ClientTimeout, TCPConnector

#from ..utils.logger import log

@dataclass
class Proxy:
    ip: str
    port: int
    protocol: str = "http"
    last_checked: float = 0.0
    is_alive: bool = False
    fail_count: int = 0

    def url(self) -> str:
        return f"{self.protocol}://{self.ip}:{self.port}"

    def ssl(self) -> bool:
        return self.protocol.lower() == "https"

    def __hash__(self):
        return hash((self.ip, self.port, self.protocol))


class ProxyPool:
    # 类变量（全局共享）
    _instance = None
    _lock = threading.Lock()

    _init_proxies = [
        {"ip": "47.92.248.86", "port": 10000, "protocol": "https"},
        {"ip": "47.92.242.45", "port": 8999, "protocol": "http"},
        {"ip": "8.219.167.110", "port": 8082, "protocol": "http"},
        {"ip": "8.130.34.237", "port": 8080, "protocol": "http"},
        {"ip": "101.200.187.233", "port": 41890, "protocol": "http"},
        {"ip": "122.136.212.132", "port": 53281, "protocol": "http"},
        {"ip": "124.71.157.181", "port": 8020, "protocol": "http"},
        {"ip": "114.115.130.225", "port": 3128, "protocol": "https"},
        {"ip": "36.6.144.96", "port": 8089, "protocol": "http"},
        {"ip": "121.43.233.77", "port": 80, "protocol": "http"},
        {"ip": "8.140.199.37", "port": 7890, "protocol": "http"},
        {"ip": "175.24.164.254", "port": 80, "protocol": "http"},
        {"ip": "101.133.138.238", "port": 8118, "protocol": "http"},
        {"ip": "47.93.249.121", "port": 8118, "protocol": "http"},
        {"ip": "121.43.102.172", "port": 80, "protocol": "http"},
        {"ip": "43.243.234.21", "port": 8000, "protocol": "http"},
        {"ip": "121.40.101.174", "port": 80, "protocol": "http"},
        {"ip": "121.41.96.82", "port": 80, "protocol": "http"},
        {"ip": "47.98.240.73", "port": 80, "protocol": "http"},
        {"ip": "124.70.205.56", "port": 8089, "protocol": "https"},
        {"ip": "47.96.252.95", "port": 80, "protocol": "http"},
        {"ip": "121.40.101.10", "port": 80, "protocol": "http"},
        {"ip": "47.96.39.52", "port": 80, "protocol": "http"},
        {"ip": "47.99.73.126", "port": 80, "protocol": "http"},
        {"ip": "118.31.40.222", "port": 80, "protocol": "http"},
        {"ip": "121.43.232.142", "port": 80, "protocol": "http"},
        {"ip": "121.41.59.152", "port": 80, "protocol": "http"},
        {"ip": "121.199.29.75", "port": 80, "protocol": "http"},
        {"ip": "47.99.73.79", "port": 80, "protocol": "http"},
        {"ip": "47.99.151.66", "port": 80, "protocol": "http"},
        {"ip": "121.40.240.189", "port": 80, "protocol": "http"},
        {"ip": "101.37.22.158", "port": 80, "protocol": "http"},
        {"ip": "101.37.21.202", "port": 80, "protocol": "http"},
        {"ip": "121.40.249.227", "port": 80, "protocol": "http"},
        {"ip": "121.40.217.37", "port": 80, "protocol": "http"},
        {"ip": "121.43.33.29", "port": 80, "protocol": "http"},
        {"ip": "121.43.59.220", "port": 80, "protocol": "http"},
        {"ip": "116.62.136.190", "port": 80, "protocol": "http"},
        {"ip": "47.106.208.135", "port": 7777, "protocol": "http"},
        {"ip": "8.219.5.240", "port": 9992, "protocol": "https"},
        {"ip": "8.134.140.97", "port": 443, "protocol": "https"},
        {"ip": "39.104.79.145", "port": 50001, "protocol": "https"},
        {"ip": "222.89.237.101", "port": 9002, "protocol": "http"},
        {"ip": "111.3.102.207", "port": 30001, "protocol": "http"},
        {"ip": "114.231.42.178", "port": 8888, "protocol": "http"},
        {"ip": "114.231.45.164", "port": 8888, "protocol": "http"},
        {"ip": "42.193.179.113", "port": 8118, "protocol": "http"},
        {"ip": "114.231.41.81", "port": 8888, "protocol": "http"},
        {"ip": "121.5.130.51", "port": 8899, "protocol": "https"},
        {"ip": "8.219.208.252", "port": 10028, "protocol": "https"},
        {"ip": "39.99.54.91", "port": 80, "protocol": "http"},
        {"ip": "183.234.218.201", "port": 9002, "protocol": "http"},
        {"ip": "58.254.141.70", "port": 8998, "protocol": "http"},
        {"ip": "218.75.102.198", "port": 8000, "protocol": "http"},
        {"ip": "118.190.142.208", "port": 80, "protocol": "http"},
        {"ip": "47.94.207.215", "port": 3128, "protocol": "http"},
        {"ip": "223.123.100.138", "port": 8080, "protocol": "http"},
        {"ip": "139.227.214.142", "port": 3128, "protocol": "http"},
        {"ip": "183.240.23.105", "port": 8080, "protocol": "http"},
        {"ip": "39.106.60.216", "port": 3128, "protocol": "https"},
        {"ip": "106.54.88.99", "port": 8888, "protocol": "http"},
        {"ip": "61.186.204.158", "port": 7001, "protocol": "http"},
        {"ip": "58.214.243.91", "port": 80, "protocol": "http"},
        {"ip": "47.97.16.1", "port": 80, "protocol": "http"},
        {"ip": "39.108.254.31", "port": 80, "protocol": "http"},
        {"ip": "39.101.206.0", "port": 8080, "protocol": "http"},
        {"ip": "47.96.255.189", "port": 80, "protocol": "http"},
        {"ip": "101.43.178.227", "port": 7890, "protocol": "http"},
        {"ip": "47.98.112.38", "port": 80, "protocol": "http"}
    ]

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 避免重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.test_url = "http://httpbin.org/ip"
        self.timeout = 1
        self.check_interval = 30  # 每30秒检查一次

        self._proxies: Dict[str, Proxy] = {}
        self._available: List[Proxy] = []
        self._data_lock = threading.Lock()

        self._stop_event = threading.Event()
        self._checker_thread = None
        self._initialized = True

        self._start_background_checker()

    def _start_background_checker(self):
        """启动后台检测线程"""
        if self._checker_thread and self._checker_thread.is_alive():
            print("⚠️ 后台检测已在运行")
            return

        def run_loop():
            # 为线程创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # 🔁 首次立即检测
            try:
                loop.run_until_complete(self._check_all_proxies())
            except Exception as e:
                print(f"❌ 首次检测失败: {e}")

            # 🔁 周期性检测
            while not self._stop_event.is_set():
                try:
                    # 使用 sleep 并检查 stop_event
                    if self._stop_event.wait(self.check_interval):
                        print(f"被 set 就退出")
                        break  # 被 set 就退出
                    loop.run_until_complete(self._check_all_proxies())
                except Exception as e:
                    print(f"❌ 检测循环异常: {e}")
                    time.sleep(5)  # 避免异常频繁重启

            print("🛑 检测线程已退出")
            loop.close()

        # 启动线程（daemon=True 表示随主程序退出）
        self._checker_thread = threading.Thread(target=run_loop, name="ProxyChecker", daemon=True)
        self._checker_thread.start()
        print("✅ ProxyPool: 后台检测线程已启动")

    async def _check_all_proxies(self):
        """异步检测所有代理"""
        if not self._proxies:
            print("🔍 无代理需要检测")
            return

        print(f"[{time.strftime('%H:%M:%S')}] 开始检测 {len(self._proxies)} 个代理...")

        # ✅ 关键：设置底层连接超时和读超时
        connector = TCPConnector(
            limit=100,                    # 最大并发连接数
            limit_per_host=10,            # 每个 host 最大连接
            ssl=False
        )

        timeout = ClientTimeout(
            total=10,      # 总超时（包括连接、读、写）
            connect=5,     # 连接超时（关键！防卡住）
            sock_read=8,   # socket 读超时
            sock_connect=5 # socket 连接超时
        )

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        ) as session:
            tasks = [self._test_proxy(proxy, session) for proxy in self._proxies.values()]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        now = time.time()
        new_available = []

        with self._data_lock:
            for proxy, result in zip(self._proxies.values(), results):
                proxy.last_checked = now
                if isinstance(result, Exception):
                    proxy.is_alive = False
                    proxy.fail_count += 1
                else:
                    if result:
                        proxy.is_alive = True
                        proxy.fail_count = 0
                        new_available.append(proxy)
                    else:
                        proxy.is_alive = False
                        proxy.fail_count += 1

            self._available[:] = new_available  # 替换内容

        print(f"📊 检测完成，{len(new_available)} 个代理可用")

    async def _test_proxy(self, proxy: Proxy, session: aiohttp.ClientSession) -> bool:
        print(f"🧪 正在测试代理: {proxy.url()}")  # 👈 关键：确认是否打印
        try:
            async with session.get(
                self.test_url,
                proxy=proxy.url(),
                ssl=proxy.ssl()
            ) as resp:
                print(f"tested:{proxy}:{resp.status}")
                return resp.status == 200
        except Exception as e:
            print(f"test error:{e}")
            return False

    @classmethod
    def add_proxy(cls, ip: str, port: int, protocol: str = "http"):
        """静态方法：添加代理"""
        instance = cls()
        key = f"{ip}:{port}:{protocol}"
        with instance._data_lock:
            if key not in instance._proxies:
                instance._proxies[key] = Proxy(ip, port, protocol)
                print(f"➕ 添加代理: {key}")

    @classmethod
    def add_proxies(cls, proxy_list: List[Dict]):
        """静态方法：批量添加代理"""
        for p in proxy_list:
            cls.add_proxy(p["ip"], p["port"], p.get("protocol", "http"))

    @classmethod
    def get_random_proxy(cls) -> Optional[str]:
        """静态方法：获取一个随机可用代理 URL"""
        instance = cls()
        with instance._data_lock:
            if instance._available:
                return choice(instance._available).url()
            return None

    @classmethod
    def get_all_proxies(cls) -> List[str]:
        """静态方法：获取所有可用代理"""
        instance = cls()
        with instance._data_lock:
            return [p.url() for p in instance._available]

    @classmethod
    def size(cls) -> int:
        """静态方法：返回可用代理数量"""
        instance = cls()
        with instance._data_lock:
            return len(instance._available)

    @classmethod
    def shutdown(cls):
        """静态方法：关闭后台检测"""
        instance = cls()
        instance._stop_event.set()
        print("🛑 ProxyPool: 已关闭")


# ===================== 使用示例（任何地方均可调用）=====================
if __name__ == "__main__":
    # 添加代理（静态调用）
    #ProxyPool.add_proxies([
    #    {"ip": "127.0.0.1", "port": 7890, "protocol": "http"},  # Clash
    #    {"ip": "127.0.0.1", "port": 1080, "protocol": "socks5"}, # Shadowsocks
    #])

    #ProxyPool.add_proxies(ProxyPool._init_proxies)
    
    ProxyPool.add_proxies([
        {"ip": "121.43.59.220", "port": 80, "protocol": "https"}
    ])

    time.sleep(10)

    # 模拟多个模块持续访问
    for i in range(100):
        time.sleep(3)
        proxy = ProxyPool.get_random_proxy()
        print(f"请求 {i+1}: 获取代理 -> {proxy} | 当前池大小: {ProxyPool.size()}")
