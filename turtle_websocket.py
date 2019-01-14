# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate
from trade_v3 import buyin_more, buyin_less, ensure_buyin_more, ensure_buyin_less, sell_less_batch, sell_more_batch, ensure_sell_more, ensure_sell_less
from entity import Coin, Indicator, DealEntity
from config_strict import futureAPI, vol_1m_line, vol_3s_line, vol_1m_bal, vol_3s_bal, incr_5m_rate, incr_1m_rate, incr_10s_rate
import time
import json
from turtle import Turtle

import traceback
from collections import deque
import websocket
import codecs

# 默认币种handle_deque
coin = Coin("etc", "usdt")
time_type = "ETC-USD-190329"
turtle = Turtle(coin.name, time_type)
time_flag_1s = 0
time_flag_1min = 0

file_transaction, file_deal = coin.gen_future_file_name()

deque_min = deque()
deque_10s = deque()
deque_3s = deque()
deque_5m = deque()
ind_1min = Indicator(60)
ind_10s = Indicator(10)
ind_3s = Indicator(3)
ind_5m = Indicator(300)



def handle_deque(deq, entity, ts, ind):
    price_sum = 0.0
    price_num = 0
    while len(deq) > 0:
        left = deq.popleft()
        price_sum += left.price
        price_num += 1
        if float(left.time + ind.interval) > float(ts):
            deq.appendleft(left)
            break
        ind.minus_vol(left)
        ind.minus_price(left)
    deq.append(entity)
    ind.add_price(entity)
    ind.add_vol(entity)
    return (round(price_sum / price_num, 4) if price_num > 0 else 0.0)




def on_message(ws, message):
    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    if 'pong' in message or 'addChannel' in message:
        return
    global deque_3s, deque_10s, deque_min, \
        deque_5m, ind_3s, ind_10s, ind_1min, ind_5m, time_flag_1min, time_flag_1s
    jmessage = json.loads(message)

    ts = time.time()

    if int(ts) - int(time_flag_1min) >= 60:
        time_flag_1min = int(ts)
        turtle.calc_unit()

    if int(ts) - int(time_flag_1s) >= 1:
        time_flag_1s = int(ts)
        turtle.build_position()
        turtle.add_position()

    for each_message in jmessage:
        for jdata in each_message['data']:
            latest_price = float(jdata[1])
            deal_entity = DealEntity(jdata[0], float(jdata[1]), round(float(jdata[2]), 3), ts, jdata[4])

            handle_deque(deque_3s, deal_entity, ts, ind_3s)
            handle_deque(deque_10s, deal_entity, ts, ind_10s)
            handle_deque(deque_min, deal_entity, ts, ind_1min)
            price_5m_ago = handle_deque(deque_5m, deal_entity, ts, ind_5m)






def on_error(ws, error):
    traceback.print_exc()
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    print("websocket connected...")
    ws.send("{'event':'addChannel','channel':'ok_sub_futureusd_%s_trade_quarter'}" % coin.name)


if __name__ == '__main__':
    ws = websocket.WebSocketApp("wss://real.okex.com:10440/websocket/okexapi?compress=true",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    while True:
        ws.run_forever(ping_interval=20, ping_timeout=10)
        print("write left lines into file...")
        with codecs.open(file_deal, 'a+', 'UTF-8') as f:
            f.writelines(write_lines)
            write_lines = []