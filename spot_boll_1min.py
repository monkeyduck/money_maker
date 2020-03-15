# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string
from strategy import get_spot_boll
from entity import Coin
from monitor.monitor_etc_depth import SpotMaker
import time
from config_strict import spotAPI
import traceback

# 默认币种handle_deque
coin = Coin("etc", "usdt")
instrument_id = coin.get_instrument_id()
file_transaction, file_deal = coin.gen_future_file_name()


if __name__ == '__main__':
    more = 0
    last_macd = 0
    first = True
    order_id_queue = []
    last_minute_ts = 0
    del_list = []
    spot_maker = SpotMaker(1, spotAPI)
    size = 1
    while True:
        try:
            ts = time.time()
            if int(ts) - last_minute_ts > 10:
                last_minute_ts = int(ts)
                try:
                    df = get_spot_boll(spotAPI, instrument_id, 60)
                except Exception as e:
                    print(repr(e))
                    traceback.print_exc()
                    continue
                top = list(df['top'])[-1]
                bottom = list(df['bottom'])[-1]
                timestamp = list(df['time'])
                ret = spotAPI.get_specific_ticker(instrument_id)
                buy_price = float(ret['best_bid']) + 0.0001
                sell_price = float(ret['best_ask']) - 0.0001
                latest_price = float(ret['last'])
                print('latest price: %.4f, boll 上轨: %.4f, 下轨: %.4f, now: %s' % (latest_price, top, bottom, timestamp2string(ts)))
                if latest_price > top:
                    spot_maker.take_sell_order(size, sell_price)
                    print('挂卖单成功')
                if latest_price < bottom:
                    spot_maker.take_buy_order(size, buy_price)
                    print('挂买单成功')




        except Exception as e:
            print(repr(e))
            traceback.print_exc()
            continue

