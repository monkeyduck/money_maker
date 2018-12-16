# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate, cal_weighted
from trade_v3 import ensure_sell_more, ensure_sell_less, ensure_buyin_less, ensure_buyin_more, buyin_more, buyin_less, sell_less_batch, sell_more_batch
from entity import Coin, Indicator, DealEntity
from config_avg import futureAPI
import time
import json

import traceback
import websocket
import codecs

# 默认币种handle_deque
coin_etc = Coin("etc", "usdt")
coin_btc = Coin("btc", "usdt")
coin_ltc = Coin("ltc", "usdt")
coin_eth = Coin("eth", "usdt")
coin_eos = Coin("eos", "usdt")
coin_xrp = Coin("xrp", "usdt")

time_type = "EOS-USD-190329"
file_transaction, file_deal = coin_eos.gen_future_file_name()


latest_price = 0

more = 0
less = 0
buy_price = 0
last_5min_macd_ts = 0

btc_30s_change = 0
eth_30s_change = 0
ltc_30s_change = 0
etc_30s_change = 0
eos_30s_change = 0
xrp_30s_change = 0
btc_5min_change = 0
eth_5min_change = 0
ltc_5min_change = 0
etc_5min_change = 0
eos_5min_change = 0
xrp_5min_change = 0


write_lines = []


def on_message(ws, message):
    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    if 'pong' in message or 'addChannel' in message:
        return
    global latest_price, buy_price, more, less, write_lines, last_5min_macd_ts, \
        btc_30s_change, eth_30s_change, ltc_30s_change, etc_30s_change, eos_30s_change, xrp_30s_change, \
        btc_5min_change, eth_5min_change, ltc_5min_change, etc_5min_change, eos_5min_change, xrp_5min_change
    jmessage = json.loads(message)
    ts = time.time()
    now_time = timestamp2string(ts)

    try:
        if int(ts) - int(last_5min_macd_ts) >= 60:
            last_5min_macd_ts = int(ts)
            print(ts, last_5min_macd_ts)
            if more == 0 and less == 0:
                ret = futureAPI.get_specific_position(time_type)
                print(ret)
                if len(ret["holding"]) > 0:
                    buy_available = int(ret["holding"][0]["long_avail_qty"])
                    sell_available = int(ret["holding"][0]["short_avail_qty"])
                    if buy_available > 0:
                        thread.start_new_thread(ensure_sell_more, (futureAPI, coin_eos.name, time_type, latest_price, buy_price,))
                    if sell_available > 0:
                        thread.start_new_thread(ensure_sell_less, (futureAPI, coin_eos.name, time_type, latest_price, buy_price,))
                else:
                    print("确认未持仓")

        each_message = jmessage[0]
        channel = each_message['channel']
        jdata = each_message['data'][0]
        latest_price = float(jdata[1])
        deal_entity = DealEntity(jdata[0], latest_price, round(float(jdata[2]), 3), ts, jdata[4])
        if channel == 'ok_sub_spot_btc_usdt_deals':
            coin_btc.process_entity(deal_entity, ts)
            btc_30s_change = cal_rate(latest_price, coin_btc.get_avg_price_30s())
            btc_5min_change = cal_rate(latest_price, coin_btc.get_avg_price_5min())
            print('btc 30s change: %.3f%%, 5min change: %.3f%%' % (eth_30s_change, eth_5min_change))

        elif channel == 'ok_sub_spot_etc_usdt_deals':
            coin_etc.process_entity(deal_entity, ts)
            etc_30s_change = cal_rate(latest_price, coin_etc.get_avg_price_30s())
            etc_5min_change = cal_rate(latest_price, coin_etc.get_avg_price_5min())
            print('etc 30s change: %.3f%%, 5min change: %.3f%%' % (eth_30s_change, eth_5min_change))

        elif channel == 'ok_sub_spot_ltc_usdt_deals':
            coin_ltc.process_entity(deal_entity, ts)
            ltc_30s_change = cal_rate(latest_price, coin_ltc.get_avg_price_30s())
            ltc_5min_change = cal_rate(latest_price, coin_ltc.get_avg_price_5min())
            print('ltc 30s change: %.3f%%, 5min change: %.3f%%' % (eth_30s_change, eth_5min_change))

        elif channel == 'ok_sub_spot_eos_usdt_deals':
            coin_eos.process_entity(deal_entity, ts)
            eos_30s_change = cal_rate(latest_price, coin_eos.get_avg_price_30s())
            eos_5min_change = cal_rate(latest_price, coin_eos.get_avg_price_5min())
            print('eos 30s change: %.3f%%, 5min change: %.3f%%' % (eth_30s_change, eth_5min_change))

        elif channel == 'ok_sub_spot_eth_usdt_deals':
            coin_eth.process_entity(deal_entity, ts)
            eth_30s_change = cal_rate(latest_price, coin_eth.get_avg_price_30s())
            eth_5min_change = cal_rate(latest_price, coin_eth.get_avg_price_5min())
            print('eth 30s change: %.3f%%, 5min change: %.3f%%' % (eth_30s_change, eth_5min_change))
        elif channel == 'ok_sub_spot_xrp_usdt_deals':
            coin_xrp.process_entity(deal_entity, ts)
            xrp_30s_change = cal_rate(latest_price, coin_xrp.get_avg_price_30s())
            xrp_5min_change = cal_rate(latest_price, coin_xrp.get_avg_price_5min())
            print('xrp 30s change: %.3f%%, 5min change: %.3f%%' % (eth_30s_change, eth_5min_change))

        prices_30s = [btc_30s_change, eth_30s_change, ltc_30s_change, etc_30s_change, eos_30s_change, xrp_30s_change]
        prices_5min = [btc_5min_change, eth_5min_change, ltc_5min_change, etc_5min_change, eos_5min_change, xrp_5min_change]
        weights = [0.2, 0.15, 0.15, 0.15, 0.2, 0.15]
        weighted_30s_change = cal_weighted(prices_30s, weights)
        weighted_5min_change = cal_weighted(prices_5min, weights)

        if more == 1:
            if weighted_30s_change < -0.2 or weighted_5min_change < 0:
                if sell_more_batch(futureAPI, time_type, latest_price):
                    more = 0
                    thread.start_new_thread(ensure_sell_more,
                                            (futureAPI, coin_eos.name, time_type, latest_price, buy_price,))

        elif less == 1:
            if weighted_30s_change > 0.2 or weighted_5min_change > 0:

                if sell_less_batch(futureAPI, time_type, latest_price):
                    less = 0
                    thread.start_new_thread(ensure_sell_less,
                                            (futureAPI, coin_eos.name, time_type, latest_price, buy_price,))
        elif more == 0 and weighted_30s_change > 0.2 and weighted_5min_change > 0.3:
            if buyin_more(futureAPI, coin_eos.name, time_type):
                more = 1
                thread.start_new_thread(ensure_buyin_more, (futureAPI, coin_eos.name, time_type, latest_price,))
                buy_price = latest_price
                info = u'发出做多信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                    f.writelines(info + '\n')
        elif less == 0 and weighted_30s_change < -0.2 and weighted_5min_change < -0.3:
            if buyin_less(futureAPI, coin_eos.name, time_type, latest_price - 0.01):
                less = 1
                thread.start_new_thread(ensure_buyin_less, (futureAPI, coin_eos.name, time_type, latest_price,))
                buy_price = latest_price
                info = u'发出做空信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                    f.writelines(info + '\n')

        rate_info = u'weighted 30s_rate: %.3f%%, 5min_rate: %.3f%%' % (weighted_30s_change, weighted_5min_change)
        write_info = rate_info + u', ' + now_time + '\r\n'
        write_lines.append(write_info)
        if len(write_lines) >= 100:
            with codecs.open(file_deal, 'a+', 'UTF-8') as f:
                f.writelines(write_lines)
                write_lines = []

        print(rate_info + u', ' + now_time)
    except Exception as e:
        print(repr(e))
        traceback.print_exc()


def on_error(ws, error):
    traceback.print_exc()
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    print("websocket connected...")
    ws.send("{'event':'addChannel','channel':'ok_sub_spot_btc_usdt_deals'}")
    ws.send("{'event':'addChannel','channel':'ok_sub_spot_etc_usdt_deals'}")
    ws.send("{'event':'addChannel','channel':'ok_sub_spot_ltc_usdt_deals'}")
    ws.send("{'event':'addChannel','channel':'ok_sub_spot_eth_usdt_deals'}")
    ws.send("{'event':'addChannel','channel':'ok_sub_spot_eos_usdt_deals'}")
    ws.send("{'event':'addChannel','channel':'ok_sub_spot_xrp_usdt_deals'}")



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