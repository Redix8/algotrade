import os
import jwt
import uuid
import hashlib
from urllib.parse import urlencode

import requests


access_key = os.environ['UPBIT_OPEN_API_ACCESS_KEY']
secret_key = os.environ['UPBIT_OPEN_API_SECRET_KEY']


def cal_order_price(price):
    if price >= 2_000_000:   return 1000 * (price//1000) 
    elif price >= 1_000_000: return 500  * (price//500) 
    elif price >= 500_000  : return 100  * (price//100) 
    elif price >= 100_000  : return 50   * (price//50)	
    elif price >= 10_000   : return 10   * (price//10)	
    elif price >= 1_000	   : return 5    * (price//5)   
    elif price >= 100	   : return 1    * (price//1)   
    elif price >= 10	   : return 0.1  * (price//0.1) 
    elif price >= 0		   : return 0.01 * (price//0.01)


def get_headers(query=None):
    payload = {
        'access_key': access_key,
        'nonce': str(uuid.uuid4()),
    }

    if query:
        query_string = urlencode(query).encode()
        m = hashlib.sha512()
        m.update(query_string)
        query_hash = m.hexdigest()
        payload['query_hash'] = query_hash
        payload['query_hash_alg'] = 'SHA512'

    jwt_token = jwt.encode(payload, secret_key)
    authorize_token = 'Bearer {}'.format(jwt_token)
    headers = {"Authorization": authorize_token}

    return headers


class Broker:
    def __init__(self, cash_amount=0):
        self.server_url = "https://api.upbit.com"
        self.cash = cash_amount
        
        return

    def get_market_info(self):        
        querystring = {"isDetails":"false"}

        res = requests.request("GET", self.server_url + "/v1/market/all", params=querystring)
        coins = []
        for coin in res.json():
            if "KRW" in coin["market"]:
                coins.append(coin["market"])

        return coins
    
    def set_cash(self, cash_amount):
        self.cash = cash_amount
    
    def get_cash(self):
        return self.cash

    def get_accounts(self):
        headers = get_headers()
        res = requests.get(self.server_url + "/v1/accounts", headers=headers)
        accounts = dict()
        if res.status_code == 200:
            for unit in res.json():
                accounts[f"{unit['unit_currency']}-{unit['currency']}"] = {
                    "balance" : float(unit["balance"]),
                    "locked" : float(unit["locked"]),
                    "avg_buy_price" : float(unit["avg_buy_price"]),
                }
        else:
            e = res.json()
            print(f"{e['error']['name']} : {e['error']['message']}" )
            return
            
        return accounts

    def get_current_info(self, coin_names):
        url = "https://api.upbit.com/v1/ticker"
        querystring = {"markets":",".join(coin_names)}
        response = requests.request("GET", url, params=querystring)
        return response.json()

    # def get_cash_from_server(self):
        
    #     headers = get_headers()

    #     res = requests.get(self.server_url + "/v1/accounts", headers=headers)
    #     if res.status_code == 200:
    #         for account in res.json():
    #             if account["currency"] == "KRW":
    #                 if float(account["balance"]) > 0:
    #                     return 
    #                 else:
    #                     return 0
    #     else:
    #         e = res.json()
    #         print(f"{e['error']['name']} : {e['error']['message']}" )
            
    #     return

    def buy(self, coin_name, price, volume):
        query = {
            'market': coin_name,
            'side': 'bid',
            'volume': str(volume),
            'price': str(price),
            'ord_type': 'limit',
        }
        headers = get_headers(query=query)

        res = requests.post(self.server_url + "/v1/orders", params=query, headers=headers)

        if res.status_code == 200:
            return res.json()
        else:
            e = res.json()
            print(f"{e['error']['name']} : {e['error']['message']}" )

        return 
    
    def sell(self, coin_name, volume, price):
        query = {
            'market': coin_name,
            'side': 'ask',
            'volume': str(volume),
            'price': str(price),
            'ord_type': 'limit',
        }
        headers = get_headers(query=query)

        res = requests.post(self.server_url + "/v1/orders", params=query, headers=headers)

        if res.status_code == 200:
            return res.json()
        else:
            e = res.json()
            print(f"{e['error']['name']} : {e['error']['message']}" )

        return

    def marketCheck(self, coin_name):
        query = {
            'market': coin_name,
        }
        headers = get_headers(query=query)
        res = requests.get(self.server_url + "/v1/orders/chance", params=query, headers=headers)

        if res.status_code == 200:
            return res.json()
        else:
            e = res.json()
            print(f"{e['error']['name']} : {e['error']['message']}" )

        return 




    
    


