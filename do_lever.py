# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate, string2timestamp
from entity import Coin, Indicator, DealEntity, INSTRUMENT_ID_LINKER
import time
import json
import traceback
from collections import deque
import websocket
import codecs
import sys
import math

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
    if ind_1min.vol > 300000 and ind_1min.ask_vol > 1.5 * ind_1min.bid_vol \
            and ind_3m.vol > 400000 and ind_3m.ask_vol > 1.3 * ind_3m.bid_vol and -1.2 < price_1m_change \
            and price_3m_change < price_1m_change < -0.3 and price_10s_change <= -0.05:
        return True
    elif ind_1min.vol > 200000 and ind_1min.ask_vol > 2 * ind_1min.bid_vol \
            and ind_3m.vol > 300000 and ind_3m.ask_vol > 2 * ind_3m.bid_vol \
            and price_3m_change < price_1m_change < -0.3 and price_10s_change <= -0.05:
        return True
    return False


def do_lever_less():
    borrow_num = borrow_coin(instrument_id.split(INSTRUMENT_ID_LINKER)[0])
    if borrow_num:
        write_info('借币成功,' + instrument_id.split(INSTRUMENT_ID_LINKER)[0] + ', num:' + borrow_num)
        sell_order_id = False
        while not sell_order_id:
            sell_order_id = sell_all_coin(instrument_id)
            time.sleep(0.5)
        write_info('卖出成功' + instrument_id.split(INSTRUMENT_ID_LINKER)[0])
        return sell_order_id
    else:
        write_info("借币失败！")
        return False


def sell_all_coin():
    coin_account = leverAPI.get_coin_account_info(instrument_id.split(INSTRUMENT_ID_LINKER)[0])
    coin_available = int(coin_account['available'])
    if coin_available > 1:
        return leverAPI.lever_sell_market(instrument_id, coin_available)
    else:
        return False


def buy_coin(price):
    account_info = leverAPI.get_coin_account_info(instrument_id)
    usdt_available = float(account_info['currency:USDT']['available'])
    amount = math.floor(usdt_available / price)
    if amount > 0:
        buy_order_id = False
        while not buy_order_id:
            buy_order_id = leverAPI.lever_buy_FOK(instrument_id, amount, price)
            time.sleep(0.2)
        write_info('买入成功' + instrument_id.split(INSTRUMENT_ID_LINKER)[0])
        return buy_order_id
    return False


def repay_coin():
    amount = 1
    while amount > 0:
        currency = instrument_id.split(INSTRUMENT_ID_LINKER)[0].upper()
        account_info = leverAPI.get_coin_account_info(instrument_id)
        amount = float(account_info['currency:' + currency]['borrowed'])
        if amount > 0:
            repay_result = leverAPI.repay_coin(instrument_id, currency, amount)
            if repay_result and repay_result['result']:
                return True
        else:
            return True


def stop_lever_less(price):
    buy_order_id = buy_coin(price)
    if buy_order_id:
        return repay_coin()


def borrow_coin(currency):
    try:
        query_available_result = leverAPI.query_lever_available(instrument_id)
        write_info('query available result: %s', query_available_result)
        borrow_num = 0
        for result in query_available_result:
            borrow_num = int(result['currency:' + currency.upper()]['available'])
        if borrow_num > 0:
            borrow_result = leverAPI.borrow_coin(instrument_id, currency, borrow_num)
            write_info('borrow result: %s', borrow_result)
            if borrow_result and borrow_result['result']:
                return borrow_num
        else:
            return False
    except Exception as e:
        write_info(repr(e))
        return False


def write_info(info):
    print(info)
    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
        f.writelines(info + '\n')


def on_message(ws, message):
    global latest_price, last_avg_price, less, deque_3s, deque_10s, deque_min,\
        deque_3m, ind_1s, ind_10s, ind_1min, ind_3m, write_lines, last_3min_macd_ts, new_macd, lessless,\
        future_buy_time, buyin_price_spot, moremore, freeze_time

    ts = time.time()
    now_time = timestamp2string(ts)

    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    json_message = json.loads(message)
    for json_data in json_message['data']:
        json_data = {'side': 'buy', 'trade_id': '4879570', 'price': '4.836', 'size': '103.6', 'instrument_id': 'EOS-USDT', 'timestamp': '2020-02-16T03:44:30.503Z'}
        trade_side = json_data['side']
        trade_id = json_data['trade_id']
        trade_price = json_data['price']
        trade_size = json_data['size']
        trade_time = json_data['timestamp']
        # +8h，转成北京时间
        trade_time_local = int(time.mktime(time.strptime(trade_time, "%Y-%m-%dT%H:%M:%S.%fZ"))) + 8 * 3600
        deal_entity = DealEntity(trade_id, trade_price, trade_size, trade_time_local, trade_side)
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
        price_change_3m_ago = cal_rate(latest_price, deque_3m[0])
        write_info("3min ago change: %.2f%%" % price_change_3m_ago)


def on_error(ws, error):
    traceback.write_info_exc()
    write_info(error)


def on_close(ws):
    write_info("### closed ###")


def on_open(ws):
    write_info("websocket connected...")
    ws.send("{\"op\": \"subscribe\", \"args\": [\"spot/trade:%s-USDT\"]}" % (coin.name.upper()))


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
            from config_mother import leverAPI
        # elif config_file == 'config_son1':
        #     from config_son1 import spotAPI, okFuture, futureAPI
        # elif config_file == 'config_son3':
        #     from config_son3 import spotAPI, okFuture, futureAPI
        else:
            print('输入config_file有误，请输入config_mother or config_son1 or config_son3')
            sys.exit()

        while True:
            ws = websocket.WebSocketApp("wss://real.okex.com:10442/ws/v3?compress=true",
                                        on_message=on_message,
                                        on_error=on_error,
                                        on_close=on_close)
            ws.on_open = on_open
            ws.run_forever(ping_interval=15, ping_timeout=10)
            print("write left lines into file...")
            with codecs.open(file_deal, 'a+', 'UTF-8') as f:
                f.writelines(write_lines)
                write_lines = []
    else:
        print('缺少参数 coin_name, config_file')
        print('for example: python monitor_spot etc config_mother')