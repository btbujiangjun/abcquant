# main.py
import os
import sys
import time
import signal

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import QuantDB
from utils.logger import logger
from agents.scheduler import Scheduler

def main():
    logger.info("Starting quant spider project...")

    # 1. 初始化数据库
    db = QuantDB()
    db.init_db()
    logger.info("Database initialized.")
    
    # 2. 启动调度器
    scheduler = Scheduler()
    scheduler.start()
    logger.info("Scheduler started.")

    # 3. 定义优雅退出函数
    def shutdown_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        scheduler.shutdown()
        sys.exit(0)

    # 捕获退出信号
    signal.signal(signal.SIGINT, shutdown_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, shutdown_handler)  # kill 命令
 
    try:
        # 保持主程序运行，以便调度器后台执行任务
        while True:
            time.sleep(2)
    except Exception as e:
        logger.error(f"Main loop exception: {e}")
        shutdown_handler(None, None)    

if __name__ == "__main__":
    main()
