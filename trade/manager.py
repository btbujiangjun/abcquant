import time
import futu as ft

class OrderManager:
    def __init__(self, gateway, config):
        self.gateway = gateway
        self.cfg = config
        self.active_orders = {} # {order_id: info}

    def execute_signal(self, symbol, signal):
        side = ft.TrdSide.BUY if signal == 1 else ft.TrdSide.SELL
        order_id = self.gateway.place_order(symbol, 10, side=side)
        if order_id:
            self.active_orders[order_id] = {"code": symbol, "time": time.time(), "side": side}
            print(f"订单已提交: {order_id}")

    def monitor_and_cleanup(self):
        """检查超时未成交订单"""
        now = time.time()
        for oid, info in list(self.active_orders.items()):
            if now - info['time'] > self.cfg.ORDER_TIMEOUT:
                print(f"撤销超时订单: {oid}")
                self.gateway.ctx.order_operator(ft.OrderOp.CANCEL, order_id=oid)
                del self.active_orders[oid]
