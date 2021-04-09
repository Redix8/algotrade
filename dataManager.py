import pandas as pd
import numpy as np
import requests
import datetime
from collections import deque

def calRSI(m_Df, m_N):

    U = np.where(m_Df.diff(1) > 0, m_Df.diff(1), 0)
    D = np.where(m_Df.diff(1) < 0, m_Df.diff(1) *(-1), 0)

    AU = pd.DataFrame(U).rolling( window=m_N, min_periods=m_N).mean()
    AD = pd.DataFrame(D).rolling( window=m_N, min_periods=m_N).mean()
    RSI = AU.div(AD+AU) *100
    return RSI.squeeze().array


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
            print(f"load {self.coin_name} data.")
            df = pd.read_csv(f"./coindata/{self.coin_name}.csv")
        except:
            print(f"{self.coin_name} has no data")
            df = None

        return df

    def loadFromServer(self):
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
        df['rsiMA3'] = df['RSI'].rolling(3).mean()

        return df

    def dataSync(self):
        
        if self.df:
            pass
        else:
            self.df = self.loadFromServer()

        return 
    



    

