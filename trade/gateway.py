import time
import threading
import pandas as pd
import futu as ft
from db import TradeDB
from trade.config import TradeConfig
from utils.logger import logger
from utils.notify import email_notify, dingtalk_notify 

class OrderHandler(ft.TradeOrderHandlerBase):
    """异步订单成交回报处理器：负责实盘成交价校准"""
    def __init__(self, gateway):
        super().__init__()
        self.gateway = gateway

    def on_recv_rsp(self, rsp_pb):
        ret, content = super().on_recv_rsp(rsp_pb)
        if ret != ft.RET_OK:
            return ret, content
            
        for _, r in content.iterrows():
            # 1. 核心：当订单完全成交时，更新逻辑账户（SQLite）
            if r['order_status'] == ft.OrderStatus.FILLED_ALL:
                success = self.gateway.db.record_trade(
                    r['order_id'], 
                    r['code'], 
                    r['trd_side'], 
                    r['dealt_qty'], 
                    r['dealt_avg_price']
                )
                if success:
                    msg = f"✅ 成交校准入账\n标的: {r['code']}\n均价: {r['dealt_avg_price']}\n数量: {r['dealt_qty']}"
                    logger.info(msg)
                    dingtalk_notify("交易确认", msg)
            
            # 2. 更新内存中的活跃订单状态
            self.gateway._update_active_order_status(
                r['order_id'], 
                r['order_status'], 
                r['dealt_qty']
            )
            
        return ret, content

class FutuGateway:
    def __init__(self):
        self.settings = TradeConfig.get_current()
        self.db = TradeDB() # 逻辑账本
        
        # 1. 初始化上下文
        self.quote_ctx = ft.OpenQuoteContext(host=TradeConfig.HOST, port=TradeConfig.PORT)
        if TradeConfig.SCAN_LIST[0].startswith("HK"):
            self.trd_ctx = ft.OpenHKTradeContext(host=TradeConfig.HOST, port=TradeConfig.PORT)
        else:
            self.trd_ctx = ft.OpenUSTradeContext(host=TradeConfig.HOST, port=TradeConfig.PORT)
        
        # 2. 内存状态
        self.active_orders = {}    # {order_id: info}
        self.real_positions = {}   # 柜台真实持仓镜像
        self.lock = threading.Lock()
        
        # 3. 注册处理器
        self.trd_ctx.set_handler(OrderHandler(self))
        self._prepare_env()

    def _prepare_env(self):
        """交易环境解锁与行情订阅"""
        if self.settings["unlock"]:
            ret, data = self.trd_ctx.unlock_trade(self.settings["password"])
            if ret != ft.RET_OK:
                logger.error(f"❌ 交易解锁失败: {data}")
        
        logger.info(f"📡 正在订阅行情: {TradeConfig.SCAN_LIST}")
        # 订阅1分钟K线和买卖盘
        self.quote_ctx.subscribe(TradeConfig.SCAN_LIST, [ft.SubType.K_1M, ft.SubType.ORDER_BOOK])

    # ========================== 数据获取功能 ==========================

    def get_market_data(self):
        """获取所有监控标的的K线数据"""
        res = {}
        for sym in TradeConfig.SCAN_LIST:
            ret, df = self.quote_ctx.get_cur_kline(sym, num=100, ktype=ft.KLType.K_1M)
            if ret == ft.RET_OK:
                res[sym] = df
            else:
                logger.error(f"❌ 获取行情失败 {sym}: {df}")
        return res

    def get_account_status(self):
        """打印并返回完整的账户透视表（逻辑 vs 柜台）"""
        ret, data = self.trd_ctx.accinfo_query(trd_env=self.settings["trd_env"])
        if ret != ft.RET_OK:
            logger.error(f"❌ 获取柜台资金失败: {data}")
            return None
            
        acc = data.iloc[0]
        logic_balance = self.db.get_balance()
        logic_pos = self.db.get_positions()
        
        status_report = (
            f"\n" + "="*40 + "\n"
            f"💰 [账户资金概览]\n"
            f"柜台总资产: {acc['total_assets']:.2f} | 现金: {acc['cash']:.2f}\n"
            f"量化逻辑余额: {logic_balance:.2f}\n"
            f"量化逻辑持仓: {list(logic_pos.keys())}\n"
            + "="*40
        )
        logger.info(status_report)
        return acc

    # ========================== 交易与订单管理 ==========================

    def execute_trade(self, symbol, side):
        """执行滑点下单"""
        # 1. 校验量化余额
        balance = self.db.get_balance()
        ret_snap, snap = self.quote_ctx.get_market_snapshot([symbol])
        if ret_snap != ft.RET_OK: return None
        last_price = snap['last_price'].iloc[0]

        # 2. 计算股数
        if side == ft.TrdSide.BUY:
            # 只能在分配给量化的金额内买入
            qty = int((balance * TradeConfig.MAX_WEIGHT_PER_STOCK) / last_price)
        else:
            # 只能卖出逻辑持仓内的股数
            qty = self.db.get_positions().get(symbol, {}).get('qty', 0)

        if qty <= 0: return None

        # 3. 获取深度数据计算滑点价
        ret_ob, ob = self.quote_ctx.get_order_book(symbol, num=1)
        price = last_price
        if ret_ob == ft.RET_OK:
            # 买入按卖一价加滑点，卖出按买一价减滑点
            price = ob['Ask'][0][0] + TradeConfig.SLIPPAGE_ADJUST if side == ft.TrdSide.BUY else ob['Bid'][0][0] - TradeConfig.SLIPPAGE_ADJUST

        # 4. 下单
        ret_o, data = self.trd_ctx.place_order(
            price=price, qty=qty, code=symbol, trd_side=side,
            order_type=ft.OrderType.NORMAL, trd_env=self.settings["trd_env"]
        )
        
        if ret_o == ft.RET_OK:
            order_id = data['order_id'].iloc[0]
            with self.lock:
                self.active_orders[order_id] = {
                    'code': symbol, 'side': side, 'qty': qty, 
                    'submit_time': time.time(), 'is_active': True
                }
            logger.info(f"📤 订单已发出: {symbol} {side} {qty}股 @{price}")
            return order_id
        return None

    def cancel_order(self, order_id):
        """手动撤单接口"""
        ret, data = self.trd_ctx.order_operator(ft.OrderOp.CANCEL, order_id=order_id, trd_env=self.settings["trd_env"])
        if ret == ft.RET_OK:
            logger.info(f"🚫 撤单成功: {order_id}")
            return True
        return False

    def check_and_cancel_timeouts(self):
        """自动超时撤单监控"""
        now = time.time()
        with self.lock:
            for oid, info in list(self.active_orders.items()):
                if info['is_active'] and (now - info['submit_time'] > TradeConfig.ORDER_TIMEOUT):
                    logger.warning(f"⏰ 订单 {oid} ({info['code']}) 超时未成交，执行撤单...")
                    self.cancel_order(oid)

    # ========================== 对账与同步 ==========================

    def sync_positions(self):
        """同步真实柜台持仓镜像"""
        ret, data = self.trd_ctx.position_list_query(trd_env=self.settings["trd_env"])
        if ret == ft.RET_OK:
            new_pos = {row['code']: {'qty': row['qty'], 'cost': row['cost_price']} for _, row in data.iterrows()}
            with self.lock:
                self.real_positions = new_pos
            logger.info(f"账户持仓:{new_pos}")
            return True
        return False

    def daily_reconciliation(self):
        """执行每日收盘对账报表"""
        self.sync_positions()
        logic_pos = self.db.get_positions()
        
        diffs = []
        for code, info in logic_pos.items():
            real_qty = self.real_positions.get(code, {}).get('qty', 0)
            if info['qty'] != real_qty:
                diffs.append(f"❌ 差异: {code} (逻辑:{info['qty']} | 柜台:{real_qty})")
        
        status = "✅ 正常" if not diffs else "⚠️ 异常"
        report = (
            f"【每日量化对账报告】\n"
            f"结果: {status}\n"
            f"逻辑现金: {self.db.get_balance():.2f}\n"
            + ("\n".join(diffs) if diffs else "逻辑仓位与柜台完全同步。")
        )
        email_notify(f"对账报告 - {status}", report)
        dingtalk_notify("收盘总结", report)

    def _update_active_order_status(self, order_id, status, dealt_qty):
        """内部方法：维护活跃订单内存状态"""
        with self.lock:
            if order_id in self.active_orders:
                # 终结状态：全部成交、已撤单、已失效
                if status in [ft.OrderStatus.FILLED_ALL, ft.OrderStatus.CANCELLED, ft.OrderStatus.DISABLED]:
                    self.active_orders[order_id]['is_active'] = False

    def close(self):
        """资源释放"""
        self.quote_ctx.close()
        self.trd_ctx.close()
        logger.info("🔒 交易网关已关闭")
