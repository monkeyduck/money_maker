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

# 默认币种handle_deque
instrument_id = "etc_usdt"
buy_price = 10000
sell_price = 0
amount = 1
sell_queue = []
buy_queue = []
first = True

class SpotMaker:
    def __init__(self, interval):
        self.timeInterval = interval
        self.log_file = './spot_maker.log'

    def timeLog(self, log):
        print(log)
        with codecs.open(self.log_file, 'a+', 'utf-8') as f:
            f.writelines(log)

    def go(self):
        while True:
            try:
                if self.timeInterval > 0:
                    self.timeLog("等待 %.1f 秒进入下一个循环..." % self.timeInterval)
                    time.sleep(self.timeInterval)
            except Exception:
                self.timeLog(traceback.format_exc())
                continue



def on_message(ws, message):
    global buy_price, sell_price, buy_queue, sell_queue, first
    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    if 'pong' in message or 'addChannel' in message:
        return
    global write_lines
    jmessage = json.loads(message)
    for each_message in jmessage:
        data = each_message['data']
        asks = data['asks'][::-1]
        bids = data['bids']
        ask_price = float(asks[0][0])
        bid_price = float(bids[0][0])
        # ask_2_price = float(asks[1][0])
        # bid_2_price = float(bids[1][0])
        buy_unfilled_size = 0
        sell_unfilled_size = 0
        if ask_price < sell_price:
            print('sell_queue: ', sell_queue)
            to_del_list = []
            for order_id in sell_queue:
                # order_info = spotAPI.get_order_info(order_id, instrument_id)
                # if order_info['status'] == 'part_filled':
                #     filled_size = float(order_info['filled_size'])
                #     total_size = float(order_info['size'])
                #     sell_unfilled_size += (total_size - filled_size)
                # elif order_info['status'] == 'filled':
                #     continue
                # elif order_info['status'] == 'open':
                #     sell_unfilled_size += amount
                print('revoke order: %s, result: %s' % (order_id,spotAPI.revoke_order(instrument_id, order_id)))
                to_del_list.append(order_id)
            for to_del_id in to_del_list:
                sell_queue.remove(to_del_id)
        if bid_price > buy_price:
            to_del_list = []
            print('buy_queue: ', buy_queue)
            for order_id in buy_queue:
                # order_info = spotAPI.get_order_info(order_id, instrument_id)
                # if order_info['status'] == 'part_filled':
                #     filled_size = float(order_info['filled_size'])
                #     total_size = float(order_info['size'])
                #     buy_unfilled_size += (total_size - filled_size)
                # elif order_info['status'] == 'filled':
                #     continue
                # elif order_info['status'] == 'open':
                #     buy_unfilled_size += amount
                print('revoke order: %s, result: %s' % (order_id, spotAPI.revoke_order(instrument_id, order_id)))
                to_del_list.append(order_id)
            for to_del_id in to_del_list:
                buy_queue.remove(to_del_id)
        #下单
        if ask_price >= bid_price * 1.001:
            # print("buy")
            buy_price = bid_price + 0.0001
            sell_price = ask_price - 0.0001
            if first:
                first = False
                buy_order_id = spot_buy(spotAPI, instrument_id, amount + buy_unfilled_size, buy_price)
                sell_order_id = spot_sell(spotAPI, instrument_id, amount + sell_unfilled_size, sell_price)
            else:
                first = True
                sell_order_id = spot_sell(spotAPI, instrument_id, amount + sell_unfilled_size, sell_price)
                buy_order_id = spot_buy(spotAPI, instrument_id, amount + buy_unfilled_size, buy_price)

            if buy_order_id:
                buy_queue.append(buy_order_id)
            if sell_order_id:
                sell_queue.append(sell_order_id)
            ask_info = 'asks price: %.4f, sel_price: %.4f' % (ask_price, sell_price)
            bid_info = 'bids price: %.4f, buy_price: %.4f' % (bid_price, buy_price)
            print(ask_info)
            print(bid_info)

        # write_lines.append(timestamp2string(timestamp) + '\r\n' + ask_info + '\r\n' + bid_info)
        # if len(write_lines) > 300:
        #     with codecs.open(file_depth, 'a+', 'UTF-8') as f:
        #         f.writelines(write_lines)
        #         write_lines = []


def on_error(ws, error):
    traceback.print_exc()
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    print("websocket connected...")
    ws.send("{'event':'addChannel','channel':'ok_sub_spot_etc_usdt_depth_5'}")


if __name__ == '__main__':
    # ws = websocket.WebSocketApp("wss://real.okex.com:10442/ws/v3?compress=true",
    ws = websocket.WebSocketApp("wss://real.okex.com:10440/websocket/okexapi?compress=true",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    while True:
        ws.run_forever(ping_interval=10, ping_timeout=5)
