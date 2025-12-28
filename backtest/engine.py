import matplotlib.pyplot as plt
from utils.logger import logger

class BacktestEngine:
    def __init__(self, initial_cash=100000, fee=0.001, slippage=0.0):
        self.initial_cash = initial_cash
        self.fee = fee
        self.slippage = slippage

    def run_backtest(self, df, signal_col='signal'):
        cash, position, positions, equity_curve, ops = self.initial_cash, 0, [], [], []
        for _, row in df.iterrows():
            signal, price, date = row[signal_col], float(row['close']), row['date'] 
            if float(signal) == 1 and int(position) == 0:
                buy_price = price * (1 + self.slippage)
                position, cash = cash/buy_price, 0
                ops.append("BUY")
            elif float(signal) == -1 and position>0:
                sell_price = price * (1 - self.slippage)
                cash, position = position * sell_price * (1 - self.fee), 0
                ops.append("SELL")
            else:
                ops.append("HOLD")

            total_equity = cash + position * price
            equity_curve.append(total_equity)
            positions.append(position)

        df['ops'] = ops
        df['equity'] = equity_curve
        df['position'] = positions
        return df

    def plot_equity(self, df, symbol:str):
        title = f"{symbol} backtest result"
        plt.figure(figsize=(12,6))
        plt.plot(df['date'], df['equity'], label=title)
        plt.xlabel('Date')
        plt.ylabel('Equity')
        plt.title(title)
        plt.legend()
        plt.grid(True)
        plt.show()
