import inspect
import threading
from utils.logger import logger
import backtest.strategy as strategy_module

class StrategyRegistry:
    _registry = {}
    _lock = threading.Lock()
    _discovered = False

    @classmethod
    def discover(cls):
        if cls._discovered:
            return

        """
        自动化扫描 backtest.strategy 模块中所有继承自 BaseStrategy 的类
        """
        with cls._lock:
            if not cls._discovered:
                for name, obj in inspect.getmembers(strategy_module):
                    # BaseStrategy的子类但不是BaseStrategy
                    if inspect.isclass(obj) and \
                        issubclass(obj, strategy_module.BaseStrategy) and \
                        obj is not strategy_module.BaseStrategy:
                
                        cls._registry[name] = obj
                        cls._discovered = True

        logger.info(f"✅ 策略自动化注册完成，共加载 {len(cls._registry)} 个类: {list(cls._registry.keys())}")

    @classmethod
    def get_class(cls, class_name):
        """根据类名字符串获取类对象"""
        if not cls._registry:
            cls.discover()
        return cls._registry.get(class_name)

