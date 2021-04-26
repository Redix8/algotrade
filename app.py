# -*- coding: utf-8 -*-

# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

from dataManager import CoinData
from strategy import myStrategyRSI, myStrategyM
from broker import Broker
from collections import deque
import datetime
import time
import logging

from tqdm import tqdm
import pandas as pd
import numpy as np

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate

import plotly.graph_objects as go
from plotly.subplots import make_subplots


logger = logging.getLogger()
logger.setLevel(logging.INFO)
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

# static values
MAX_ORDER = 5
START_CASH = 100_000

# broker init
broker = Broker()
broker.set_cash(START_CASH)
coin_names = broker.get_market_info()
info = broker.get_current_info(coin_names)
# 거래대금 순위
# top30 = sorted(info, key=lambda x:float(x["acc_trade_price_24h"]), reverse=True)[:30]
top50 = sorted(info, key=lambda x:float(x["acc_trade_price_24h"]), reverse=True)[:50]
top50 = {x['market']:x["acc_trade_price_24h"] for x in info}
# 시가총액 순위
top30big = [
     "KRW-BTC"  ,  # 비트코인
     "KRW-ETH"  ,  # 이더리움
     "KRW-XRP"  ,  # 리플
     "KRW-ADA"  ,  # 에이다   
     "KRW-DOT"  ,  # 폴카닷
     "KRW-LTC"  ,  # 라이트코인
     "KRW-LINK" ,  # 체인링크
     "KRW-BCH"  ,  # 비트코인캐시
     "KRW-XLM"  ,  # 스텔라루멘
     "KRW-THETA",  # 세타토큰
     "KRW-TRX"  ,  # 트론
     "KRW-VET"  ,  # 비체인    
     "KRW-BTT"  ,  # 비트토렌트
     "KRW-IOTA" ,  # 아이오타
     "KRW-EOS"  ,  # 이오스
     "KRW-BSV"  ,  # 비트코인에스브이
     "KRW-CRO"  ,  # 크립토닷컴체인
     "KRW-XTZ"  ,  # 테조스
     "KRW-ATOM" ,  # 코스모스
     "KRW-NEO"  ,  # 네오
     "KRW-XEM"  ,  # 넴    
     "KRW-CHZ"  ,  # 칠리즈
     "KRW-ENJ"  ,  # 엔진코인
     "KRW-ETC"  ,  # 이더리움클래식
     "KRW-BAT"  ,  # 베이직어텐션토큰
     "KRW-HBAR" ,  # 헤데라해시그래프
     "KRW-ZIL"  ,  # 질리카
     "KRW-MANA" ,  # 디센트럴랜드
     "KRW-TFUEL",  # 쎄타퓨엘
     "KRW-ICX"  ,  # 아이콘
]
coin_names = top30big
# reverseAcc = sorted(info, key=lambda x:float(x["acc_trade_price_24h"]))[20:-10] # test?

# Dash 
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)


current_order = 0

coin_data = []
buy_orders = []
sell_orders = []
pending_orders = []

app.layout = html.Div([
    html.H1(children='ALGO Trading'),

    html.Div(children=[
        html.Button('Data Load', id='data_load'),
        dcc.Loading(
            id="loading-1",
            type="default",
            children=html.Div(id="loading-output-1")
        ),
    ]),

    html.Div([
        html.Button('START Trade', id='start_trade'),
        html.Button('STOP', id='stop_trade'), 
        html.Div(id="show_trading_state"),
        dcc.Interval(
            id="trade_interval",
            interval=1000 * 2,
            n_intervals=0,
            disabled=True
        ),               
    ]),

    html.Div([
        html.Div(id="test")   
    ]),


    html.Div([        
        html.Label("coins"),
        dcc.Dropdown(
            id='coin_selector',
            options=[{"label": cn, "value": cn} for cn in coin_names],
            value = None
        ),
        dcc.Graph(
            id='coin_chart',            
        )
    ]),

    html.Div([
        html.Button('Buy coins', id='buy_button'),        
        html.Button('Sell coins', id='sell_button'),
    ]),

    html.Div([
        html.Label("Buy list"),
        html.Div(id="buy_list_table"),
        html.Label("Sell list"),
        html.Div(id="sell_list_table"),
    ], style={"columnCount":2}),

    html.Label("내 보유 자산"),
    html.Div([
        html.Table([
            html.Thead(
                html.Tr([
                    html.Th('Coin name'),
                    html.Th('volume'),
                    html.Th('매수평균'),
                    html.Th('현재가'),
                    html.Th('등락률')
                ])
            ),
            html.Tbody(id="my_account"),
            dcc.Interval(
                id="account_interval",
                interval=5000,
                n_intervals=0
            ),
        ]),        
    ]),
])

# @app.callback(
#     Input("buy_button", "n_clicks"),
# )
# def send_buy_request(n):
#     if n_clicks is None:
#         raise PreventUpdate
#     return

# @app.callback(
#     Input("sell_button", "n_clicks"),
# )
# def send_sell_request(n):
#     if n_clicks is None:
#         raise PreventUpdate
#     return

@app.callback(
    Output(component_id='trade_interval', component_property='disabled'),
    Output("show_trading_state", "children"),
    Input('start_trade', 'n_clicks'), 
    Input('stop_trade', 'n_clicks'),
)
def trade_start_stop(start, stop):
    if start is None:
        return True, html.H4("Stoped")
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    if 'start_trade' in changed_id:
        return False, html.H4("Trading")
    elif 'stop_trade' in changed_id:
        return True, html.H4("Stoped")  

@app.callback(
    Output("my_account", "children"),
    Input("account_interval", "n_intervals")
)
def update_accounts(n):
    global broker
    accs = broker.get_accounts()
    current_balance = [cname for cname, v in accs.items() if cname not in ["KRW-KRW", "KRW-USDT"]]
    tinfo = {}
    if current_balance:
        tinfo = broker.get_current_info()    
    tinfo = {c["market"]: c["trade_price"] for c in tinfo}
    rows = []
    for cname, acc in accs.items():
        if cname in ["KRW-KRW", "KRW-USDT"]:
            item = html.Tr([
                html.Td(cname),
                html.Td(acc["balance"]),
                html.Td("-"),
                html.Td("-"),
                html.Td("-"),
            ])
        else:
            item = html.Tr([
                html.Td(cname),
                html.Td(acc["balance"]),
                html.Td(acc["avg_buy_price"]),
                html.Td(tinfo[cname]),
                html.Td(f'{(float(tinfo[cname])/float(acc["avg_buy_price"])-1)*100:.2f}%'),
            ])
        rows.append(item)        

    return rows


def generate_buy_list():
    global buy_orders, top50
    sorted_orders = sorted(buy_orders, key=lambda x : x["coin"].df["Momentum"][-2], reverse=True)
    return html.Table([        
        html.Thead(
            html.Tr([
                html.Th('Coin Name'),
                html.Th('No.'),
                html.Th('Trade Price 24'),
                html.Th('Momentum'),
                html.Th('close')
            ])
        ),
        html.Tbody([
            html.Tr([
                html.Td(od["coin_name"]),
                html.Td(i),
                html.Td(f'{top50.get(od["coin_name"])/100_000_000:,.2f}억원'),
                html.Td(f'{od["coin"].df["Momentum"][-2]:.2f}'),
                html.Td(od['price']),
            ]) for i, od in enumerate(sorted_orders) if od["coin_name"] in top30big     # 정렬 및 필터
        ])
    ])

def generate_sell_list():
    global sell_orders
    return  html.Table([
        html.Thead(
            html.Tr([
                html.Th('Coin Name'),
                html.Th('close'),
                html.Th('volume'),
                html.Th('등락률(%)')
            ])
        ),
        html.Tbody([
            html.Tr([
                html.Td(od["coin_name"]),                
                html.Td(f'{od["price"]}'),
                html.Td(f'{od["volume"]}'),
                html.Td(f'{od["chg"]}')
            ]) for od in sell_orders
        ])
    ])


def make_order_list():
    for coin_name in tqdm(top30big):
        coin_data.append(CoinData(coin_name)) 
        time.sleep(0.1)
    
    buy_orders = []
    sell_orders = []
    buy_list, sell_list = myStrategyM(coin_data)
    current_accounts = broker.get_accounts()
    cash_per_order = (broker.get_cash() / (MAX_ORDER-current_order))
    for coin in buy_list:
        if cash_per_order<5000:
            continue
        account = current_accounts.get(coin.coin_name)
        if (not account
            or account["balance"]*account["avg_buy_price"] < 5000
            and account["locked"]):

            market_info = broker.marketCheck(coin.coin_name)
            if not market_info["market"]["state"] == "active":
                continue

            order_volume = (cash_per_order * (1-float(market_info["bid_fee"])) / coin.last_price)
            order = {
                "coin": coin,
                "coin_name": coin.coin_name,
                "volume": order_volume,
                "price" : coin.last_price,
            }
            buy_orders.append(order)
         
    for coin in sell_list:
        account = current_accounts.get(coin.coin_name)
        if account:
            if account["balance"] > 0 and not account["locked"]: # 현재 코인 있음
                order={
                    "coin": coin,
                    "coin_name": coin.coin_name,
                    "volume": account["balance"],
                    "price" : coin.df["trade_price"][-2],
                    "chg": (coin.df["trade_price"][-2]/float(account["avg_buy_price"])-1)*100
                }
                sell_orders.append(order)
    
    return buy_orders, sell_orders

@app.callback(
    Output("buy_list_table", "children"),
    Output("sell_list_table", "children"),
    Output("loading-output-1", "children"),
    Input("data_load", "n_clicks"),
)
def load_coin_data(n_clicks):
    if n_clicks is None:
        raise PreventUpdate
    logger.info("Load coin data")
    global coin_data, coin_names, broker, current_order, buy_orders, sell_orders, top30big
    coin_data = []
    buy_orders, sell_orders = make_order_list()
                # broker.sell(coin.coin_name, account["balance"], coin.df["trade_price"][-2]) #전일종가에 판매     

    """
    cash_per_order = (broker.get_cash() / (MAX_ORDER-current_order))

    for coin in coin_data:
        cond_buy, cond_sell = myStrategyRSI(coin)
        coin.df["MarkerBuy"] = np.where(cond_buy, coin.df["low_price"]-coin.df["high_price"].mean()/20, np.nan)
        coin.df["MarkerSell"] = np.where(cond_sell, coin.df["high_price"]+coin.df["high_price"].mean()/20, np.nan)

        current_buy = cond_buy[-2]
        current_sell = cond_sell[-2]
        account = current_accounts.get(coin.coin_name)

        if account:
            if account["balance"] > 0 and not account["locked"]: # 현재 코인 있음
                if current_sell and current_buy:
                    continue
                elif current_sell:
                    order={
                        "coin": coin,
                        "coin_name": coin.coin_name,
                        "volume": account["balance"],
                        "price" : coin.df["trade_price"][-2],
                        "chg": (coin.df["trade_price"][-2]/float(account["avg_buy_price"])-1)*100
                    }
                    sell_orders.append(order)
                    # broker.sell(coin.coin_name, account["balance"], coin.df["trade_price"][-2]) #전일종가에 판매           

        else:
            market_info = broker.marketCheck(coin.coin_name)
            if not market_info["market"]["state"] == "active":
                continue
            if cash_per_order<5000:
                continue

            if current_buy:
                order_volume = (cash_per_order * (1-float(market_info["bid_fee"])) / coin.last_price)
                order = {
                    "coin": coin,
                    "coin_name": coin.coin_name,
                    "volume": order_volume,
                    "price" : coin.last_price,
                }
                buy_orders.append(order)
    """
    return generate_buy_list(), generate_sell_list(), None

@app.callback(
    Output("test", "children"),
    Input("trade_interval", "n_intervals")
)
def doing_trade(n):
    if n <= 0:
        raise PreventUpdate
    global pending_orders
    buy_orders, sell_orders = make_order_list()
    
    # 취소    
    for pending in pending_orders:
        if pending["side"] in ["bid", "ask"]:
            res = broker.cancel(pending["market"], pending["price"], pending["volume"], pending["uuid"])
            pending_orders.append(res)    
    
    # 주문 확인
    if pending_orders:
        uuids = [pending["uuid"] for pending in pending_orders]
        res = broker.orderCheck(uuids)
        left = []
        c={"bid":"BUY", "ask":"SELL"}
        for order in res:
            if order["state"] == "done":
                logger.info(f"{c[order['side']]} order complete - {order['market']}, {order['price']}, {order['volume']}" )
            elif order["state"] == "cancel":
                logger.info(f"{c[order['side']]} order cancel - {order['market']}, {order['price']}, {order['volume']}")
            else:
                left.append(order)
        pending_orders = left



    for order in sell_orders:
        res = broker.sell(order["coin_name"], order["price"].  order["volume"])
        pending_orders.append(res)

    for order in buy_orders:
        res = broker.buy(order["coin_name"], order["price"], order["volume"])
        pending_orders.append(res)



    return html.H4(datetime.datetime.now().strftime("%Y/%m/%d - %H:%M:%S"))

    

@app.callback(Output("coin_chart", "figure"), Input("coin_selector", "value"))
def update_graph(coin_name):
    if coin_name is None:
        raise PreventUpdate
    global coin_data
    df = [coin.df for coin in coin_data if coin.coin_name == coin_name][0]

    fig = make_subplots(rows=2, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.02,
                    row_heights=[0.8, 0.2])


    fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['opening_price'],
            high=df['high_price'],
            low=df['low_price'],
            close=df['trade_price'],
            name="price"
        ), row=1, col=1)

    fig.add_trace(go.Scatter(
            x=df.index,
            y=df["MA20"], 
            name="MA20"
        ), row=1, col=1)

    fig.add_trace(go.Scatter(
            x=df.index,
            y=df["MFI"],
            name="MFI"
        ), row=2, col=1)

    fig.add_hline(y=65, line_width=1, line_dash="dashdot", line_color="crimson", row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index,
                       y=df.MarkerBuy,
                       mode='markers',
                       name ='buy',
                       marker=go.scatter.Marker(size=10,
                                        symbol="triangle-up",
                                        color="green")
                       ),row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index,
                       y=df.MarkerSell,
                       mode='markers',
                       name ='sell',
                       marker=go.scatter.Marker(size=10,
                                        symbol="triangle-down",
                                        color="red")
                       ),row=1, col=1)

    fig.update_layout(xaxis_rangeslider_visible=False)
    fig.update_layout(
        title={
            'text': coin_name,
            'y':0.9,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top'})
    fig.update_yaxes(range=[0, 100], row=2, col=1)
    fig.update_layout(hovermode="x unified")

    return fig


if __name__ == '__main__':
    app.run_server(debug=True)