# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate, string2timestamp
from trade_spot_v3 import buy_all_position, sell_all_position
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
ind_3s = Indicator(1)
ind_3m = Indicator(180)
less = 0
last_3min_macd_ts = 0

last_avg_price = 0
buy_price = 0


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


def on_message(ws, message):
    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    if 'pong' in message or 'addChannel' in message:
        return
    global latest_price, last_avg_price, buy_price, less, deque_3s, deque_10s, deque_min, \
        deque_3m, ind_3s, ind_10s, ind_1min, ind_3m, write_lines, last_3min_macd_ts, new_macd
    jmessage = json.loads(message)

    ts = time.time()
    now_time = timestamp2string(ts)
    if int(ts) - last_3min_macd_ts > 180:
        print('now: %s' % ts)
        df = get_spot_macd(spotAPI, instrument_id, 300)
        diff = list(df['diff'])
        dea = list(df['dea'])
        new_macd = 2 * (diff[-1] - dea[-1])
        last_3min_macd_ts = int(ts)

    for each_message in jmessage:
        for jdata in each_message['data']:
            latest_price = float(jdata[1])
            deal_entity = DealEntity(jdata[0], float(jdata[1]), round(float(jdata[2]), 3), ts, jdata[4])

            handle_deque(deque_3s, deal_entity, ts, ind_3s)
            handle_deque(deque_10s, deal_entity, ts, ind_10s)
            handle_deque(deque_min, deal_entity, ts, ind_1min)
            handle_deque(deque_3m, deal_entity, ts, ind_3m)

            avg_3s_price = ind_3s.cal_avg_price()
            avg_10s_price = ind_10s.cal_avg_price()
            avg_min_price = ind_1min.cal_avg_price()
            avg_3m_price = ind_3m.cal_avg_price()
            price_10s_change = cal_rate(avg_3s_price, avg_10s_price)
            price_1m_change = cal_rate(avg_3s_price, avg_min_price)
            price_3m_change = cal_rate(avg_3s_price, avg_3m_price)

            if ind_3m.vol > 500000 and ind_3m.ask_vol > ind_3m.bid_vol \
                    and ind_1min.vol > 300000 and ind_1min.ask_vol > ind_1min.bid_vol and price_3m_change < -0.4 and new_macd < 0:
                sell_id = sell_all_position(spotAPI, instrument_id, latest_price - 0.001)
                if sell_id:
                    time.sleep(1)
                    sell_order_info = spotAPI.get_order_info(sell_id, instrument_id)
                    if sell_order_info['status'] == 'filled' or sell_order_info['status'] == 'part_filled':
                        less = 1
                        buy_price = sell_order_info['price']
                        info = u'全部卖出！！！平均成交价格：' + buy_price + u', ' + now_time
                        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                            f.writelines(info + '\n')
                    else:
                        spotAPI.revoke_order_exception(instrument_id, sell_id)
            elif less == 1 and price_3m_change > 0 and new_macd > 0:
                buy_id = buy_all_position(spotAPI, instrument_id, latest_price)
                if buy_id:
                    time.sleep(3)
                    order_info = spotAPI.get_order_info(buy_id, instrument_id)
                    if order_info['status'] == 'filled':
                        less = 0
                        buy_price = order_info['price']
                        info = u'全部买入！！！买入价格：' + str(buy_price) + u', ' + now_time
                        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                            f.writelines(info + '\n')
                    else:
                        attempts = 5
                        while attempts > 0:
                            attempts -= 1
                            spotAPI.revoke_order_exception(instrument_id, buy_id)
                            time.sleep(1)
                            order_info = spotAPI.get_order_info(buy_id, instrument_id)
                            if order_info['status'] == 'cancelled':
                                break


            price_info = deal_entity.type + u' now_price: %.4f, 3s_price: %.4f, 10s_price: %.4f, 1m_price: %.4f, ' \
                                            u'3min_price: %.4f' \
                         % (latest_price, avg_3s_price, avg_10s_price, avg_min_price, avg_3m_price)
            vol_info = u'cur_vol: %.3f, 3s vol: %.3f, 10s vol: %.3f, 1min vol: %.3f, ask_vol: %.3f, bid_vol: %.3f, ' \
                       u'3s_ask_vol: %.3f, 3s_bid_vol: %.3f, 3min vol: %.3f, 3min_ask_vol: %.3f, 3min_bid_vol: %.3f' \
                       % (deal_entity.amount, ind_3s.vol, ind_10s.vol, ind_1min.vol, ind_1min.ask_vol, ind_1min.bid_vol,
                          ind_3s.ask_vol, ind_3s.bid_vol, ind_3m.vol, ind_3m.ask_vol, ind_3m.bid_vol)
            rate_info = u'10s_rate: %.2f%%, 1min_rate: %.2f%%, 3min_rate: %.2f%%' \
                        % (price_10s_change, price_1m_change, price_3m_change)
            write_info = price_info + u', ' + vol_info + u', ' + rate_info + u', ' + now_time + '\r\n'
            write_lines.append(write_info)
            if len(write_lines) >= 100:
                with codecs.open(file_deal, 'a+', 'UTF-8') as f:
                    f.writelines(write_lines)
                    write_lines = []

            print(price_info + '\r\n' + vol_info + '\r\n' + rate_info + u', ' + now_time)


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
        file_transaction, file_deal = coin.gen_file_name()
        config_file = sys.argv[2]
        if config_file == 'config_mother':
            from config_mother import spotAPI
        elif config_file == 'config_son1':
            from config_son1 import spotAPI
        elif config_file == 'config_son3':
            from config_son3 import spotAPI
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