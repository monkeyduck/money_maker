#!/usr/bin/python
# -*- coding: UTF-8 -*-

import websocket
import codecs
try:
    import thread
except ImportError:
    import _thread as thread
import time
import datetime
from collections import deque
from trade import *
import os
import traceback

deque_min = deque()
deque_10s = deque()
deque_3s  = deque()
latest_price = 0
deal_list = []



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
        self.price_num += deal_entity.amount
        self.price += deal_entity.price * deal_entity.amount

    def minus_price(self, deal_entity):
        self.price_num -= deal_entity.amount
        self.price -= deal_entity.price * deal_entity.amount


def timestamp2string(timeStamp):
    timeStamp = int(timeStamp)
    try:
        if len(str(timeStamp)) > 10:
            ts = float(timeStamp) / 1000
        else:
            ts = timeStamp
        d = datetime.datetime.fromtimestamp(ts)
        str1 = d.strftime("%Y-%m-%d %H:%M:%S")
        # 2015-08-28 16:43:37.283000'
        return str1
    except Exception as e:
        print (e)
        return ''


ind_1min = indicator(60)
ind_10s = indicator(10)
ind_3s = indicator(3)
more = 0
less = 0
last_avg_price = 0
buy_price = 0
last_last_price = 0
incr_rate = 0.004
decr_rate = 0.004


def connect():
    ws = websocket.WebSocket()
    ws_address = "wss://real.okex.com"
    ws_port = 10441
    ws.connect(ws_address, http_proxy_host="websocket", http_proxy_port=ws_port)


def on_message(ws, message):
    try:
        if 'pong' in message or 'addChannel' in message:
            return
        global latest_price, last_avg_price, buy_price, last_last_price, more, less, deque_3s, deque_10s, deque_min
        jmessage = json.loads(message)
        ts = time.time()
        file_path = os.getcwd()
        file_transaction = file_path + '/transaction.txt'
        file_deal = file_path + '/deals.txt'

        while len(deque_3s) > 0:
            left = deque_3s.popleft()
            if float(left.time + 3) > float(ts):
                deque_3s.appendleft(left)
                break
            ind_3s.minus_vol(left)
            ind_3s.minus_price(left)

        while len(deque_10s) > 0:
            left = deque_10s.popleft()
            if float(left.time + 10) > float(ts):
                deque_10s.appendleft(left)
                break
            ind_10s.minus_vol(left)
            ind_10s.minus_price(left)

        while len(deque_min) > 0:
            left = deque_min.popleft()
            if float(left.time + 60) > float(ts):
                deque_min.appendleft(left)
                break
            ind_1min.minus_price(left)
            ind_1min.minus_vol(left)

        jdata = jmessage[0]['data'][0]
        latest_price = float(jdata[1])
        deal_entity = dealEntity(jdata[0], float(jdata[1]), round(float(jdata[2]), 2), ts, jdata[4])

        deque_min.append(deal_entity)
        deque_10s.append(deal_entity)
        deque_3s.append(deal_entity)

        ind_3s.add_price(deal_entity)
        ind_3s.add_vol(deal_entity)

        ind_10s.add_vol(deal_entity)
        ind_10s.add_price(deal_entity)

        ind_1min.add_vol(deal_entity)
        ind_1min.add_price(deal_entity)

        avg_3s_price = ind_3s.cal_avg_price()
        avg_10s_price = ind_10s.cal_avg_price()
        avg_min_price = ind_1min.cal_avg_price()

        if more == 1:
            if avg_10s_price <= avg_min_price:
                # 按买一价出售
                if sell_more():
                    sell_price = get_latest_price_this_week('buy')
                    info = u'发出卖出信号！！！卖出价格：' + str(sell_price) + u', 收益: ' + str(sell_price - buy_price)
                    print (info)
                    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                        f.writelines(info + '\n')
                    more = 0
        elif less == 1:
            if avg_10s_price >= avg_min_price:
                if sell_less():
                    sell_price = get_latest_price_this_week('buy')
                    info = u'发出卖出信号！！！卖出价格：' + str(sell_price) + u', 收益: ' + str(buy_price - sell_price)
                    print (info)
                    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                        f.writelines(info + '\n')
                    less = 0
        elif check_vol():
            if latest_price > avg_3s_price > avg_10s_price > last_avg_price > last_last_price and avg_3s_price > float((1 + incr_rate) * avg_min_price) \
                    and ind_1min.bid_vol > float(2 * ind_1min.ask_vol):
                if buyin_more():
                    more = 1
                    buy_price = get_latest_price_this_week('sell')
                    info = u'发出做多信号！！！买入价格：' + str(buy_price) + u', ' + timestamp2string(ts)
                    print (info)
                    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                        f.writelines(info + '\n')

            elif latest_price < avg_3s_price < avg_10s_price < last_avg_price < last_last_price and avg_3s_price < float((1 - decr_rate) * avg_min_price) \
                    and ind_1min.ask_vol > float(2 * ind_1min.bid_vol):
                if buyin_less():
                    buy_price = get_latest_price_this_week('sell')
                    info = u'发出做空信号！！！买入价格：' + str(buy_price) + u', ' + timestamp2string(ts)
                    print (info)
                    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                        f.writelines(info + '\n')
                    less = 1
        if last_avg_price != avg_10s_price:
            last_last_price = last_avg_price
            last_avg_price = avg_10s_price

        price_info = deal_entity.type + u' now_price: %s, 3s_price: %s, 10s_price: %s, 1m_price: %s' % (latest_price, str(ind_3s.cal_avg_price()), str(ind_10s.cal_avg_price()), str(avg_min_price))
        vol_info = u'cur_vol: %s, 3s vol: %s, 10s vol: %s, 1min vol: %s, ask_vol: %s, bid_vol: %s' % (str(deal_entity.amount), str(ind_3s.vol), str(ind_10s.vol), str(ind_1min.vol), str(ind_1min.ask_vol), str(ind_1min.bid_vol))
        with codecs.open(file_deal, 'a+', 'UTF-8') as f:
            f.writelines(price_info + u', ' + vol_info + u', ' + timestamp2string(ts) + '\r\n')

        # print 'now_price: %s' % latest_price + ', 10_avg_price: ' + str(ind_10s.cal_avg_price()) + ', 1min_avg_price: '
        # + str(avg_min_price)
        #  print 'cur_vol: ' + str(deal_entity.amount) + ', 10s vol: ' + str(ind_10s.vol) + ', 1min vol: '
        # + str(ind_1min.vol)
        print(price_info + '\r\n' + vol_info + u', ' + timestamp2string(ts))
    except Exception as e:
        print(e.message)


def check_vol():
    if ind_1min.vol > float(120000):
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
        # while 1:
        #     time.sleep(20)
        #     ws.send("{'event':'ping'}")
    thread.start_new_thread(run, ())


if __name__ == "__main__":
    # websocket.enableTrace(True)
    ws = websocket.WebSocketApp("wss://real.okex.com:10441/websocket",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    while True:
        ws.run_forever(ping_interval=20, ping_timeout=10)