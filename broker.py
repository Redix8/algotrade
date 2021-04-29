import os
import jwt
import uuid
import hashlib
import time
from urllib.parse import urlencode

import requests
import logging

logger = logging.getLogger(())

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

    def add_cash(self, cash_amount):
        self.cash += cash_amount

    def sub_cash(self, cash_amount):
        self.cash -= cash_amount

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
            logger.error(f"{e['error']['name']} : {e['error']['message']}" )
            return
            
        return accounts

    def get_current_info(self, coin_names):
        url = "https://api.upbit.com/v1/ticker"
        querystring = {"markets":",".join(coin_names)}
        response = requests.request("GET", url, params=querystring)
        
        if res.status_code == 201:            
            return response.json()
        else:
            e = response.json()
            logger.error(f"{e['error']['name']} : {e['error']['message']}" )
        return 

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

        while True:
            res = requests.post(self.server_url + "/v1/orders", params=query, headers=headers)

            if res.status_code == 201:
                logger.info(f'BUY order - {coin_name}, price: {price}, volume: {volume}')
                return res.json()
            else:
                e = res.json()
                logger.error(f'BUY order error - {coin_name}, price: {price}, volume: {volume}')
                logger.error(f"{e['error']['name']} : {e['error']['message']}" )
                if e['error']['name'] == "too_many_request_order":
                    time.sleep(0.1)
                    continue
                return

        return 
    
    def sell(self, coin_name, price, volume):
        query = {
            'market': coin_name,
            'side': 'ask',
            'volume': str(volume),
            'price': str(price),
            'ord_type': 'limit',
        }
        headers = get_headers(query=query)
        
        while True:
            res = requests.post(self.server_url + "/v1/orders", params=query, headers=headers)

            if res.status_code == 201:
                logger.info(f'SELL order - {coin_name}, price: {price}, volume: {volume}')
                return res.json()
            else:
                e = res.json()
                logger.error(f'SELL order error - {coin_name}, price: {price}, volume: {volume}')
                logger.error(f"{e['error']['name']} : {e['error']['message']}" )
                if e['error']['name'] == "too_many_request_order":
                    time.sleep(0.1)
                    continue
                return
        return

    def cancel(self, coin_name, price, volume, uuid):
        query = {
            'uuid': uuid,
        }
        headers = get_headers(query=query)
        while True:
            res = requests.delete(self.server_url + "/v1/order", params=query, headers=headers)

            if res.status_code == 200:
                logger.info(f'CANCEL order - {coin_name}, price: {price}, volume: {volume}')
                return res.json()
            else:
                e = res.json()
                logger.error(f'CANCEL order error - {coin_name}, price: {price}, volume: {volume}')
                logger.error(f"{e['error']['name']} : {e['error']['message']}" )
                if e['error']['name'] == "too_many_request_order":
                    time.sleep(0.1)
                    continue
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
            logger.error(f"{e['error']['name']} : {e['error']['message']}" )

        return 

    '''
    state: wait(체결대가), watch(예약주문 대기), done(전체 체결 완료), cancel(주문 취소)
    '''
    def orderCheck(self, uuids, states=["wait"]):        
        query = {
            'states[]': states,
            'uuids[]': uuids,   
        }
        states_query_string = '&'.join(["states[]={}".format(state) for state in states])
        uuids_query_string = '&'.join(["uuids[]={}".format(uuid) for uuid in uuids])

        query_string = "{0}&{1}".format(states_query_string, uuids_query_string).encode()

        m = hashlib.sha512()
        m.update(query_string)
        query_hash = m.hexdigest()

        payload = {
            'access_key': access_key,
            'nonce': str(uuid.uuid4()),
            'query_hash': query_hash,
            'query_hash_alg': 'SHA512',
        }

        jwt_token = jwt.encode(payload, secret_key)
        authorize_token = 'Bearer {}'.format(jwt_token)
        headers = {"Authorization": authorize_token}

        res = requests.get(self.server_url + "/v1/orders", params=query, headers=headers)
        if res.status_code == 200:
            return res.json()
        else:
            e = res.json()
            logger.error(f"{e['error']['name']} : {e['error']['message']}" )

        return 





    
    


