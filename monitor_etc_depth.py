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


class Order:
    def __init__(self, order_id, price, amount, type, order_time):
        self.order_id = order_id
        self.price = price
        self.amount = amount
        self.type = type
        self.order_time = order_time

    def detail(self):
        return self.type + " " + str(self.amount) + ' at price ' + str(self.price) + ', order_id: ' + self.order_id


class SpotMaker:
    def __init__(self, interval):
        self.timeInterval = interval
        self.log_file = os.getcwd() + '/spot_maker.log'


    def timeLog(self, log):
        print(log)
        with codecs.open(self.log_file, 'a+', 'utf-8') as f:
            f.writelines(log + '\r\n')

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


def on_message(ws, message):
    global buy_price, sell_price, buy_queue, sell_queue, bid_price, ask_price, last_time_sec
    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    if 'pong' in message or 'addChannel' in message:
        return
    jmessage = json.loads(message)
    for each_message in jmessage:
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
            if now_time_sec > last_time_sec + 0.5:
                last_time_sec = now_time_sec
                print('撤单前sell_queue length: ', len(sell_queue))
                new_queue = []
                for order in sell_queue:
                    print(order.detail())
                    if ask_price_2 < order.price:
                        spot_maker.timeLog('卖二价: %.4f 低于卖单价: %.4f, 撤卖单%s' % (ask_price_2, order.price, order.order_id))
                        try:
                            spot_maker.timeLog('撤单成功，order_id: %s, result: %s, 时间: %s'
                                               % (order.order_id, spotAPI.revoke_order(instrument_id, order.order_id), timestamp2string(now_time_sec)))
                        except Exception as e:
                            traceback.print_exc()
                            spot_maker.timeLog(
                                "撤单失败: %s, order_id: %s, 时间: %s" % (repr(e), order.order_id, timestamp2string(now_time_sec)))
                            continue

                        if ask_price > bid_price * 1.0006:
                            sell_price = ask_price - 0.0001
                            buy_price = bid_price + 0.0001
                            try:
                                sell_order_id = spot_sell(spotAPI, instrument_id, amount, sell_price)
                                if sell_order_id:
                                    sell_order = Order(sell_order_id, sell_price, amount, 'sell', timestamp2string(now_time_sec))
                                    new_queue.append(sell_order)
                                    spot_maker.timeLog("挂卖出单成功，时间：%s, 价格: %.4f, order_id: %s" % (timestamp2string(now_time_sec), sell_price, sell_order_id))
                                buy_order_id = spot_buy(spotAPI, instrument_id, amount, buy_price)
                                if buy_order_id:
                                    buy_order = Order(buy_order_id, buy_price, amount, 'buy', timestamp2string(now_time_sec))
                                    buy_queue.append(buy_order)
                                    spot_maker.timeLog("挂买入单成功，时间：%s, 价格: %.4f, order_id: %s" % (timestamp2string(now_time_sec), buy_price, buy_order_id))
                            except Exception as e:
                                traceback.print_exc()
                                spot_maker.timeLog('挂单失败: ' + repr(e))
                                continue

                    elif ask_price == order.price and ask_price_2 > order.price * 1.0002:
                        spot_maker.timeLog('卖二价: %.4f,比当前挂的卖一价: %.4f 高万二, 撤卖一单%s' % (ask_price_2, order.price, order.order_id))
                        try:
                            spot_maker.timeLog('撤单成功，order_id: %s, result: %s, 时间: %s'
                                               % (order.order_id, spotAPI.revoke_order(instrument_id, order.order_id),
                                                  timestamp2string(now_time_sec)))
                        except Exception as e:
                            traceback.print_exc()
                            spot_maker.timeLog(
                                "撤单失败: %s，order_id: %s, 时间: %s" % (repr(e), order.order_id, timestamp2string(now_time_sec)))
                            continue
                        try:
                            sell_price = ask_price_2 - 0.0001
                            sell_order_id = spot_sell(spotAPI, instrument_id, amount, sell_price)
                            if sell_order_id:
                                sell_order = Order(sell_order_id, sell_price, amount, 'sell',
                                                   timestamp2string(now_time_sec))
                                new_queue.append(sell_order)
                                spot_maker.timeLog("挂卖出单成功，时间：%s, 价格: %.4f, order_id: %s" % (
                                timestamp2string(now_time_sec), sell_price, sell_order_id))
                        except Exception as e:
                            traceback.print_exc()
                            spot_maker.timeLog(
                                "挂单卖出失败: %s, order_id: %s, 时间: %s" % (repr(e), order.order_id, timestamp2string(now_time_sec)))
                            continue
                    elif bid_price > order.price:
                        continue
                    else:
                        new_queue.append(order)
                sell_queue = copy.deepcopy(new_queue)
                new_queue = []
                print('撤单后sell_queue length: ', len(sell_queue))
                print('撤单前buy_queue length: ', len(buy_queue))
                for order in buy_queue:
                    print(order.detail())
                    if bid_price_2 > order.price:
                        spot_maker.timeLog('买二价: %.4f 高于买单价: %.4f, 撤买单%s' % (bid_price_2, order.price, order.order_id))
                        try:
                            spot_maker.timeLog('撤单成功，order_id: %s, result: %s, 时间: %s' % (order.order_id, spotAPI.revoke_order(instrument_id, order.order_id), timestamp2string(now_time_sec)))
                        except Exception as e:
                            traceback.print_exc()
                            spot_maker.timeLog(
                                "撤单失败: %s，order_id: %s, 时间: %s" % (repr(e), order.order_id, timestamp2string(now_time_sec)))
                            continue
                        if ask_price > bid_price * 1.0006:
                            sell_price = ask_price - 0.0001
                            buy_price = bid_price + 0.0001
                            try:
                                buy_order_id = spot_buy(spotAPI, instrument_id, amount, buy_price)
                                if buy_order_id:
                                    buy_order = Order(buy_order_id, buy_price, amount, 'buy',
                                                      timestamp2string(now_time_sec))
                                    new_queue.append(buy_order)
                                    spot_maker.timeLog("挂买入单成功，时间：%s, 价格: %.4f, order_id: %s" % (
                                    timestamp2string(now_time_sec), buy_price, buy_order_id))

                                sell_order_id = spot_sell(spotAPI, instrument_id, amount, sell_price)
                                if sell_order_id:
                                    sell_order = Order(sell_order_id, sell_price, amount, 'sell',
                                                       timestamp2string(now_time_sec))
                                    sell_queue.append(sell_order)
                                    spot_maker.timeLog("挂卖出单成功，时间：%s, 价格: %.4f, order_id: %s" % (
                                        timestamp2string(now_time_sec), sell_price, sell_order_id))
                            except Exception as e:
                                traceback.print_exc()
                                spot_maker.timeLog('挂单失败: ' + repr(e))
                                continue

                    elif bid_price == order.price and bid_price_2 * 1.0002 < bid_price:
                        spot_maker.timeLog('买二价: %.4f,比当前挂的买一价: %.4f 低万二, 撤买一单%s' % (bid_price_2, order.price, order.order_id))
                        try:
                            spot_maker.timeLog('撤单成功，order_id: %s, result: %s, 时间: %s'
                                               % (order.order_id, spotAPI.revoke_order(instrument_id, order.order_id),
                                                  timestamp2string(now_time_sec)))
                        except Exception as e:
                            traceback.print_exc()
                            spot_maker.timeLog(
                                "撤单失败: %s，order_id: %s, 时间: %s" % (repr(e), order.order_id, timestamp2string(now_time_sec)))
                            continue
                        try:
                            buy_price = bid_price_2 + 0.0001
                            buy_order_id = spot_buy(spotAPI, instrument_id, amount, buy_price)
                            if buy_order_id:
                                buy_order = Order(buy_order_id, buy_price, amount, 'buy',
                                                   timestamp2string(now_time_sec))
                                new_queue.append(buy_order)
                                spot_maker.timeLog("挂买单成功，时间：%s, 价格: %.4f, order_id: %s" % (
                                timestamp2string(now_time_sec), buy_price, buy_order_id))
                        except Exception as e:
                            traceback.print_exc()
                            spot_maker.timeLog(
                                "撤单失败: %s，order_id: %s, 时间: %s" % (repr(e), order.order_id, timestamp2string(now_time_sec)))
                            continue
                    elif ask_price < order.price:
                        continue
                    else:
                        new_queue.append(order)
                buy_queue = copy.deepcopy(new_queue)
                print('撤单后buy_queue length: ', len(buy_queue))
        elif channel == ('ok_sub_spot_%s_usdt_deals' % coin_name):
            for jdata in each_message['data']:
                latest_deal_price = float(jdata[1])
                print("最新成交价: %.4f, 买一价: %.4f, 卖一价: %.4f" % (latest_deal_price, bid_price, ask_price))
                if latest_deal_price > bid_price * 1.0002 and ask_price > latest_deal_price * 1.0002 \
                        and buy_price != bid_price + 0.0001 and sell_price != ask_price - 0.0001:
                    buy_price = bid_price + 0.0001
                    sell_price = ask_price - 0.0001
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
                    if buy_order_id:
                        buy_order = Order(buy_order_id, buy_price, amount, 'buy', timestamp2string(now_time_sec))
                        buy_queue.append(buy_order)
                        spot_maker.timeLog("挂买入单成功，时间：%s, 价格: %.4f, order_id: %s" % (timestamp2string(time.time()), buy_price, buy_order_id))
                    if sell_order_id:
                        sell_order = Order(sell_order_id, sell_price, amount, 'sell', timestamp2string(now_time_sec))
                        sell_queue.append(sell_order)
                        spot_maker.timeLog("挂卖出单成功，时间：%s, 价格: %.4f, order_id: %s" % (timestamp2string(time.time()), sell_price, sell_order_id))


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
