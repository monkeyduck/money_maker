# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate
from strategy import get_macd
from entity import Coin, Indicator, DealEntity
import time
from trade import sell_less_price, sell_more_price, buyin_more_price, buyin_less_price, get_order_info
from config_quick import okFuture
import json
import codecs

# 默认币种handle_deque
coin = Coin("etc", "usdt")
time_type = "quarter"
file_transaction, file_deal = coin.gen_future_file_name()


if __name__ == '__main__':
    more = 0
    less = 0
    last_macd = 0
    first = True
    order_id_queue = []
    last_minute_ts = 0
    del_list = []
    while True:
        try:
            ts = time.time()
            # 获取未完成订单
            if len(order_id_queue) > 0:
                print("order id list: ", order_id_queue)
            for i in range(len(order_id_queue)):
                old_order_id = order_id_queue[i]
                order_info = get_order_info(okFuture, coin.name, time_type, old_order_id)
                # 完全成交的订单或已经撤单的订单
                status = order_info['status']
                order_type = int(order_info['type'])
                ret = okFuture.future_ticker(coin.name + "_usd", time_type)['ticker']
                buy_price = ret['buy'] + 0.001
                sell_price = ret['sell'] - 0.001
                if status == 2:
                    print("order %s 已完全成交" % str(old_order_id))
                    del_list.append(old_order_id)
                    if order_type == 3:
                        order_id = buyin_less_price(okFuture, coin.name, time_type, sell_price)
                        if order_id:
                            order_id_queue.append(order_id)
                            print("挂单开空, order_id: %s, 价格: %.3f" % (str(order_id), sell_price))
                            less = 1
                    elif order_type == 4:
                        order_id = buyin_more_price(okFuture, coin.name, time_type, buy_price)
                        if order_id:
                            order_id_queue.append(order_id)
                            print("挂单开多, order_id: %s, 价格: %.3f" % (str(order_id), buy_price))
                            more = 1

                elif status == -1:
                    del_list.append(old_order_id)
                elif int(ts) > int(order_info['create_date'] / 1000) + 10:
                    okFuture.future_cancel(coin.name + "_usd", time_type, old_order_id)
                    if order_type == 1:
                        order_id = buyin_more_price(okFuture, coin.name, time_type, buy_price)
                        if order_id:
                            order_id_queue.append(order_id)
                    elif order_type == 2:
                        order_id = buyin_less_price(okFuture, coin.name, time_type, sell_price)
                        if order_id:
                            order_id_queue.append(order_id)
                    elif order_type == 3:
                        order_id = sell_more_price(okFuture, coin.name, time_type, sell_price)
                        if order_id:
                            order_id_queue.append(order_id)
                            more = 0
                    elif order_type == 4:
                        order_id = sell_less_price(okFuture, coin.name, time_type, buy_price)
                        if order_id:
                            order_id_queue.append(order_id)
                            less = 0
            for del_id in del_list:
                order_id_queue.remove(del_id)
            del_list = []
            time.sleep(1)

            if int(ts) - last_minute_ts > 60:
                last_minute_ts = int(ts)
                if more == 1:
                    print("持有做多单")
                if less == 1:
                    print("持有做空单")

                df = get_macd(okFuture, coin.name + "_usd", time_type, "1min", 300)
                diff = list(df['diff'])
                dea = list(df['dea'])
                timestamp = list(df['timestamp'])
                new_macd = 2 * (diff[-1] - dea[-1])
                ret = okFuture.future_ticker(coin.name + "_usd", time_type)['ticker']
                buy_price = ret['buy'] + 0.001
                sell_price = ret['sell'] - 0.001
                if more == 1 and new_macd <= 0:
                    order_id = sell_more_price(okFuture, coin.name, time_type, sell_price)
                    if order_id:
                        order_id_queue.append(order_id)
                        more = 0

                elif less == 1 and new_macd >= 0:
                    order_id = sell_less_price(okFuture, coin.name, time_type, buy_price)
                    if order_id:
                        order_id_queue.append(order_id)
                        less = 0

                if more == 0 and last_macd < 0 < new_macd:
                    order_id = buyin_more_price(okFuture, coin.name, time_type, buy_price)
                    if order_id:
                        order_id_queue.append(order_id)
                        print("挂单开多, order_id: %s, 价格: %.3f" % (str(order_id), buy_price))
                        more = 1
                elif less == 0 and last_macd > 0 > new_macd:
                    order_id = buyin_less_price(okFuture, coin.name, time_type, sell_price)
                    if order_id:
                        order_id_queue.append(order_id)
                        print("挂单开空, order_id: %s, 价格: %.3f" % (str(order_id), sell_price))
                        less = 1
                last_macd = new_macd
                if first:
                    first = False
                    for i in range(0, len(diff)):
                        print("macd: %.6f, diff: %.6f, dea: %.6f, macd_time: %s" % (
                        2 * (diff[i] - dea[i]), diff[i], dea[i], timestamp2string(timestamp[i])))
                print(new_macd, diff[-1], dea[-1], timestamp2string(timestamp[-1]), timestamp2string(ts))
        except:
            continue

