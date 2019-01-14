# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate, string2timestamp
from trade_v3 import buyin_more, buyin_less, ensure_buyin_more, ensure_buyin_less, sell_less_batch, sell_more_batch, ensure_sell_more, ensure_sell_less
from entity import Coin, Indicator, DealEntity, Order
from config_strict import spotAPI
from trade_spot_v3 import spot_buy, spot_sell
import time
import json

import traceback
from collections import deque
import websocket
import codecs
import os
import copy
import sys

# 默认币种handle_deque
coin_name = "etc"
instrument_id = "etc_usdt"
buy_price = 10000
sell_price = 0
amount = 1
sell_queue = []
buy_queue = []
ask_price = 0
bid_price = 0
last_time_sec = 0
last_time_account_sec = 0
latest_deal_price=0
deque_3s = deque()
ind_3s = Indicator(3)


class SpotMaker:
    def __init__(self, interval):
        self.timeInterval = interval
        self.log_file = os.getcwd() + '/spot_maker.log'


    def timeLog(self, log):
        print(log)
        with codecs.open(self.log_file, 'a+', 'utf-8') as f:
            f.writelines(log + '\r\n')

    def get_account_money(self, coin_name):
        ret = spotAPI.get_coin_account_info(coin_name)
        self.timeLog(str(ret))
        coin_balance = float(ret['balance'])
        price = float(spotAPI.get_specific_ticker(instrument_id)['last'])
        usdt_ret = spotAPI.get_coin_account_info("usdt")
        usdt_balance = float(usdt_ret['balance'])
        self.timeLog(str(usdt_ret))
        total_usdt = coin_balance * price + usdt_balance
        self.timeLog("当前时间: %s, 持有%s: %.4f,单价: %.4f, usdt: %.4f, 折合: %.4f USDT"
                     % (timestamp2string(time.time()), coin_name, coin_balance, price, usdt_balance, total_usdt))

    def revoke_order(self, order_id, now_time_sec):
        try:
            self.timeLog('撤单成功，order_id: %s, result: %s, 时间: %s'
                               % (order_id, spotAPI.revoke_order(instrument_id, order_id),
                                  timestamp2string(now_time_sec)))
            return True
        except Exception as e:
            traceback.print_exc()
            self.timeLog(
                "撤单失败: %s, order_id: %s, 时间: %s" % (repr(e), order_id, timestamp2string(now_time_sec)))
            return False

    def take_sell_order(self, size, price):
        try:
            ret = spotAPI.take_order('limit', 'sell', instrument_id, size, margin_trading=1, client_oid='',
                                     price=price, funds='', )
            if ret and ret['result']:
                return ret["order_id"]
            return False
        except Exception as e:
            traceback.print_exc()
            self.timeLog("挂卖单失败，%s" % repr(e))
            return False

    def take_buy_order(self, size, price):
        try:
            ret = spotAPI.take_order('limit', 'buy', instrument_id, size, margin_trading=1, client_oid='',
                                     price=price, funds='', )
            if ret and ret['result']:
                return ret["order_id"]
            return False
        except Exception as e:
            traceback.print_exc()
            self.timeLog("挂卖单失败，%s" % repr(e))
            return False

    def delete_overdue_order(self, latest_deal_price):
        now_ts = int(time.time())
        self.timeLog('Start to delete pending orders..., %s' % timestamp2string(now_ts))
        orders_list = spotAPI.get_orders_list('open', instrument_id)
        self.timeLog('before delete, pending orders num: %d' % len(orders_list))
        for order in orders_list[0]:
            o_price = float(order['price'])
            o_time = string2timestamp(order['timestamp'])
            if o_time < now_ts - 60 or o_price < latest_deal_price * 0.995 or o_price or o_price > 1.005 * latest_deal_price:
                order_id = order['order_id']
                self.revoke_order(order_id, now_ts)
        self.timeLog('Finish delete pending orders')


    # def go(self):
    #     while True:
    #         try:
    #             if self.timeInterval > 0:
    #                 self.timeLog("等待 %.1f 秒进入下一个循环..." % self.timeInterval)
    #                 time.sleep(self.timeInterval)
    #         except Exeception as e:
    #             self.timeLog(traceback.format_exc())
    #             continue

spot_maker = SpotMaker(1)


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


def on_message(ws, message):
    global buy_price, sell_price, buy_queue, sell_queue, bid_price, ask_price, last_time_sec,latest_deal_price,last_time_account_sec
    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    if 'pong' in message or 'addChannel' in message:
        return
    jmessage = json.loads(message)
    each_message = jmessage[0]
    channel = each_message['channel']
    now_time_sec = float(time.time())
    if channel == 'ok_sub_spot_%s_usdt_depth_5' % coin_name:
        data = each_message['data']
        asks = data['asks'][::-1]
        bids = data['bids']
        ask_price = float(asks[0][0])
        bid_price = float(bids[0][0])
        ask_price_2 = float(asks[1][0])
        bid_price_2 = float(bids[1][0])
        mid_price = (ask_price + bid_price) / 2


    elif channel == ('ok_sub_spot_%s_usdt_deals' % coin_name):

        jdata = each_message['data'][0]
        latest_deal_price = float(jdata[1])
        mid_price = (ask_price + bid_price) / 2
        deal_entity = DealEntity(jdata[0], float(jdata[1]), round(float(jdata[2]), 3), now_time_sec, jdata[4])
        handle_deque(deque_3s, deal_entity, now_time_sec, ind_3s)
        avg_3s_price = ind_3s.cal_avg_price()

        price_3s_change = cal_rate(latest_deal_price, avg_3s_price)
        spot_maker.timeLog("最新成交价: %.4f, 中间价: %.4f, 买一价: %.4f, 卖一价: %.4f, 3秒平均价: %.4f, 波动: %.3f%%"
                           % (latest_deal_price, mid_price, bid_price, ask_price, avg_3s_price, price_3s_change))
        if price_3s_change > 0.03 or price_3s_change < -0.03:
            return
        elif latest_deal_price >= bid_price * 1.0003 and ask_price >= latest_deal_price * 1.0003:
            buy_price = bid_price + 0.0001
            sell_price = ask_price - 0.0001
        elif ask_price > bid_price * 1.0006:
            buy_price = bid_price + 0.0001
            sell_price = ask_price - 0.0001
        else:
            # 不操作
            return
        try:
            buy_order_id = spot_buy(spotAPI, instrument_id, amount, buy_price)
        except Exception as e:
            buy_order_id = False
            traceback.print_exc()
        try:
            sell_order_id = spot_sell(spotAPI, instrument_id, amount, sell_price)
        except Exception as e:
            sell_order_id = False
            traceback.print_exc()




def on_error(ws, error):
    traceback.print_exc()
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    print("websocket connected...")
    ws.send("{'event':'addChannel','channel':'ok_sub_spot_%s_usdt_depth_5'}" % coin_name)
    ws.send("{'event':'addChannel','channel':'ok_sub_spot_%s_usdt_deals'}" % coin_name)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        coin_name = sys.argv[1]
    instrument_id = coin_name + "_usdt"
    ws = websocket.WebSocketApp("wss://real.okex.com:10440/websocket/okexapi?compress=true",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    while True:
        ws.run_forever(ping_interval=10, ping_timeout=5)
