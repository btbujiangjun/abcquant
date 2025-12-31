import pandas as pd
from utils.logger import logger
from core.interval import INTERVAL

OHLC_FIELD = ['date', 'open', 'high', 'low', 'close', 'volume']

class OHLCData:
    def __init__(self, data: pd.DataFrame, interval: str = 'daily'):
        missing_fields = [f for f in OHLC_FIELD if f not in data.columns]
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            raise ValueError(f"{missing_fields} are required")
        
        if interval not in INTERVAL:
            raise ValueError(f"Invalid interval {interval}, choose from {INTERVAL}")

        self.logic = {
            'open': 'first', 'high': 'max', 'low': 'min',
            'close': 'last', 'volume': 'sum'
        }
        if "amount" in data.columns:
            self.logic["amount"] = "sum"
        elif "volume" in data.columns and "close" in data.columns:
            data = data.assign(amount=data['close'] * data['volume'])
            self.logic["amount"] = "sum"

        self.data, self.interval = data, interval

    def pct_change(self, percentage:bool=True, calc_column:str="close") -> pd.DataFrame:
        assert all(column in self.data.columns for column in [calc_column, 'date']), \
            f"Column ['date', {calc_column}] are required."
        column = "pct_change"
        if column not in self.data.columns:
            self.data['date'] = pd.to_datetime(self.data['date'])
            self.data = self.data.sort_values(by='date', ascending=False)
            self.data[column] = self.data['close'].ffill().pct_change(periods=-1)
            if percentage:
                self.data[column] = self.data['close'].pct_change(periods=-1).apply(
                    lambda x: f"{x*100:.2f}%" if pd.notnull(x) else "0.00%"
                )
            else:
                self.data[column] = self.data['close'].ffill().pct_change().round(2)
            self.data["date"] = self.data["date"].dt.strftime('%Y-%m-%d')
        return self.data

    def daily_week(self) -> pd.DataFrame:
        if self.interval != "daily":
            raise ValueError(f"Only daily data can be resampled to weekly, got {self.interval}")

        df = self.data.copy()
        has_symbol = "symbol" in df.columns
        if not has_symbol:
            df["symbol"] = "DEFAULT"

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df['date'])
        
        df_week = (df.groupby("symbol")
                   .resample('W-MON', closed='left', label='left')
                   .agg(self.logic)
                   .reset_index())

        all_cols = self.data.columns
        for col in all_cols:
            if col not in df_week.columns:
                mapping = df.groupby("symbol")[col].first()
                df_week[col] = df_week["symbol"].map(mapping)

        df_week["date"] = df_week['date'].dt.strftime('%Y-%m-%d')
        
        if not has_symbol:
            df_week.drop(columns=["symbol"], inplace=True)
            
        return df_week

"""
import pandas as pd
from utils.logger import logger
from core.interval import INTERVAL

OHLC_FIELD = ['date', 'open', 'high', 'low', 'close', 'volume']
OHLC_FIELD_FULL = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']

class OHLCData:
    def __init__(self, data:pd.DataFrame, interval:str='daily'):
        assert len(data) > 0, \
            "No ohlc data"
        for field in OHLC_FIELD:
            if field not in data.columns:
                print(f"no field:{field}")
        assert all([field in data.columns for field in OHLC_FIELD]), \
            f"{OHLC_FIELD} are required"        
        assert interval in INTERVAL, \
            f"Invalid interval {interval}, choose from {INTERVAL}"
        self.logic = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
        }
        if "amount" in data.columns:
            self.logic["amount"] = "sum"

        self.data, self.interval = data, interval

    def daily_week(self):
        assert self.interval == "daily" or "daily" in self.data.columns, \
            "Only support `daily` data, but it's {self.interval}"

        df_day = self.data.copy()
        has_symbol = True if "symbol" in df_day.columns else False
        if not has_symbol:
            df_day["symbol"] = "DEFAULT"

        if not isinstance(df_day.index, pd.DatetimeIndex):
            df_day["date"] = pd.to_datetime(df_day["date"])
            df_day.set_index("date", inplace=True, drop=False)
        df_day.set_index("symbol", append=True, inplace=True, drop=False)
        df_day = df_day.reorder_levels(['symbol', 'date']).sort_index()

        history_df_week = df_day.groupby(level=0).resample('W-MON', level=1, closed='left', label='left').agg(self.logic)
 
        last_day = df_day.iloc[-1]['date']
        last_monday = last_day - pd.Timedelta(days=last_day.weekday())

        complete_df_weekly = history_df_week.loc[(slice(None), slice(None, last_monday - pd.Timedelta(seconds=1))), :]
       
        incomplete_slice = df_day.loc[(slice(None), slice(last_monday, last_day)), :]
        if not incomplete_slice.empty:
            current_df_weekly = incomplete_slice.groupby(level=0).agg(self.logic)
            current_df_weekly["date"] = last_monday
            current_df_weekly.set_index('date', append=True, inplace=True)
            df_week = pd.concat([complete_df_weekly, current_df_weekly]).sort_index()
        else:
            df_week = complete_df_weekly
        
        if not has_symbol:
            df_week = df_week.reset_index(level=0, drop=True)
        else:        
            df_week = df_week.reset_index()
        
        drop_cols = []
        for col in self.data.columns:
            if col not in df_week.columns:
                unique_values = self.data[col].unique()
                if len(unique_values) == 1:
                    df_week[col] = unique_values[0]
                else:
                    drop_cols.append(col)
        if len(drop_cols) > 0:
            logger.warning(f"daily_week drop columns:{drop_cols}")
        df_week["date"] = df_week['date'].dt.strftime('%Y-%m-%d')
    
        return df_week
"""
