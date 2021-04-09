# -*- coding: utf-8 -*-

# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

from dataManager import CoinData
from strategy import myStrategyRSI
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
# file_handler = logging.handlers.TimedRotatingFileHandler(filename="logfile", when="midnight", interval=1, encoding="utf-8")
# file_handler.setFormatter(formatter)
# file_handler.suffix = "%Y%m%d"
# logger.addHandler(file_handler)

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
# info = broker.get_current_info(coin_names)
# top30 = sorted(info, key=lambda x:float(x["acc_trade_price_24h"]), reverse=True)[:30]
# reverseAcc = sorted(info, key=lambda x:float(x["acc_trade_price_24h"]))[20:-10] # test?

# Dash 
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)


current_order = 0

coin_data = []
buy_orders = []
sell_orders = []

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
        
    ]),

    # html.Div([
    #     html.Table([
    #         html.Tr([html.Th('Button 1'),
    #                  html.Th('Button 2'),]),
    #         html.Tr([html.Td(btn1 or 0),
    #                  html.Td(btn2 or 0),])
    #     ]),
    #     html.Pre(ctx_msg)
    # ])

])

@app.callback(Output("loading-output-1", "children"), Input("data_load", "n_clicks"))
def load_coin_data(n_clicks):
    if n_clicks is None:
        raise PreventUpdate
    print("Load coin data")
    global coin_data, coin_names, broker, current_order, buy_orders, sell_orders
    coin_data = []
    for coin_name in tqdm(coin_names):
        coin_data.append(CoinData(coin_name)) 
        time.sleep(0.1)

    cash_per_order = (broker.get_cash() / (MAX_ORDER-current_order))
    current_accounts = broker.get_accounts()   

    for coin in coin_data:
        cond_buy, cond_sell = myStrategyRSI(coin)
        coin.df["MarkerBuy"] = np.where(cond_buy, coin.df["low_price"]-coin.df["high_price"].mean()/20, np.nan)
        coin.df["SymbolBuy"] = "triangle-up"
        coin.df["ColorBuy"] = "green"

        coin.df["MarkerSell"] = np.where(cond_sell, coin.df["high_price"]+coin.df["high_price"].mean()/20, np.nan)
        coin.df["SymbolSell"] = "triangle-down"
        coin.df["ColorSell"] = "red"
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
                    }
                    sell_orders.append()
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
    return 

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
            y=df["RSI"],
            name="RSI"
        ), row=2, col=1)

    fig.add_hline(y=65, line_width=1, line_dash="dashdot", line_color="crimson", row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index,
                       y=df.MarkerBuy,
                       mode='markers',
                       name ='buy',
                       marker=go.scatter.Marker(size=10,
                                        symbol=df["SymbolBuy"],
                                        color=df["ColorBuy"])
                       ),row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index,
                       y=df.MarkerSell,
                       mode='markers',
                       name ='sell',
                       marker=go.scatter.Marker(size=10,
                                        symbol=df["SymbolSell"],
                                        color=df["ColorSell"])
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