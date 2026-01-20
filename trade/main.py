import time
import futu as ft
from trade.config import TradeConfig
from trade.gateway import FutuGateway
from utils.logger import logger

class EMAStrategy:
    """双均线金叉死叉策略逻辑"""
    @staticmethod
    def get_signal(df):
        if df is None or len(df) < TradeConfig.EMA_LONG + 1:
            return None
            
        # 计算 EMA
        ema_s = df['close'].ewm(span=TradeConfig.EMA_SHORT, adjust=False).mean()
        ema_l = df['close'].ewm(span=TradeConfig.EMA_LONG, adjust=False).mean()
        
        # 金叉：短线向上穿过长线
        if ema_s.iloc[-1] > ema_l.iloc[-1] and ema_s.iloc[-2] <= ema_l.iloc[-2]:
            return "BUY"
        # 死叉：短线向下穿过长线
        if ema_s.iloc[-1] < ema_l.iloc[-1] and ema_s.iloc[-2] >= ema_l.iloc[-2]:
            return "SELL"
        return None

def main():
    # 1. 初始化网关与状态
    bot = FutuGateway()
    last_recon_day = ""
    logger.info(f"🚀 量化机器人已启动 | 模式: {TradeConfig.CURRENT_MODE} | 标的: {TradeConfig.SCAN_LIST}")
    
    # 2. 查看账户信息
    bot.get_account_status()
    bot.sync_positions()
    bot.daily_reconciliation()        
    try:
        while True:
            # --- 第一阶段：风控与对账维护 ---
            # 同步柜台真实持仓镜像（用于日志打印和对账）
            bot.sync_positions()
            # 检查并取消超时未成交订单
            bot.check_and_cancel_timeouts()

            # --- 第二阶段：定时任务（收盘对账） ---
            curr_t = time.strftime("%H:%M")
            curr_d = time.strftime("%Y-%m-%d")
            
            # 假设在美东时间 16:15 执行每日对账报表推送
            if curr_t == TradeConfig.RECON_TIME and last_recon_day != curr_d:
                logger.info("⏰ 到达定时任务时间，执行收盘对账...")
                bot.daily_reconciliation()
                last_recon_day = curr_d
            
            # --- 第三阶段：策略执行逻辑 ---
            # 获取数据库中记录的逻辑持仓
            logic_positions = bot.db.get_positions()
            # 获取K线行情
            market_data = bot.get_market_data()
            
            for symbol, df in market_data.items():
                signal = EMAStrategy.get_signal(df)
                
                # 基于 SQLite 记录的逻辑持仓决定是否交易，实现真正的账户隔离
                quant_pos_qty = logic_positions.get(symbol, {}).get('qty', 0)
                
                if signal == "BUY" and quant_pos_qty == 0:
                    logger.info(f"📈 {symbol} 触发金叉买入信号 | 当前逻辑持仓: {quant_pos_qty}")
                    bot.execute_trade(symbol, ft.TrdSide.BUY)
                    
                elif signal == "SELL" and quant_pos_qty > 0:
                    logger.info(f"📉 {symbol} 触发死叉卖出信号 | 当前逻辑持仓: {quant_pos_qty}")
                    bot.execute_trade(symbol, ft.TrdSide.SELL)

            # --- 第四阶段：活跃订单状态监控 ---
            with bot.lock:
                active_ids = [k for k, v in bot.active_orders.items() if v['is_active']]
                if active_ids:
                    logger.info(f"📊 监控中订单: {active_ids}")

            # 扫描频率：美股建议15-30秒，避免触发富途API流量限制
            time.sleep(30) 
            
    except KeyboardInterrupt:
        logger.info("⌨️ 用户手动停止机器人...")
    except Exception as e:
        logger.error(f"🚨 系统运行异常: {e}", exc_info=True)
    finally:
        bot.close()
        logger.info("🔌 API连接已关闭，程序退出。")

if __name__ == "__main__":
    main()
