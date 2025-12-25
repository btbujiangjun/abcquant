import matplotlib.pyplot as plt
from utils.logger import logger

class BacktestEngine:
    def __init__(self, initial_cash=100000, fee=0.001, slippage=0.0):
        self.initial_cash = initial_cash
        self.fee = fee
        self.slippage = slippage

    def run_backtest(self, df, signal_col='signal'):
        cash = self.initial_cash
        position = 0
        equity_curve = []
        positions = []

        for _, row in df.iterrows():
            signal = row[signal_col]
            price = float(row['close'])
            date = row['date']

            if float(signal) == 1 and int(position) == 0:
                buy_price = price * (1+self.slippage)
                position = cash/buy_price
                cash = 0
                logger.info(f"BUY at {buy_price:.2f} in {date}, position={position:.2f}")
            elif float(signal) == -1 and position>0:
                sell_price = price * (1 - self.slippage)
                cash = position * sell_price * (1 - self.fee)
                position = 0
                logger.info(f"SELL at {sell_price:.2f} in {date}, cash={cash:.2f}")

            total_equity = cash + position * price
            equity_curve.append(total_equity)
            positions.append(position)

        df['equity'] = equity_curve
        df['position'] = positions
        return df

    def plot_equity(self, df):
        plt.figure(figsize=(12,6))
        plt.plot(df['date'], df['equity'], label='Equity Curve')
        plt.xlabel('Date')
        plt.ylabel('Equity')
        plt.title('Equity Curve')
        plt.legend()
        plt.grid(True)
        plt.show()
