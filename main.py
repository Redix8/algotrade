from dataManager import CoinData
from strategy import myStrategyRSI
from broker import Broker
from collections import deque
import datetime
import time
from tqdm import tqdm
import logging

# 로그 생성
logger = logging.getLogger()

# 로그의 출력 기준 설정
logger.setLevel(logging.INFO)

# log 출력 형식
formatter = logging.Formatter('%(asctime)s - %(message)s')

# log 출력
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# log를 파일에 출력
file_handler = logging.handlers.TimedRotatingFileHandler(filename="logfile", when="midnight", interval=1, encoding="utf-8")
file_handler.setFormatter(formatter)
file_handler.suffix = "%Y%m%d"
logger.addHandler(file_handler)

# EXCHANGE API
# [주문 요청]
# 초당 8회, 분당 200회

# [주문 요청 외 API]
# 초당 30회, 분당 900회


# QUOTATION API
# 분당 600회, 초당 10회 (종목, 캔들, 체결, 티커, 호가별)

# (cash / price)

MAX_ORDER = 5
START_CASH = 100_000

if __name__ == '__main__':
    broker = Broker()
    broker.set_cash(START_CASH)
    coin_names = broker.get_market_info()
    current_order = 0
    
    info = broker.get_current_info(coin_names)
    top30 = sorted(info, key=lambda x:float(x["acc_trade_price_24h"]), reverse=True)[:30]
    # reverseAcc = sorted(info, key=lambda x:float(x["acc_trade_price_24h"]))[20:-10] # test?

    print("Load coin data")
    coin_data = []
    for coin_name in tqdm(coin_names):
        coin_data.append(CoinData(coin_name)) 
        time.sleep(0.1)

    cash_per_order = (broker.get_cash() / (MAX_ORDER-current_order))

    current_accounts = broker.get_accounts()    
    
    buy_orders = []
    for coin in coin_data:
        cond_buy, cond_sell = myStrategyRSI(coin)
        account = current_accounts.get(coin.coin_name)
        if account:
            if account["balance"] > 0 and not account["locked"]: # 현재 코인 있음
                if cond_sell and cond_buy:
                    continue
                elif cond_sell:
                    broker.sell(coin.coin_name, account["balance"], coin.df["trade_price"][-2]) #전일종가에 판매           

        else:
            market_info = broker.marketCheck(coin.coin_name)
            if not market_info["market"]["state"] == "active":
                continue
            if cash_per_order<5000:
                continue

            if cond_buy:
                order_volume = (cash_per_order * (1-market_info["bid_fee"]) / coin.last_price)
                order = {
                    "coin": coin,
                    "coin_name": coin.coin_name,
                    "volume": order_volume,
                    "price" : coin.last_price,
                }
                buy_orders.append(order)
        
          









    

    










