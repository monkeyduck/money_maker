#!/usr/bin/python
# -*- coding: UTF-8 -*-

import websocket
import codecs
try:
    import thread
except ImportError:
    import _thread as thread
from collections import deque
from trade import *
import os
import traceback


class Coin:
    def __init__(self, name, refer):
        self.name = name
        self.refer = refer

    def gen_file_name(self):
        file_path = os.getcwd()
        transaction = file_path + '/' + self.name + '_transaction.txt'
        deal = file_path + '/' + self.name + '_deals.txt'
        return transaction, deal

    def gen_full_name(self):
        return self.name + "_" + self.refer


class dealEntity:
    def __init__(self, _id, _price, _amount, _time, _type):
        self.id = _id
        self.price = _price
        self.amount = _amount
        self.time = _time
        self.type = _type

    def detail(self):
        if self.type == 'ask':
            category = 'sell '
        else:
            category = 'buy  '
        return str(self.time) + ': ' + category + str(self.amount) + '\t at price: ' + str(self.price)


class indicator:
    def __init__(self, interval):
        self.interval = interval
        self.vol = 0
        self.avg_price = 0
        self.price = 0
        self.price_num = 0
        self.bid_vol = 0
        self.ask_vol = 0

    def cal_avg_price(self):
        if self.price_num != 0:
            return round(float(self.price) / float(self.price_num), 4)
        else:
            return 0

    def add_vol(self, deal_entity):
        self.vol += deal_entity.amount
        if deal_entity.type == 'ask':
            self.ask_vol += deal_entity.amount
        elif deal_entity.type == 'bid':
            self.bid_vol += deal_entity.amount

    def minus_vol(self, deal_entity):
        self.vol -= deal_entity.amount
        if deal_entity.type == 'ask':
            self.ask_vol -= deal_entity.amount
        elif deal_entity.type == 'bid':
            self.bid_vol -= deal_entity.amount

    def add_price(self, deal_entity):
        self.price_num += 1
        self.price += deal_entity.price

    def minus_price(self, deal_entity):
        self.price_num -= 1
        self.price -= deal_entity.price


# 默认币种
coin = Coin("eos", "usdt")
file_transaction, file_deal = coin.gen_file_name()

deque_min = deque()
deque_10s = deque()
deque_3s = deque()
deque_5m = deque()
latest_price = 0
ind_1min = indicator(60)
ind_10s = indicator(10)
ind_3s = indicator(3)
ind_5m = indicator(300)
more = 0
less = 0
last_avg_price = 0
buy_price = 0
last_last_price = 0
incr_5m_rate = 0.6
incr_1m_rate = 0.3
time_type = "this_week"
write_lines = []
avg_min_vol = 10000


def connect():
    ws = websocket.WebSocket()
    ws_address = "wss://real.okex.com"
    ws_port = 10441
    ws.connect(ws_address, http_proxy_host="websocket", http_proxy_port=ws_port)


def handle_deque(deq, entity, ts, ind):
    while len(deq) > 0:
        left = deq.popleft()
        if float(left.time + ind.interval) > float(ts):
            deq.appendleft(left)
            break
        ind.minus_vol(left)
        ind.minus_price(left)
    deq.append(entity)
    ind.add_price(entity)
    ind.add_vol(entity)


def cal_rate(cur_price, last_price):
    return round((cur_price - last_price) / last_price, 4) * 100


def on_message(ws, message):
    if 'pong' in message or 'addChannel' in message:
        print(message)
        return
    global latest_price, last_avg_price, buy_price, last_last_price, more, less, deque_3s, deque_10s, deque_min, \
        deque_5m, ind_3s, ind_10s, ind_1min, ind_5m, write_lines
    jmessage = json.loads(message)
    ts = time.time()
    now_time = timestamp2string(ts)

    jdata = jmessage[0]['data'][0]
    latest_price = float(jdata[1])
    deal_entity = dealEntity(jdata[0], float(jdata[1]), round(float(jdata[2]), 3), ts, jdata[4])

    handle_deque(deque_3s, deal_entity, ts, ind_3s)
    handle_deque(deque_10s, deal_entity, ts, ind_10s)
    handle_deque(deque_min, deal_entity, ts, ind_1min)
    handle_deque(deque_5m, deal_entity, ts, ind_5m)

    avg_3s_price = ind_3s.cal_avg_price()
    avg_10s_price = ind_10s.cal_avg_price()
    avg_min_price = ind_1min.cal_avg_price()
    avg_5m_price = ind_5m.cal_avg_price()
    price_10s_change = cal_rate(avg_3s_price, avg_10s_price)
    price_1m_change = cal_rate(avg_3s_price, avg_min_price)
    price_5m_change = cal_rate(avg_3s_price, avg_5m_price)

    if more == 1:
        if avg_10s_price <= 1.001 * avg_5m_price or (0.3 * ind_3s.ask_vol > ind_3s.bid_vol > 3000):
            # 按买一价出售
            if sell_more(coin.name, time_type):
                sell_price = latest_price
                info = u'发出卖出信号！！！卖出价格：' + str(sell_price) + u', 收益: ' + str(sell_price - buy_price) \
                       + ', ' + now_time
                print (info)
                with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                    f.writelines(info + '\n')
                more = 0
    elif less == 1:
        if avg_10s_price >= 0.999 * avg_5m_price:
            if sell_less(coin.name, time_type):
                sell_price = latest_price
                info = u'发出卖出信号！！！卖出价格：' + str(sell_price) + u', 收益: ' + str(buy_price - sell_price) \
                       + ', ' + now_time
                print (info)
                with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                    f.writelines(info + '\n')
                less = 0
    elif check_vol():
        if latest_price > avg_3s_price >= avg_10s_price > last_avg_price > last_last_price > avg_min_price > avg_5m_price \
                and (price_5m_change > incr_5m_rate and price_1m_change > incr_1m_rate and price_10s_change >= 0) \
                and ind_1min.bid_vol > float(1.5 * ind_1min.ask_vol) and ind_3s.bid_vol > float(2 * ind_3s.ask_vol):
            if buyin_more_batch(coin.name, time_type, latest_price):
                more = 1
                buy_price = latest_price
                info = u'发出做多信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                    f.writelines(info + '\n')

        elif latest_price < avg_3s_price < avg_10s_price < last_avg_price < last_last_price < avg_min_price < avg_5m_price \
                and (price_5m_change < -1 * incr_5m_rate and price_1m_change < -1 * incr_1m_rate and price_10s_change <= 0) \
                and ind_1min.ask_vol > float(1.5 * ind_1min.bid_vol) and ind_3s.ask_vol > float(2 * ind_3s.bid_vol):
            if buyin_less_batch(coin.name, time_type, latest_price):
                buy_price = latest_price
                info = u'发出做空信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                    f.writelines(info + '\n')
                less = 1
    if last_avg_price != avg_10s_price:
        last_last_price = last_avg_price
        last_avg_price = avg_10s_price

    price_info = deal_entity.type + u' now_price: %.4f, 3s_price: %.4f, 10s_price: %.4f, 1m_price: %.4f, ' \
                                    u'5min_price: %.4f' \
                 % (latest_price, avg_3s_price, avg_10s_price, avg_min_price, avg_5m_price)
    vol_info = u'cur_vol: %.3f, 3s vol: %.3f, 10s vol: %.3f, 1min vol: %.3f, ask_vol: %.3f, bid_vol: %.3f, 3s_ask_vol: ' \
               u'%.3f, 3s_bid_vol: %.3f' \
               % (deal_entity.amount, ind_3s.vol, ind_10s.vol, ind_1min.vol, ind_1min.ask_vol, ind_1min.bid_vol, ind_3s.ask_vol, ind_3s.bid_vol)
    rate_info = u'10s_rate: %.2f%%, 1min_rate: %.2f%%, 5min_rate: %.2f%%' \
                % (price_10s_change, price_1m_change, price_5m_change)
    write_info = price_info + u', ' + vol_info + u', ' + rate_info + u', ' + now_time + '\r\n'
    write_lines.append(write_info)
    if len(write_lines) >= 100:
        with codecs.open(file_deal, 'a+', 'UTF-8') as f:
            f.writelines(write_lines)
            write_lines = []

    print(price_info + '\r\n' + vol_info + '\r\n' + rate_info + u', ' + now_time)


def query_24h_vol():
    global avg_min_vol
    while 1:
        avg_min_vol = float(okSpot.ticker("eos_usdt")['ticker']['vol']) / 24 / 60
        print('1min avg_vol: %.3f' % avg_min_vol)
        time.sleep(60)


def check_vol():
    if ind_1min.vol > 8 * avg_min_vol and ind_3s.vol > 0.5 * avg_min_vol:
        return True
    else:
        return False


def on_error(ws, error):
    traceback.print_exc()
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    def run(*args):
        ws.send("{'event':'addChannel','channel':'ok_sub_spot_eos_usdt_deals'}")
        print("thread starting...")

    thread.start_new_thread(run, ())


if __name__ == "__main__":
    # websocket.enableTrace(True)
    ws = websocket.WebSocketApp("wss://real.okex.com:10441/websocket",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    thread.start_new_thread(query_24h_vol, ())
    while True:
        ws.run_forever(ping_interval=10, ping_timeout=8)
        print("write left lines into file...")
        with codecs.open(file_deal, 'a+', 'UTF-8') as f:
            f.writelines(write_lines)
            write_lines = []