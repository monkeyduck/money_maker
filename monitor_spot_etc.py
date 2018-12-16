# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate
from trade_v3 import buyin_more, buyin_less, ensure_buyin_more, ensure_buyin_less, sell_less_batch, sell_more_batch, ensure_sell_more, ensure_sell_less
from entity import Coin, Indicator, DealEntity
from config_avg import spotAPI
from trade_spot_v3 import spot_buy, spot_sell
import time
import json

import traceback
from collections import deque
import websocket
import codecs
import os

# 默认币种handle_deque
instrument_id = "etc_usdt"
buy_price = 10000
sell_price = 0
amount = 0.1
sell_queue = []
buy_queue = []
first = True
ask_price = 0
bid_price = 0
file_depth = os.getcwd() + '/spot_deal_depth.txt'

def on_message(ws, message):
    global buy_price, sell_price, buy_queue, sell_queue, first, ask_price, bid_price
    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    if 'pong' in message or 'addChannel' in message:
        return
    global write_lines
    jmessage = json.loads(message)
    for each_message in jmessage:
        channel = each_message['channel']
        if channel == 'ok_sub_spot_etc_usdt_depth_5':
            data = each_message['data']
            asks = data['asks'][::-1]
            bids = data['bids']
            ask_price = float(asks[0][0])
            bid_price = float(bids[0][0])
            ask_2_price = float(asks[1][0])
            bid_2_price = float(bids[1][0])
        elif channel == 'ok_sub_spot_etc_usdt_deals':
            for jdata in each_message['data']:
                latest_price = float(jdata[1])
                info = 'latest price: %.4f, %s, ask_price: %.4f, bid_price: %.4f' % (latest_price, jdata[4], ask_price, bid_price)
                print(info)
                with codecs.open(file_depth, 'a+', 'UTF-8') as f:
                    f.writelines(info + '\r\n')


def on_error(ws, error):
    traceback.print_exc()
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    print("websocket connected...")
    ws.send("{'event':'addChannel','channel':'ok_sub_spot_etc_usdt_depth_5'}")
    ws.send("{'event':'addChannel','channel':'ok_sub_spot_etc_usdt_deals'}")



if __name__ == '__main__':

    ws = websocket.WebSocketApp("wss://real.okex.com:10440/websocket/okexapi?compress=true",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    while True:
        ws.run_forever(ping_interval=10, ping_timeout=5)
