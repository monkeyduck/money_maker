# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate
from strategy import get_macd, check_trend, get_spot_macd
from entity import Coin, Indicator, DealEntity
import time
from trade import sell_less_price, sell_more_price, buyin_more, buyin_less, buyin_less_price, buyin_more_price, get_order_info
from config_avg import okFuture, spotAPI
import json
import codecs

# 默认币种handle_deque
coin = Coin("eos", "usdt")
instrument_id = coin.get_instrument_id()
time_type = "quarter"
file_transaction, file_deal = coin.gen_future_file_name()
buy_thread = 0.0001


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
                print('订单信息: %s' % order_info)
                # 完全成交的订单或已经撤单的订单
                status = order_info['status']
                order_type = int(order_info['type'])
                ret = okFuture.future_ticker(coin.name + "_usd", time_type)['ticker']
                buy_price = ret['buy'] + 0.001
                sell_price = ret['sell'] - 0.001
                if status == 2:
                    print("order %s 已完全成交" % str(old_order_id))
                    del_list.append(old_order_id)
                    if order_type == 1:
                        more = 1
                    elif order_type == 2:
                        less = 1
                    elif order_type == 3:
                        more = 0
                    elif order_type == 4:
                        less = 0

                elif status == -1:
                    del_list.append(old_order_id)
                elif int(ts) > int(order_info['create_date'] / 1000) + 3:
                    okFuture.future_cancel(coin.name + "_usd", time_type, old_order_id)
                    if order_type == 1:
                        order_id = buyin_more(okFuture, coin.name, time_type, buy_price)
                        if order_id:
                            order_id_queue.append(order_id)
                    elif order_type == 2:
                        order_id = buyin_less(okFuture, coin.name, time_type, sell_price)
                        if order_id:
                            order_id_queue.append(order_id)
                    elif order_type == 3:
                        order_id = sell_more_price(okFuture, coin.name, time_type, sell_price)
                        if order_id:
                            order_id_queue.append(order_id)
                    elif order_type == 4:
                        order_id = sell_less_price(okFuture, coin.name, time_type, buy_price)
                        if order_id:
                            order_id_queue.append(order_id)
            for del_id in del_list:
                order_id_queue.remove(del_id)
            del_list = []
            time.sleep(1)

            if int(ts) - last_minute_ts > 60:
                last_minute_ts = int(ts)
                if more == 1:
                    jRet = json.loads(okFuture.future_position_4fix(coin.name + "_usd", time_type, "1"))
                    if len(jRet["holding"]) > 0:
                        buy_available = jRet["holding"][0]["buy_available"]
                        if buy_available > 0:
                            print("确认持有做多单: ", jRet)
                        else:
                            more = 0
                    else:
                        more = 0
                elif less == 1:
                    jRet = json.loads(okFuture.future_position_4fix(coin.name + "_usd", time_type, "1"))
                    if len(jRet["holding"]) > 0:
                        sell_available = jRet["holding"][0]["sell_available"]
                        if sell_available > 0:
                            print("确认持有做空单: ", jRet)
                        else:
                            less = 0
                    else:
                        less = 0
                else:
                    print('未持有单, %s' % timestamp2string(int(ts)))
                df = get_spot_macd(spotAPI, instrument_id, 300)
                # df = get_macd(okFuture, coin.name + "_usd", time_type, "5min", 300)
                diff = list(df['diff'])
                dea = list(df['dea'])
                timestamp = list(df['time'])
                new_macd = 2 * (diff[-1] - dea[-1])
                macd_5min = list(df['macd'])

                # df_15 = get_macd(okFuture, coin.name + "_usd", time_type, "15min", 300)
                # diff_15 = list(df_15['diff'])
                # dea_15 = list(df_15['dea'])
                # timestamp_15 = list(df_15['timestamp'])
                # macd_15min = list(df_15['macd'])
                # new_macd_15 = macd_15min[-1]

                ret = okFuture.future_ticker(coin.name + "_usd", time_type)['ticker']
                print('%s最新行情: %s, new_macd: %.6f, last_macd: %.6f' % (coin.name, ret, new_macd, last_macd))
                buy_price = ret['buy']
                sell_price = ret['sell']
                if more == 1 and ((check_trend(list(df['macd'])) == 'down' and new_macd < buy_thread)
                                  or new_macd < -buy_thread):
                    order_id = sell_more_price(okFuture, coin.name, time_type, sell_price)
                    if order_id:
                        print('挂平多单')
                        order_id_queue.append(order_id)

                elif less == 1 and ((check_trend(list(df['macd'])) == 'up' and new_macd > -buy_thread)
                                    or new_macd > buy_thread):
                    order_id = sell_less_price(okFuture, coin.name, time_type, buy_price)
                    if order_id:
                        print('挂平空单')
                        order_id_queue.append(order_id)

                if more == 0 and last_macd <= buy_thread < new_macd and diff[-1] > 0:
                    order_id = buyin_more_price(okFuture, coin.name, time_type, buy_price)
                    if order_id:
                        order_id_queue.append(order_id)
                        print("挂单开多, order_id: %s, 价格: %.3f" % (str(order_id), buy_price))
                elif less == 0 and new_macd < -buy_thread <= last_macd and diff[-1] < 0:
                    order_id = buyin_less_price(okFuture, coin.name, time_type, sell_price)
                    if order_id:
                        order_id_queue.append(order_id)
                        print("挂单开空, order_id: %s, 价格: %.3f" % (str(order_id), sell_price))
                last_macd = new_macd
                for i in range(len(diff) - 10, len(diff)):
                    print("5min macd: %.6f, diff: %.6f, dea: %.6f, macd_time: %s, now: %s" %
                          (2 * (diff[i] - dea[i]), diff[i], dea[i], timestamp2string(timestamp[i]), timestamp2string(time.time())))

        except Exception as e:
            print(e)
            continue

