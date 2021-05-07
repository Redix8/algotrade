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
import logging.handlers
import pickle
import pprint

from tqdm import tqdm
import pandas as pd
import numpy as np

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

import plotly.graph_objects as go
from plotly.subplots import make_subplots

server_loger = logging.getLogger('werkzeug')
server_loger.disabled = True

logger = logging.getLogger('trading')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(message)s')

sysLogger = logging.getLogger('system')
sysLogger.setLevel(logging.DEBUG)

# log 출력
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# log를 파일에 출력
file_handler = logging.handlers.TimedRotatingFileHandler(filename="log/tradefile", when="midnight", interval=1, encoding="utf-8")
file_handler.setFormatter(formatter)
file_handler.suffix = "%Y%m%d"
logger.addHandler(file_handler)

file_handler_for_sys = logging.handlers.TimedRotatingFileHandler(filename="log/sysfile", when="midnight", interval=1, encoding="utf-8")
file_handler_for_sys.setFormatter(formatter)
file_handler_for_sys.suffix = "%Y%m%d"
sysLogger.addHandler(file_handler_for_sys)

# EXCHANGE API
# [주문 요청]
# 초당 8회, 분당 200회
# [주문 요청 외 API]
# 초당 30회, 분당 900회

# QUOTATION API
# 분당 600회, 초당 10회 (종목, 캔들, 체결, 티커, 호가별)

# static values
MAX_ORDER = 5
START_CASH = 250_000

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

accs = broker.get_accounts()
current_balance = [cname for cname, v in accs.items() if cname not in ["KRW-KRW", "KRW-USDT"] and (v["balance"]*v["avg_buy_price"]+v["locked"]*v["avg_buy_price"]>=5000)]
sum_balance_value = sum([accs.get(cname)['balance']*accs.get(cname)['avg_buy_price'] for cname in current_balance])
broker.set_cash(START_CASH - sum_balance_value if START_CASH>=sum_balance_value else 0)
current_order_used = len(current_balance)
hours_check = [False for _ in range(24)]
minutes_check = [False for _ in range(60)]
# minutes_check[0] = True # 거래가 일어나는 00분은 제외(데이터 갱신이 안될 수 있음)
coin_data = []
buy_orders = []
sell_orders = []
pending_orders = []
sold_orders = []
try:
    with open('tmp/pending', 'rb') as f:
        pending_orders = pickle.load(f)
    if len(pending_orders):
        current_order_used+=len(pending_orders)
except:
    pass

try:
    with open('tmp/sold', 'rb') as f:
        sold_orders = pickle.load(f)    
except:
    pass
print(current_balance)
print(sold_orders)
sysLogger.debug(f'current_balance :{pprint.pformat(current_balance)}')
sysLogger.debug(f'sold_orders :{pprint.pformat(sold_orders)}')

app.layout = html.Div([
    html.H1(children='ALGO Trading'),

    html.Div(children=[
        html.Button('Data Load', id='data_load'),
        dcc.Loading(
            id="loading-1",
            type="default",
            children=html.Div(id="loading-output-1")
        ),
        html.Div([
            html.Div(id="broker_money"),
            dcc.Input(id='broker_money_input', value=0, type='number', min=0, step=5000),
            html.Button('Set', id='set_broker_money')]),
        dcc.Loading(
            id="loading-2",
            type="default",
            children=html.Div(id="loading-output-2")
        ),    
    ]),

    html.Div([
        html.Button('START Trade', id='start_trade'),
        html.Button('STOP', id='stop_trade'), 
        html.Div(id="show_trading_state"),
        dcc.Interval(
            id="trade_interval",
            interval=1000 * 3,
            n_intervals=0,
            disabled=True
        ),
        dcc.Interval(
            id="pendingcheck_interval",
            interval=2300,
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

    html.Label("내 보유 자산"),
    html.Div([
        html.Table([
            html.Thead(
                html.Tr([
                    html.Th('Coin name'),
                    html.Th('volume'),
                    html.Th('매수평균'),
                    html.Th('현재가'),
                    html.Th('등락률'),
                    html.Th('총액')
                ])
            ),
            html.Tbody(id="my_account"),
        ]),        
    ]),

    html.Label("미체결"),
    html.Div([
        html.Table([
            html.Thead(
                html.Tr([
                    html.Th('Coin name'),
                    html.Th('volume'),
                    html.Th('주문가격'),
                    html.Th('총액')
                ])
            ),
            html.Tbody(id="pending_list")
        ]),        
    ]),

    html.Div([
        html.Label("Buy list"),
        html.Div(id="buy_list_table"),
        html.Label("Sell list"),
        html.Div(id="sell_list_table"),
    ], style={"columnCount":2}),

    dcc.Interval(
        id="infomation_interval",
        interval=5000,
        n_intervals=0
    ),
])

@app.callback(
    Output("loading-output-2", "children"),
    Input("set_broker_money", "n_clicks"),
    State("broker_money_input", "value"),    
    prevent_initial_call=True,
)
def set_broker_money(n_clicks, value):
    if n_clicks is None:
        raise PreventUpdate
    global broker
    broker.set_cash(value)

    return

@app.callback(
    Output(component_id='trade_interval', component_property='disabled'),
    Output(component_id='pendingcheck_interval', component_property='disabled'),
    Output("show_trading_state", "children"),
    Input('start_trade', 'n_clicks'), 
    Input('stop_trade', 'n_clicks'),
)
def trade_start_stop(start, stop):
    if start is None:
        return True, True, html.H4("Stoped")
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    if 'start_trade' in changed_id:
        sysLogger.debug('Trading start')
        return False, False, html.H4("Trading")
    elif 'stop_trade' in changed_id:
        sysLogger.debug('Trading stop')
        return True, True, html.H4("Stoped")  

@app.callback(
    Output("my_account", "children"),
    Output("broker_money", "children"),
    Output("buy_list_table", "children"),
    Output("sell_list_table", "children"),
    Input("infomation_interval", "n_intervals")
)
def update_accounts(n):
    global broker
    accs = broker.get_accounts()
    current_balance = [cname for cname, v in accs.items() if cname not in ["KRW-KRW", "KRW-USDT"]]
    tinfo = {}
    if current_balance:
        tinfo = broker.get_current_info(current_balance)    
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
                html.Td(f"{float(acc['balance']) + float(acc['locked']):.2f}"),
            ])
        else:
            item = html.Tr([
                html.Td(cname),
                html.Td(f'{float(acc["balance"]) + float(acc["locked"]):.8f}'),
                html.Td(acc["avg_buy_price"]),
                html.Td(tinfo[cname]),
                html.Td(f'{(float(tinfo[cname])/float(acc["avg_buy_price"])-1)*100:.2f}%'),
                html.Td(f'{float(acc["balance"])*float(tinfo[cname]) + float(acc["locked"])*float(tinfo[cname]):.2f}')
            ])
        rows.append(item)        
    broker_message = f"broker cash: {broker.get_cash():.2f}"
    return rows, broker_message, generate_buy_list(), generate_sell_list()


def generate_buy_list():
    global buy_orders, top50
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
            ]) for i, od in enumerate(buy_orders) if od["coin_name"] in top30big     # 정렬 및 필터
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
    global current_order_used, coin_data
    coin_data = []
    for coin_name in tqdm(top30big):
        coin_data.append(CoinData(coin_name)) 
        time.sleep(0.1)
    
    t = datetime.datetime.now()
    t = t - datetime.timedelta(hours=t.hour%6+6)
    tindex = t.isoformat(sep=" ", timespec="hours")
    buy_orders = []
    sell_orders = []
    buy_list, sell_list = myStrategyM(coin_data)
    current_accounts = broker.get_accounts()
    cash_per_order = 0
    pendinglist = [pending["market"] for pending in pending_orders]    
    if current_order_used<MAX_ORDER:
        cash_per_order = (broker.get_cash() / (MAX_ORDER-current_order_used))
    sysLogger.debug(f'cash_per_order: {cash_per_order} = {broker.get_cash()}/({MAX_ORDER}-{current_order_used})')
    sysLogger.debug(f'pending list : {pprint.pformat(pendinglist)}')
    for coin in buy_list:        
        if coin.coin_name in pendinglist:
            continue
        account = current_accounts.get(coin.coin_name)
        if (not account
            or (account["balance"]*account["avg_buy_price"] < 5000
            and account["locked"]*account["avg_buy_price"] < 5000)):

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
            if account["balance"] > 0: # 현재 코인 있음
                order={
                    "coin": coin,
                    "coin_name": coin.coin_name,
                    "volume": account["balance"],
                    "price" : coin.df.loc[tindex, "trade_price"],
                    "chg": (coin.df.loc[tindex, "trade_price"]/float(account["avg_buy_price"])-1)*100,
                    "reason": coin.df.loc[tindex, "sell_reason"],
                }
                sell_orders.append(order)
    # sysLogger.debug(f'buy_orders : {buy_orders}')
    # sysLogger.debug(f'sell_orders : {sell_orders}')
    return buy_orders, sell_orders

@app.callback(
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

    return None

@app.callback(
    Output("pending_list", "children"),
    Input("pendingcheck_interval", "n_intervals")
)
def check_pending(n):
    # 주문 확인
    global pending_orders, current_order_used
    if n%3==0 and pending_orders:
        uuids = [pending["uuid"] for pending in pending_orders]
        res = broker.orderCheck(uuids, ["done", "cancel"])
        if res:            
            sysLogger.debug(f'pending_orders in check interval-{n}: \n{pprint.pformat(pending_orders)}')
            sysLogger.debug(f'pending_orders check result(done, cancel): \n{pprint.pformat(res)}')
        res = list({ped['uuid']: ped for ped in res}.values())
        c={"bid":"BUY", "ask":"SELL"}
        if res:
            for order in res:
                if order["state"] == "done":                
                    if order["side"] == "ask":
                        current_order_used-=1
                        broker.add_cash(float(order["price"])*float(order["volume"]))
                    elif order["side"] == "bid":
                        broker.sub_cash(float(order["price"])*float(order["volume"]))
                    logger.info(f"{c[order['side']]} order complete - {order['market']}, {order['price']}, {order['volume']}, order used:{current_order_used}, broker_cash: {broker.get_cash()}")
                elif order["state"] == "cancel":                    
                    if order["side"] == "bid":
                        current_order_used-=1
                    logger.info(f"{c[order['side']]} order cancel - {order['market']}, {order['price']}, {order['volume']}, order used:{current_order_used}, broker_cash: {broker.get_cash()}")
        done_or_cancle = set([r['uuid'] for r in res])
        waits_ids = [uuid for uuid in uuids if uuid not in done_or_cancle]
        pending_orders = []
        if waits_ids:
            waits = broker.orderCheck(waits_ids)        
        if waits:
            sysLogger.debug(f'pending_orders check result(wait): \n{pprint.pformat(waits)}')
            pending_orders = waits
        
    rows = []
    for pending in pending_orders:        
        item = html.Tr([
            html.Td(pending['market']),              
            html.Td(pending["volume"]),              
            html.Td(pending["price"]),
            html.Td(float(pending["price"])*float(pending["volume"])),
        ])
        rows.append(item)
    # tmp backup
    with open('tmp/pending', 'wb') as f:
        pickle.dump(pending_orders, f)
    return rows


@app.callback(
    Output("test", "children"),
    Input("trade_interval", "n_intervals"),
    State("trade_interval", "disabled")
)
def doing_trade(n_intervals, disabled):
    if disabled or n_intervals<=0:
        raise PreventUpdate
    global pending_orders, hours_check, minutes_check, current_order_used, buy_orders, sell_orders, sold_orders
    t = datetime.datetime.now()
    hour = t.hour
    minute = t.minute
    pending_added = False

    if ((minute%5 == 0) and not minutes_check[minute]) or n_intervals==1:
        minutes_check = [False for _ in range(60)]
        minutes_check[minute] = True
        total_balance = 0
        accs = broker.get_accounts()
        current_balance = [cname for cname, v in accs.items() if cname not in ["KRW-KRW", "KRW-USDT"]]
        tinfo = {}
        if current_balance:
            for i in range(3):
                tinfo = broker.get_current_info(current_balance)
                tinfo = {c["market"]: c["trade_price"] for c in tinfo}
                if tinfo: break
        if tinfo:
            for k, v in accs.items():
                if k == "KRW-KRW" : total_balance += v["balance"]+v["locked"]
                elif k == "KRW-USDT": continue
                else: total_balance += (v["balance"]*float(tinfo.get(k)) + v["locked"]*float(tinfo.get(k)))
            
        logger.info(f'Current Money : {total_balance}')        
        buy_orders, sell_orders = make_order_list()
        # 6시간에 한번
        if not hours_check[hour] and hour in [0, 6, 12, 18]:
            hours_check = [False for _ in range(24)]
            hours_check[hour] = True
            # 미체결 취소
            sold_orders = []
            sysLogger.debug(f'result of making buy order : \n{pprint.pformat(buy_orders)}')
            sysLogger.debug(f'result of making sell order : \n{pprint.pformat(sell_orders)}')

            for pending in pending_orders:
                if pending["side"] in ["bid", "ask"]:
                    sysLogger.debug(f'cancel_order : {pprint.pformat(pending)}')
                    res = broker.cancel(pending["market"], pending["price"], pending["volume"], pending["uuid"])
                    if res:
                        sysLogger.debug(f'cancel_order_pending add : \n{pprint.pformat(res)}')
                        pending_orders.append(res)
                        pending_added=True

            for order in sell_orders:
                logger.info(f"sell reason: {order['reason']}")
                sysLogger.debug(f'sell_order : {pprint.pformat(order)}')
                res = broker.sell(order["coin_name"], order["price"],  order["volume"])
                if res:
                    sysLogger.debug(f'sell_order_pending add : \n{pprint.pformat(res)}')
                    pending_orders.append(res)
                    pending_added=True
                    sold_orders.append(res["market"])
                    with open('tmp/sold', 'wb') as f:
                        pickle.dump(sold_orders, f)
            time.sleep(6)

        # 5분에 한번 주문 갱신 및 매수주문만 추가갱신.        
        for order in buy_orders:
            if MAX_ORDER - current_order_used<=0:
                continue
            if (order["price"]*order["volume"])<5000:
                continue
            if order["coin_name"] in sold_orders:
                continue
            sysLogger.debug(f'buy_order : \n{pprint.pformat(order)}')
            res = broker.buy(order["coin_name"], order["price"], order["volume"])

            if res:
                sysLogger.debug(f'buy_order_pending add : \n{pprint.pformat(res)}')
                pending_orders.append(res)
                current_order_used+=1
                pending_added=True

    if pending_added:
        sysLogger.debug(f'pending_orders after trading function: \n{pprint.pformat(pending_orders)}')
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
    app.run_server(debug=False)
    