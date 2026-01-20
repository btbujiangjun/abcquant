import re

class MarketIdentifier:
    """
    股票市场识别工具类
    支持 A股 (CN), 港股 (HK), 美股 (US)
    """
    
    # 定义常见后缀映射
    MARKET_MAP = {
        'SS': 'CN',              # 上海
        'SH': 'CN',              # 上海
        'SZ': 'CN',              # 深圳
        'BJ': 'CN',              # 北京
        'HK': 'HK',              # 香港
        'US': 'US',              # 美国 (通用)
    }

    @classmethod
    def identify(cls, symbol: str) -> str:
        """
        识别主入口
        :param symbol: 原始代码，如 '00700', 'AAPL', '600519.SH', '000001.SZ'
        :return: 'CN', 'HK', 'US' 或 'UNKNOWN'
        """
        if not symbol or not isinstance(symbol, str):
            return "UNKNOWN"
            
        symbol = symbol.upper().strip()

        # 1. 尝试通过显式后缀识别 (如 600519.SH, 00700.HK)
        if '.' in symbol:
            suffix = symbol.split('.')[-1]
            if suffix in cls.MARKET_MAP:
                return cls.MARKET_MAP[suffix]

        # 2. 尝试识别纯数字代码 (CN 或 HK)
        if symbol.isdigit():
            length = len(symbol)
            if length == 6:
                return "CN"
            if 1 <= length <= 5:
                # 港股代码补齐后通常为 5 位，且在 1-9999 范围（包含创业板 8xxx）
                return "HK"

        # 3. 尝试识别纯字母代码 (US)
        if symbol.isalpha():
            return "US"

        # 4. 复杂正则匹配 (处理带连字符或数字字母混合的情况)
        # 美股可能包含连字符 (如 BRK-B)
        if re.match(r'^[A-Z.\-]+$', symbol):
            return "US"
            
        # A股常见纯数字
        if re.match(r'^\d{6}$', symbol):
            return "CN"

        return "UNKNOWN"

    @classmethod
    def get_market_info(cls, symbol: str):
        """扩展信息：返回市场代码及标准化的 Symbol"""
        market = cls.identify(symbol)
        # 简单归一化示例
        clean_code = symbol.split('.')[0]
        return {
            "origin": symbol,
            "market": market,
            "pure_code": clean_code
        }
