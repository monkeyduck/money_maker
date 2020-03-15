# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate, string2timestamp
from trade_v3 import buyin_more, buyin_less, ensure_buyin_more, ensure_buyin_less, sell_less_batch, sell_more_batch, ensure_sell_more, ensure_sell_less
from entity import Coin, Indicator, DealEntity, Order
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
last_time_account_sec = 0
latest_deal_price=0
deque_3s = deque()
ind_3s = Indicator(3)


class SpotMaker:
    def __init__(self, interval, spotAPI):
        self.spotAPI = spotAPI
        self.timeInterval = interval
        self.log_file = os.getcwd() + '/spot_maker.log'


    def timeLog(self, log):
        print(log)
        with codecs.open(self.log_file, 'a+', 'utf-8') as f:
            f.writelines(log + '\r\n')

    def get_account_money(self, coin_name):
        ret = self.spotAPI.get_coin_account_info(coin_name)
        self.timeLog(str(ret))
        coin_balance = float(ret['balance'])
        price = float(self.spotAPI.get_specific_ticker(instrument_id)['last'])
        usdt_ret = self.spotAPI.get_coin_account_info("usdt")
        usdt_balance = float(usdt_ret['balance'])
        self.timeLog(str(usdt_ret))
        total_usdt = coin_balance * price + usdt_balance
        self.timeLog("当前时间: %s, 持有%s: %.4f,单价: %.4f, usdt: %.4f, 折合: %.4f USDT"
                     % (timestamp2string(time.time()), coin_name, coin_balance, price, usdt_balance, total_usdt))

    def revoke_order(self, order_id, now_time_sec):
        try:
            self.timeLog('撤单成功，order_id: %s, result: %s, 时间: %s'
                               % (order_id, self.spotAPI.revoke_order(instrument_id, order_id),
                                  timestamp2string(now_time_sec)))
            return True
        except Exception as e:
            traceback.print_exc()
            self.timeLog(
                "撤单失败: %s, order_id: %s, 时间: %s" % (repr(e), order_id, timestamp2string(now_time_sec)))
            return False

    def take_sell_order(self, size, price):
        try:
            ret = self.spotAPI.take_order('limit', 'sell', instrument_id, size, margin_trading=1, client_oid='',
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
            ret = self.spotAPI.take_order('limit', 'buy', instrument_id, size, margin_trading=1, client_oid='',
                                     price=price, funds='', )
            if ret and ret['result']:
                return ret["order_id"]
            return False
        except Exception as e:
            traceback.print_exc()
            self.timeLog("挂买单失败，%s" % repr(e))
            return False

    def delete_overdue_order(self, latest_deal_price):
        now_ts = int(time.time())
        self.timeLog('Start to delete pending orders..., %s' % timestamp2string(now_ts))
        orders_list = self.spotAPI.get_orders_list('open', instrument_id)
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

spot_maker = SpotMaker(1, spotAPI)


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
        if now_time_sec > last_time_sec + 0.2:
            last_time_sec = now_time_sec
            print('撤单前sell_queue length: ', len(sell_queue))
            new_queue = []
            for order in sell_queue:
                is_revoke_suc = spot_maker.revoke_order(order.order_id, now_time_sec)
                if is_revoke_suc:
                    if latest_deal_price >= ask_price * 0.9999:
                        # 上涨行情, 追加买单
                        buy_price = mid_price
                        sell_price = max(buy_price * 1.001, ask_price_2)
                        buy_order_id = spot_maker.take_buy_order(2 * amount, buy_price)
                        if buy_order_id:
                            new_buy_order = Order(buy_order_id, buy_price, amount, 'buy', now_time_sec)
                            buy_queue.append(new_buy_order)
                            spot_maker.timeLog("挂买入单成功，时间：%s, 价格: %.4f, order_id: %s" % (
                                timestamp2string(now_time_sec), buy_price, buy_order_id))
                        continue
                    else:
                        sell_price = ask_price - 0.0001
                    if ask_price > bid_price * 1.0006:
                        sell_order_id = spot_maker.take_sell_order(amount, sell_price)
                        if sell_order_id:
                            new_sell_order = Order(sell_order_id, sell_price, amount, 'sell',
                                                   timestamp2string(now_time_sec))
                            new_queue.append(new_sell_order)
                            spot_maker.timeLog("挂卖出单成功，时间：%s, 价格: %.4f, order_id: %s" % (
                                timestamp2string(now_time_sec), sell_price, sell_order_id))

                else:
                    # 撤单失败，retry
                    spot_maker.timeLog('%s撤单失败，重试')
                    spot_maker.revoke_order(order.order_id, now_time_sec)

            sell_queue = copy.deepcopy(new_queue)
            new_queue = []
            print('撤单后sell_queue length: ', len(sell_queue))
            print('撤单前buy_queue length: ', len(buy_queue))
            for order in buy_queue:
                if spot_maker.revoke_order(order.order_id, now_time_sec):
                    if latest_deal_price <= bid_price * 1.0001:
                        # 下跌行情, 追加卖单
                        sell_price = mid_price
                        buy_price = min(sell_price * 0.999, bid_price_2)
                        sell_order_id = spot_maker.take_sell_order(amount, sell_price)
                        if sell_order_id:
                            new_sell_order = Order(sell_order_id, sell_price, 2 * amount, 'sell',
                                                   timestamp2string(now_time_sec))
                            sell_queue.append(new_sell_order)
                            spot_maker.timeLog("挂卖出单成功，时间：%s, 价格: %.4f, order_id: %s" % (
                                timestamp2string(now_time_sec), sell_price, sell_order_id))
                        continue
                    else:
                        buy_price = bid_price + 0.0001
                    if ask_price > bid_price * 1.0006:
                        buy_order_id = spot_maker.take_buy_order(amount, buy_price)
                        if buy_order_id:
                            new_buy_order = Order(buy_order_id, buy_price, amount, 'buy', now_time_sec)
                            new_queue.append(new_buy_order)
                            spot_maker.timeLog("挂买入单成功，时间：%s, 价格: %.4f, order_id: %s" % (
                                timestamp2string(now_time_sec), buy_price, buy_order_id))

            buy_queue = copy.deepcopy(new_queue)
            print('撤单后buy_queue length: ', len(buy_queue))

    elif channel == ('ok_sub_spot_%s_usdt_deals' % coin_name):


        jdata = each_message['data'][0]
        latest_deal_price = float(jdata[1])
        mid_price = (ask_price + bid_price) / 2
        deal_entity = DealEntity(jdata[0], float(jdata[1]), round(float(jdata[2]), 3), now_time_sec, jdata[4])
        handle_deque(deque_3s, deal_entity, now_time_sec, ind_3s)
        avg_3s_price = ind_3s.cal_avg_price()
        if now_time_sec > last_time_account_sec + 60:
            last_time_account_sec = now_time_sec
            spot_maker.get_account_money(coin_name)
            spot_maker.delete_overdue_order(latest_deal_price)
        price_3s_change = cal_rate(latest_deal_price, avg_3s_price)
        spot_maker.timeLog("最新成交价: %.4f, 中间价: %.4f, 买一价: %.4f, 卖一价: %.4f, 3秒平均价: %.4f, 波动: %.3f%%"
                           % (latest_deal_price, mid_price, bid_price, ask_price, avg_3s_price, price_3s_change))
        if price_3s_change > 0.03 or price_3s_change < -0.03:
            return
        elif latest_deal_price > bid_price * 1.0002 and ask_price > latest_deal_price * 1.0002 \
                and buy_price != bid_price + 0.0001 and sell_price != ask_price - 0.0001:
            buy_price = bid_price + 0.0001
            sell_price = ask_price - 0.0001
        elif ask_price > bid_price * 1.0006 and buy_price != bid_price + 0.0001 and sell_price != ask_price - 0.0001:
            if latest_deal_price < mid_price:
                buy_price = bid_price + 0.0001
                sell_price = buy_price * 1.0005
            else:
                sell_price = ask_price - 0.0001
                buy_price = ask_price * 0.9995
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
        if buy_order_id:
            buy_order = Order(buy_order_id, buy_price, amount, 'buy', timestamp2string(now_time_sec))
            buy_queue.append(buy_order)
            spot_maker.timeLog("挂买入单成功，时间：%s, 价格: %.4f, order_id: %s" % (
            timestamp2string(time.time()), buy_price, buy_order_id))
        if sell_order_id:
            sell_order = Order(sell_order_id, sell_price, amount, 'sell', timestamp2string(now_time_sec))
            sell_queue.append(sell_order)
            spot_maker.timeLog("挂卖出单成功，时间：%s, 价格: %.4f, order_id: %s" % (
            timestamp2string(time.time()), sell_price, sell_order_id))



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
