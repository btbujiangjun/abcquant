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


import sys
import warnings
import numpy as np

# 1. 强行将警告转为错误，这样才能触发异常堆栈
warnings.simplefilter('error', RuntimeWarning)

# 2. 定义一个异常钩子：一旦程序崩了，立刻开启 PDB 调试模式
def info(type, value, tb):
    if hasattr(sys, 'ps1') or not sys.stderr.isatty():
        sys.__excepthook__(type, value, tb)
    else:
        import traceback, pdb
        traceback.print_exception(type, value, tb)
        print("\n--- 程序崩溃，进入交互式调试模式 ---")
        pdb.post_mortem(tb) # 停在案发现场

sys.excepthook = info




def main():
    logger.info("🚀Starting quant spider project...")

    # 1. 初始化数据库
    db = QuantDB()
    db.init_db()
    logger.info("👉Database initialized.")
    
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
