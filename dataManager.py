import pandas as pd
import numpy as np
import requests
import datetime
import logging
from collections import deque

logger = logging.getLogger(())

def calRSI(m_Df, m_N):

    U = np.where(m_Df.diff(1) > 0, m_Df.diff(1), 0)
    D = np.where(m_Df.diff(1) < 0, m_Df.diff(1) *(-1), 0)

    AU = pd.DataFrame(U).rolling( window=m_N, min_periods=m_N).mean()
    AD = pd.DataFrame(D).rolling( window=m_N, min_periods=m_N).mean()
    RSI = AU.div(AD+AU) *100
    return RSI.squeeze().array

def calMFI(high, low, close, vol, period):
    typical = (high + low + close) / 3
    raw = typical * vol
    pos = np.where(typical.diff(1) > 0, raw, 0)
    neg = np.where(typical.diff(1) < 0, raw, 0)
    ratio = pd.DataFrame(pos).rolling(period).sum() / pd.DataFrame(neg).rolling(period).sum()
    mfi = 100-(100/(1+ratio))    
    return mfi

def calStochastic(high, low, close, n=14, k=3, d=3):    
    stochn = (close - low.rolling(n).min()) / (high.rolling(n).max() - low.rolling(n).min())
    stochSlowK = stochn.rolling(3).mean()
    stochSlowD = stochSlowK.rolling(3).mean()
    
    return stochSlowK, stochSlowD

class CoinData:
    def __init__(self, coin_name):
        self.url = "https://api.upbit.com/v1/candles/minutes/60"        
        self.coin_name = coin_name
        self.df = self.loadFromCSV()
        self.dataSync()

        return
    
    def set_trade_price_24H_acc(self, price):
        self.trade_price_24H_acc = price

    def get_trade_price_24H_acc(self, price):
        return self.trade_price_24H_acc

    def loadFromCSV(self):
        try:
            logger.info(f"load {self.coin_name} data.")            
            df = pd.read_csv(f"./coindata/{self.coin_name}.csv")
        except:
            logger.info(f"{self.coin_name} has no data")
            df = None

        return df

    def loadFromServer(self):
        logger.info(f"load {self.coin_name} data from server")
        querystring = {
            "market": self.coin_name,
            "to":"", # 2019-01-01T00:00:00Z
            "count":"200"
        }

        arr = deque()
        response = requests.request("GET", self.url, params=querystring)
        arr.extendleft(response.json())
        
        # querystring["to"] = arr[0]["candle_date_time_utc"] + "Z"        
        # response = requests.request("GET", self.url, params=querystring)
        # arr.extendleft(response.json())

        df = pd.DataFrame(arr)
        df.loc[:,"candle_date_time_kst"] = pd.to_datetime(df["candle_date_time_kst"])
        # tp_acc = df["candle_acc_trade_price"][-25:-1].sum()
        # self.set_trade_price_24H_acc(tp_acc)

        df = df.groupby(pd.Grouper(key="candle_date_time_kst", freq="6H")).agg(     # 6시간
            {
                "opening_price": "first", 
                "high_price": "max", 
                "low_price": "min", 
                "trade_price" : "last", 
                "candle_acc_trade_price": "sum",
                "candle_acc_trade_volume": "sum", 
            }
        ) 

        df = df.drop(df.index[0])
        df['RSI'] = calRSI(df['trade_price'], 14)
        df['MA3'] = df['trade_price'].rolling(3).mean()
        df['MA5'] = df['trade_price'].rolling(5).mean()
        df['MA10'] = df['trade_price'].rolling(10).mean()
        df['MA20'] = df['trade_price'].rolling(20).mean()        
        df['MACD'] = df['trade_price'].ewm(span=12).mean() - df['trade_price'].ewm(span=26).mean()
        df['MACDs'] = df['MACD'].ewm(span=9).mean()
        df['MACDo'] = df['MACD'] - df['MACDs']
        df['MFI'] = calMFI(df['high_price'], df['low_price'], df['trade_price'], df['candle_acc_trade_volume'], 14)
        stochSlowK, stochSlowD = calStochastic(df['high_price'], df['low_price'], df['trade_price'])
        df["stochSlowK"] = stochSlowK
        df["stochSlowD"] = stochSlowD
        
        if len(df)>28:
            df['Momentum'] = df['trade_price'].diff(28)/df['trade_price'][-29]
        else:
            df['Momentum'] = -999
        
        self.last_price = df['trade_price'][-2]

        return df

    def dataSync(self):
        
        if self.df:
            pass
        else:
            self.df = self.loadFromServer()

        return 
    



    

