# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate, string2timestamp
from strategy import get_spot_macd, check_trend
from entity import Coin, Indicator, DealEntity
from trade_spot_v3 import sell_all_position, buy_all_position
import time
from config_strict import spotAPI
import traceback
import codecs

# 默认币种handle_deque
coin = Coin("okb", "usdt")
instrument_id = coin.get_instrument_id()
file_transaction, file_deal = coin.gen_future_file_name()
buy_thread = 0.00001

if __name__ == '__main__':
    more = 0
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
                try:
                    order_info = spotAPI.get_order_info(old_order_id, instrument_id)
                except Exception as e:
                    print(repr(e))
                    traceback.print_exc()
                    del_list.append(old_order_id)
                    continue
                print(order_info)
                # 完全成交的订单或已经撤单的订单
                status = order_info['status']

                side = order_info['side']
                if status == 'filled':
                    print("order %s 已完全成交" % str(old_order_id))
                    del_list.append(old_order_id)
                    if side == 'buy':
                        more = 1
                    elif side == 'sell':
                        more = 0

                elif status == 'cancelled':
                    del_list.append(old_order_id)

                elif int(ts) > string2timestamp(order_info['timestamp']) + 5 + 8 * 3600:
                    print('撤单重挂')
                    try:
                        spotAPI.revoke_order(instrument_id, old_order_id)
                    except Exception as e:
                        print(repr(e))
                        traceback.print_exc()
                        del_list.append(old_order_id)
                        continue
                    ret = spotAPI.get_specific_ticker(instrument_id)
                    if side == 'buy':
                        buy_price = float(ret['best_bid']) + 0.0001
                        try:
                            order_id = buy_all_position(spotAPI, instrument_id, buy_price)
                            if order_id:
                                order_id_queue.append(order_id)
                        except Exception as e:
                            print(repr(e))
                            traceback.print_exc()
                            continue
                    elif side == 'sell':
                        sell_price = float(ret['best_ask']) - 0.0001
                        try:
                            order_id = sell_all_position(spotAPI, instrument_id, sell_price)
                            if order_id:
                                order_id_queue.append(order_id)
                        except Exception as e:
                            print(repr(e))
                            traceback.print_exc()
                            continue

            for del_id in del_list:
                order_id_queue.remove(del_id)
            del_list = []
            time.sleep(1)

            if int(ts) - last_minute_ts > 60:
                last_minute_ts = int(ts)
                if more == 1:
                    print("持有做多单")
                else:
                    print("未持有单")
                try:
                    df = get_spot_macd(spotAPI, instrument_id, 300)
                except Exception as e:
                    print(repr(e))
                    traceback.print_exc()
                    continue
                diff = list(df['diff'])
                dea = list(df['dea'])
                timestamp = list(df['time'])
                new_macd = 2 * (diff[-1] - dea[-1])
                if more == 1 and ((check_trend(list(df['macd'])) == 'down' and new_macd < 0.00005) or new_macd < 0):
                    ret = spotAPI.get_specific_ticker(instrument_id)
                    sell_price = float(ret['best_ask']) - 0.0001
                    order_id = sell_all_position(spotAPI, instrument_id, sell_price)
                    if order_id:
                        order_id_queue.append(order_id)

                elif more == 0 and last_macd <= buy_thread < new_macd and check_trend(list(df['macd'])) == 'up':
                    ret = spotAPI.get_specific_ticker(instrument_id)
                    buy_price = float(ret['best_bid']) + 0.0001
                    order_id = buy_all_position(spotAPI, instrument_id, buy_price)
                    if order_id:
                        order_id_queue.append(order_id)

                last_macd = new_macd
                for i in range(len(diff) - 10, len(diff)):
                    print("macd: %.6f, diff: %.6f, dea: %.6f, macd_time: %s\r\n" % (
                    2 * (diff[i] - dea[i]), diff[i], dea[i], timestamp[i]))
                print("finish calculating macd... %s" % timestamp2string(ts))

        except Exception as e:
            print(repr(e))
            traceback.print_exc()
            continue

