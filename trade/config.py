import futu as ft

class TradeConfig:
    CURRENT_MODE = "SIMULATE" # 切换 REAL 开启实盘
    HOST = '127.0.0.1'
    PORT = 11111
    
    # --- 多标的配置 ---
    # 监控列表
    SCAN_LIST = ["US.NVDA", "US.TSLA", "US.AAPL", "US.MSFT", "US.GOOG"]
    SCAN_LIST = ["HK.00700", "HK.03690", "HK.09988"]    

    # --- 风控与头寸 ---
    QUANT_INITIAL_CASH = 50000.0 # 初始量化分配金额
    MAX_WEIGHT_PER_STOCK = 0.20  # 单只股票最大占用账户总资产的 20%
    SLIPPAGE_ADJUST = 0.01       # 滑点补偿 (美股建议0.01-0.02)
    ORDER_TIMEOUT = 60           # 订单超时自动撤单时间 (秒)

    EMA_SHORT = 12
    EMA_LONG = 26
    
    ENV_SETTINGS = {
        "SIMULATE": {"trd_env": ft.TrdEnv.SIMULATE, "unlock": False},
        "REAL": {"trd_env": ft.TrdEnv.REAL, "unlock": True, "password": "MD5"}
    }

    @classmethod
    def get_current(cls):
        return cls.ENV_SETTINGS[cls.CURRENT_MODE]

    # --- 自动化通知配置 ---
    # 邮件配置
    MAIL_CONFIG = {
        "host": "smtp.xxx.com",
        "user": "your_email@xxx.com",
        "pass": "your_smtp_password",
        "receivers": ["target_email@xxx.com"]
    }
    # 钉钉机器人 Webhook (若不需要可为空)
    DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"
    RECON_TIME = "16:10" # 每日对账时间

