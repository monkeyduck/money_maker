# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate, calc_stf
from trade_v3 import buyin_more, buyin_less, ensure_buyin_more, ensure_buyin_less, sell_less_batch, sell_more_batch, ensure_sell_more, ensure_sell_less
from entity import Coin, Indicator, DealEntity
from config_avg import futureAPI, vol_1m_line, vol_3s_line, vol_1m_bal, vol_3s_bal, incr_5m_rate, incr_1m_rate, incr_10s_rate
import time
import json

import traceback
from collections import deque
import websocket
import codecs

# 默认币种handle_deque
coin = Coin("etc", "usdt")
time_type = "ETC-USD-190329"
file_transaction, file_deal = coin.gen_future_file_name()

deque_min = deque()
deque_10s = deque()
deque_3s = deque()
deque_5m = deque()
latest_price = 0
last_price = 0
last_last_price = 0
ind_1min = Indicator(60)
ind_10s = Indicator(10)
ind_3s = Indicator(3)
ind_5m = Indicator(300)
more = 0
less = 0
moreless = 0
stf = 0
last_avg_price = 0
buy_price = 0

last_5min_macd = 0
last_5min_macd_ts = 0

write_lines = []


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


def cal_price_ago(deq):
    tmp = deque()
    base = (10 if len(deq) >= 10 else len(deq))
    price_sum = 0.0
    avg_price = 0.0
    if base > 0:
        i = 0
        while i < base:
            left = deq.popleft()
            price_sum += left.price
            tmp.append(left)
            i += 1
        avg_price = round(price_sum / base, 4)
        while len(tmp) > 0:
            deq.appendleft(tmp.pop())
    return avg_price


def on_message(ws, message):
    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    if 'pong' in message or 'addChannel' in message:
        return
    global latest_price, last_avg_price, buy_price, more, less, deque_3s, deque_10s, deque_min, \
        deque_5m, ind_3s, ind_10s, ind_1min, ind_5m, write_lines, last_5min_macd, last_5min_macd_ts, moreless, stf, last_price, last_last_price
    jmessage = json.loads(message)

    ts = time.time()
    now_time = timestamp2string(ts)
    if int(ts) - int(last_5min_macd_ts) >= 60:
        last_5min_macd_ts = int(ts)
        print(ts, last_5min_macd_ts)
        if more == 0 and less == 0 and moreless == 0:
            ret = futureAPI.get_specific_position(time_type)
            print(ret)
            if len(ret["holding"]) > 0:
                buy_available = int(ret["holding"][0]["long_avail_qty"])
                sell_available = int(ret["holding"][0]["short_avail_qty"])
                if buy_available > 0:
                    thread.start_new_thread(ensure_sell_more, (futureAPI, coin.name, time_type, latest_price, buy_price,))
                if sell_available > 0:
                    thread.start_new_thread(ensure_sell_less, (futureAPI, coin.name, time_type, latest_price, buy_price,))
            else:
                print("确认未持仓")

    for each_message in jmessage:
        for jdata in each_message['data']:
            latest_price = float(jdata[1])
            deal_entity = DealEntity(jdata[0], float(jdata[1]), round(float(jdata[2]), 3), ts, jdata[4])
            stf += calc_stf(deal_entity, last_price, last_last_price)
            handle_deque(deque_3s, deal_entity, ts, ind_3s)
            handle_deque(deque_10s, deal_entity, ts, ind_10s)
            handle_deque(deque_min, deal_entity, ts, ind_1min)
            price_5m_ago = handle_deque(deque_5m, deal_entity, ts, ind_5m)

            avg_3s_price = ind_3s.cal_avg_price()
            avg_10s_price = ind_10s.cal_avg_price()
            avg_min_price = ind_1min.cal_avg_price()
            avg_5m_price = ind_5m.cal_avg_price()
            price_10s_change = cal_rate(avg_3s_price, avg_10s_price)
            price_1m_change = cal_rate(avg_3s_price, avg_min_price)
            price_5m_change = cal_rate(avg_3s_price, avg_5m_price)
            price_5m_ago_change = cal_rate(latest_price, price_5m_ago)

            if more == 1:
                    if price_1m_change <= -0.2 or price_5m_change <= 0:
                        if sell_more_batch(futureAPI, time_type, latest_price):
                            more = 0
                            thread.start_new_thread(ensure_sell_more, (futureAPI, coin.name, time_type, latest_price, buy_price,))

            elif less == 1:
                # 盈利中，放宽卖出条件，盈利最大化
                if latest_price < buy_price:
                    if price_1m_change >= 0.1 and price_5m_change >= 0:
                        if sell_less_batch(futureAPI, time_type, latest_price):
                            less = 0
                            thread.start_new_thread(ensure_sell_less, (futureAPI, coin.name, time_type, latest_price, buy_price,))
                else:
                    if price_1m_change >= 0.2 or price_5m_change >= 0:
                        if sell_less_batch(futureAPI, time_type, latest_price):
                            less = 0
                            thread.start_new_thread(ensure_sell_less, (futureAPI, coin.name, time_type, latest_price, buy_price,))

            # elif check_vol():
            #     if price_1m_change >= incr_1m_rate and 1.5 > price_5m_change >= incr_5m_rate and 0.3 > price_10s_change >= incr_10s_rate and price_10s_change <= price_1m_change <= price_5m_change:
            #         if ind_3s.bid_vol >= vol_3s_bal * ind_3s.ask_vol and ind_1min.bid_vol >= vol_1m_bal * ind_1min.ask_vol and ind_1min.vol > vol_1m_line:
            #             if latest_price > last_avg_price > avg_3s_price > avg_10s_price > avg_min_price > avg_5m_price:
            #                 if buyin_more(futureAPI, coin.name, time_type, latest_price + 0.01):
            #                     more = 1
            #                     thread.start_new_thread(ensure_buyin_more, (futureAPI, coin.name, time_type, latest_price,))
            #                     buy_price = latest_price
            #                     info = u'发出做多信号！！！买入价格：' + str(buy_price) + u', ' + now_time
            #                     with codecs.open(file_transaction, 'a+', 'utf-8') as f:
            #                         f.writelines(info + '\n')
            #
            #     elif price_5m_change <= -incr_5m_rate and -0.8 < price_1m_change <= -incr_1m_rate and price_10s_change <= -incr_10s_rate and price_10s_change >= price_1m_change >= price_5m_change:
            #         if ind_3s.ask_vol >= vol_3s_bal * ind_3s.bid_vol and ind_1min.ask_vol >= vol_1m_bal * ind_1min.bid_vol:
            #             if latest_price < last_avg_price < avg_3s_price < avg_10s_price < avg_min_price < avg_5m_price:
            #                 if buyin_less(futureAPI, coin.name, time_type, latest_price - 0.01):
            #                     less = 1
            #                     thread.start_new_thread(ensure_buyin_less, (futureAPI, coin.name, time_type, latest_price,))
            #                     buy_price = latest_price
            #                     info = u'发出做空信号！！！买入价格：' + str(buy_price) + u', ' + now_time
            #                     with codecs.open(file_transaction, 'a+', 'utf-8') as f:
            #                         f.writelines(info + '\n')

            last_avg_price = latest_price
            if latest_price != last_price:
                last_last_price = last_price
                last_price = latest_price

            price_info = deal_entity.type + u' stf index: %.4f, now_price: %.4f, 3s_price: %.4f, 10s_price: %.4f, 1m_price: %.4f, ' \
                                            u'5min_price: %.4f, last_price: %.4f, last_last_price: %.4f' \
                         % (stf, latest_price, avg_3s_price, avg_10s_price, avg_min_price, avg_5m_price, last_price, last_last_price)
            vol_info = u'cur_vol: %.3f, 3s vol: %.3f, 10s vol: %.3f, 1min vol: %.3f, ask_vol: %.3f, bid_vol: %.3f, 3s_ask_vol: %.3f, 3s_bid_vol: %.3f' \
                       % (deal_entity.amount, ind_3s.vol, ind_10s.vol, ind_1min.vol, ind_1min.ask_vol, ind_1min.bid_vol,
                          ind_3s.ask_vol, ind_3s.bid_vol)
            rate_info = u'10s_rate: %.2f%%, 1min_rate: %.2f%%, 5min_rate: %.2f%%, 5min_ago_rate: %.2f%%' \
                        % (price_10s_change, price_1m_change, price_5m_change, price_5m_ago_change)
            write_info = price_info + u', ' + vol_info + u', ' + rate_info + u', ' + now_time + '\r\n'
            write_lines.append(write_info)
            if len(write_lines) >= 100:
                with codecs.open(file_deal, 'a+', 'UTF-8') as f:
                    f.writelines(write_lines)
                    write_lines = []

            print(price_info + '\r\n' + vol_info + '\r\n' + rate_info + u', ' + now_time)


def check_vol():
    if ind_3s.vol > vol_3s_line and ind_1min.vol > vol_1m_line:
        return True
    else:
        return False


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