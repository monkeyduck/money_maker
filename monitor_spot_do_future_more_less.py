# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate, string2timestamp
from trade_v3 import buyin_less, sell_less, ensure_buyin_less, ensure_sell_less, get_latest_future_price, buyin_more, \
    sell_more, ensure_buyin_more, ensure_sell_more
from entity import Coin, Indicator, DealEntity
from strategy import get_spot_macd
import time
import json
import traceback
from collections import deque
import websocket
import codecs
import sys

deque_min = deque()
deque_10s = deque()
deque_3s = deque()
deque_3m = deque()
latest_price = 0
ind_1min = Indicator(60)
ind_10s = Indicator(10)
ind_1s = Indicator(1)
ind_3m = Indicator(180)
less = 0
lessless = 0
moremore = 0
last_3min_macd_ts = 0

last_avg_price = 0

future_buy_time = 0

spot_buy_time = 0
buyin_price_spot = 0
freeze_time = 0

write_lines = []


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


def check_do_future_less(price_3m_change, price_1m_change, price_10s_change):
    if ind_1min.vol > 200000 and ind_1min.ask_vol > 1.8 * ind_1min.bid_vol \
            and ind_3m.vol > 400000 and ind_3m.ask_vol > 1.5 * ind_3m.bid_vol and -1.2 < price_1m_change \
            and price_3m_change < price_1m_change < -0.3 and price_10s_change <= -0.05 and new_macd < 0:
        return True
    elif ind_1min.vol > 200000 and ind_1min.ask_vol > 2 * ind_1min.bid_vol \
            and ind_3m.vol > 250000 and ind_3m.ask_vol > 2 * ind_3m.bid_vol \
            and price_3m_change < price_1m_change < -0.3 and price_10s_change <= -0.05 \
            and new_macd < 0:
        return True
    elif ind_1min.vol > 100000 and ind_1min.ask_vol > 3 * ind_1min.bid_vol \
            and ind_3m.vol > 150000 and ind_3m.ask_vol > 2 * ind_3m.bid_vol \
            and price_3m_change < price_1m_change < -0.3 and price_10s_change <= -0.05 \
            and new_macd < 0:
        return True
    return False


def check_do_future_more(price_3m_change, price_1m_change, price_10s_change):
    if ind_1min.vol > 200000 and ind_1min.ask_vol * 2 < ind_1min.bid_vol \
            and ind_3m.vol > 250000 and ind_3m.ask_vol * 1.5 < ind_3m.bid_vol \
            and price_3m_change > price_1m_change > 0.3 and price_10s_change >= 0.05 \
            and new_macd > 0:
        return True
    elif ind_1min.vol > 100000 and ind_1min.ask_vol * 3 < ind_1min.bid_vol \
            and ind_3m.vol > 150000 and ind_3m.ask_vol * 2 < ind_3m.bid_vol \
            and price_3m_change > price_1m_change > 0.3 and price_10s_change >= 0.05 \
            and new_macd > 0:
        return True
    return False


def on_message(ws, message):
    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    if 'pong' in message or 'addChannel' in message:
        return
    global latest_price, last_avg_price, less, deque_3s, deque_10s, deque_min,\
        deque_3m, ind_1s, ind_10s, ind_1min, ind_3m, write_lines, last_3min_macd_ts, new_macd, lessless,\
        future_buy_time, buyin_price_spot, moremore, freeze_time
    jmessage = json.loads(message)

    ts = time.time()
    now_time = timestamp2string(ts)
    if int(ts) - last_3min_macd_ts > 60:
        last_3min_macd_ts = int(ts)
        df = get_spot_macd(spotAPI, instrument_id, 300)
        diff = list(df['diff'])
        dea = list(df['dea'])
        new_macd = 2 * (diff[-1] - dea[-1])
        with codecs.open(file_deal, 'a+', 'UTF-8') as f:
            f.writelines('update macd: %.6f\r\n' % new_macd)

    for each_message in jmessage:
        for jdata in each_message['data']:
            latest_price = float(jdata[1])
            deal_entity = DealEntity(jdata[0], float(jdata[1]), round(float(jdata[2]), 3), ts, jdata[4])

            handle_deque(deque_3s, deal_entity, ts, ind_1s)
            handle_deque(deque_10s, deal_entity, ts, ind_10s)
            handle_deque(deque_min, deal_entity, ts, ind_1min)
            handle_deque(deque_3m, deal_entity, ts, ind_3m)

            avg_3s_price = ind_1s.cal_avg_price()
            avg_10s_price = ind_10s.cal_avg_price()
            avg_min_price = ind_1min.cal_avg_price()
            avg_3m_price = ind_3m.cal_avg_price()
            price_10s_change = cal_rate(avg_3s_price, avg_10s_price)
            price_1m_change = cal_rate(avg_3s_price, avg_min_price)
            price_3m_change = cal_rate(avg_3s_price, avg_3m_price)

            # 做空
            if lessless == 0 and int(ts) - freeze_time > 180 and check_do_future_less(price_3m_change, price_1m_change, price_10s_change):
                latest_future_price = get_latest_future_price(futureAPI, future_instrument_id)
                if not latest_future_price:
                    latest_future_price = latest_price
                future_buyin_less_order_id = buyin_less(
                    futureAPI, coin.name, future_instrument_id, latest_future_price, amount=None, lever_rate=20, taker=True)
                if future_buyin_less_order_id:
                    lessless = 1
                    future_buy_time = int(ts)
                    buyin_price_spot = latest_price
                    thread.start_new_thread(ensure_buyin_less, (futureAPI, coin.name, future_instrument_id,
                                                                latest_future_price, future_buyin_less_order_id,))

                    info = now_time + u' 发出做空信号！！future_buy_price： ' + str(latest_future_price)
                    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                        f.writelines(info + '\n')

            if moremore == 0 and int(ts) - freeze_time > 180 and check_do_future_more(price_3m_change, price_1m_change, price_10s_change):
                latest_future_price = get_latest_future_price(futureAPI, future_instrument_id)
                if not latest_future_price:
                    latest_future_price = latest_price
                future_buyin_more_order_id = buyin_more(futureAPI, coin.name, future_instrument_id, latest_future_price,
                                                        amount=None, lever_rate=20, taker=True)
                if future_buyin_more_order_id:
                    moremore = 1
                    future_buy_time = int(ts)
                    buyin_price_spot = latest_price
                    thread.start_new_thread(ensure_buyin_more, (futureAPI, coin.name, future_instrument_id,
                                                                latest_future_price, future_buyin_more_order_id,))
                    info = now_time + u' 发出做多信号！！future_buy_price： ' + str(latest_future_price)
                    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                        f.writelines(info + '\n')
            if moremore == 1:
                if int(ts) - future_buy_time >= 60 and price_10s_change < -0.01:
                    if sell_more(futureAPI, future_instrument_id):
                        moremore = 0
                        thread.start_new_thread(ensure_sell_more, (futureAPI, coin.name, future_instrument_id,
                                                                   latest_price, buyin_price_spot))
                        info = u'做多止盈，盈利%.3f, time: %s' % (latest_price - buyin_price_spot, now_time)
                        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                            f.writelines(info + '\n')
                        freeze_time = int(ts)
                elif latest_price < buyin_price_spot * 0.99:
                    if sell_more(futureAPI, future_instrument_id):
                        moremore = 0
                        thread.start_new_thread(ensure_sell_more, (futureAPI, coin.name, future_instrument_id,
                                                                   latest_price, buyin_price_spot))
                        info = u'做多止损，亏损%.3f, time: %s' % (buyin_price_spot - latest_price, now_time)
                        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                            f.writelines(info + '\n')
                        freeze_time = int(ts)
            if lessless == 1:
                if price_1m_change > 0 and new_macd > 0:
                    if sell_less(futureAPI, future_instrument_id):
                        lessless = 0
                        thread.start_new_thread(ensure_sell_less, (futureAPI, coin.name, future_instrument_id,
                                                                   latest_price, buyin_price_spot))
                        freeze_time = int(ts)
                        info = u'做空止盈，盈利%.3f, time: %s' % (buyin_price_spot - latest_price, now_time)
                        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                            f.writelines(info + '\n')

                elif int(ts) - future_buy_time >= 60 and price_10s_change > 0.01:
                    if sell_less(futureAPI, future_instrument_id):
                        lessless = 0
                        thread.start_new_thread(ensure_sell_less, (
                            futureAPI, coin.name, future_instrument_id, latest_price, buyin_price_spot))
                        freeze_time = int(ts)
                        info = u'做空止盈，盈利%.2f, time: %s' % ((latest_price - buyin_price_spot), now_time)
                        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                            f.writelines(info + '\n')
                elif latest_price > buyin_price_spot * 1.01:
                    if sell_less(futureAPI, future_instrument_id):
                        lessless = 0
                        thread.start_new_thread(ensure_sell_less, (
                            futureAPI, coin.name, future_instrument_id, latest_price, buyin_price_spot))
                        freeze_time = int(ts)
                        info = u'做空止损，亏损%.2f, time: %s' % ((latest_price - buyin_price_spot), now_time)
                        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                            f.writelines(info + '\n')

            holding_status = 'future_less: %d, future_more: %d' % (lessless, moremore)
            price_info = deal_entity.type + u' now_price: %.4f, 3s_price: %.4f, 10s_price: %.4f, 1m_price: %.4f, ' \
                                            u'3min_price: %.4f' \
                         % (latest_price, avg_3s_price, avg_10s_price, avg_min_price, avg_3m_price)
            vol_info = u'cur_vol: %.3f, 3s vol: %.3f, 10s vol: %.3f, 1min vol: %.3f, ask_vol: %.3f, bid_vol: %.3f, ' \
                       u'3s_ask_vol: %.3f, 3s_bid_vol: %.3f, 3min vol: %.3f, 3min_ask_vol: %.3f, 3min_bid_vol: %.3f' \
                       % (deal_entity.amount, ind_1s.vol, ind_10s.vol, ind_1min.vol, ind_1min.ask_vol, ind_1min.bid_vol,
                          ind_1s.ask_vol, ind_1s.bid_vol, ind_3m.vol, ind_3m.ask_vol, ind_3m.bid_vol)
            rate_info = u'10s_rate: %.2f%%, 1min_rate: %.2f%%, 3min_rate: %.2f%%, new_macd: %.6f' \
                        % (price_10s_change, price_1m_change, price_3m_change, new_macd)
            write_info = holding_status + u', ' + price_info + u', ' + vol_info + u', ' + rate_info + u', ' + now_time + '\r\n'
            write_lines.append(write_info)
            if len(write_lines) >= 100:
                with codecs.open(file_deal, 'a+', 'UTF-8') as f:
                    f.writelines(write_lines)
                    write_lines = []

            print(holding_status + '\r\n' + price_info + '\r\n' + vol_info + '\r\n' + rate_info + u', ' + now_time)


def on_error(ws, error):
    traceback.print_exc()
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    print("websocket connected...")
    ws.send("{'event':'addChannel','channel':'ok_sub_spot_%s_usdt_deals'}" % coin.name)


if __name__ == '__main__':
    if len(sys.argv) > 2:
        coin_name = sys.argv[1]
        # 默认币种handle_deque
        coin = Coin(coin_name, "usdt")
        instrument_id = coin.get_instrument_id()
        future_instrument_id = coin.get_future_instrument_id()
        file_transaction, file_deal = coin.gen_file_name()
        config_file = sys.argv[2]
        if config_file == 'config_mother':
            from config_mother import spotAPI, okFuture, futureAPI
        elif config_file == 'config_son1':
            from config_son1 import spotAPI, okFuture, futureAPI
        elif config_file == 'config_son3':
            from config_son3 import spotAPI, okFuture, futureAPI
        else:
            print('输入config_file有误，请输入config_mother or config_son1 or config_son3')
            sys.exit()
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
    else:
        print('缺少参数 coin_name, config_file')
        print('for example: python monitor_spot etc config_mother')