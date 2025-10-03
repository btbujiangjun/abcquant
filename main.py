# main.py
import time
import sys
import os

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import QuantDB
from utils.logger import log
from agents.scheduler_agent import SchedulerAgent

def main():
    log.info("Starting quant spider project...")
    
    # 1. 初始化数据库
    QuantDB().init_db()
    
    # 2. 启动调度器
    scheduler_agent = SchedulerAgent()
    scheduler_agent.start_scheduler()
    
    try:
        # 保持主程序运行，以便调度器后台执行任务
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        log.info("Program terminated.")

if __name__ == "__main__":
    main()
