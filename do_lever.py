# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate, send_email
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

last_avg_price = 0

lever_sell_time = 0
lever_sell_price = 0

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


def check_do_future_less_test(price_3m_change, price_1m_change, price_10s_change):
    if ind_1min.vol > 30000 and ind_1min.ask_vol > 1.5 * ind_1min.bid_vol \
            and ind_3m.vol > 40000 and ind_3m.ask_vol > 1.3 * ind_3m.bid_vol and -1.2 < price_1m_change \
            and price_3m_change < price_1m_change < -0.1 and price_10s_change <= -0.01:
        return True
    elif ind_1min.vol > 20000 and ind_1min.ask_vol > 2 * ind_1min.bid_vol \
            and ind_3m.vol > 30000 and ind_3m.ask_vol > 2 * ind_3m.bid_vol \
            and price_3m_change < price_1m_change < -0.1 and price_10s_change <= -0.01:
        return True
    return False


def do_lever_less():
    borrow_coin(instrument_id.split(INSTRUMENT_ID_LINKER)[0])
    write_info('start to sell coin', file_transaction)
    result = sell_coin(instrument_id.split(INSTRUMENT_ID_LINKER)[0])
    write_info('sell result: ' + result, file_transaction)


def borrow_coin(currency):
    query_available_result = leverAPI.query_lever_available(instrument_id)
    borrow_num = 0
    for result in query_available_result:
        borrow_num = int(float(result['currency:' + currency.upper()]['available']))
    if borrow_num > 0:
        borrow_result = leverAPI.borrow_coin(instrument_id, currency, borrow_num)
        if borrow_result and borrow_result['result']:
            write_info('借币成功 %s，num: %s' % (currency, str(borrow_num)), file_transaction)
            return borrow_num
    else:
        return False


def sell_coin(currency):
    coin_account = leverAPI.get_coin_account_info(instrument_id)
    write_info('sell coin, account_info: ' + coin_account, file_transaction)
    coin_available = int(float(coin_account['currency:' + currency.upper()]['available']))
    if coin_available > 0:
        sell_order_id = leverAPI.lever_sell_FOK(instrument_id, coin_available, latest_price)
        if sell_order_id:
            sell_info = '杠杆卖出%s成功, num: %d, price: %.3f' % (instrument_id.split(INSTRUMENT_ID_LINKER)[0],
                                                            coin_available, latest_price)
            write_info(sell_info, file_transaction)
            thread.start_new_thread(send_email, (sell_info,))
            return True
        else:
            return False
    return False


def buy_coin():
    account_info = leverAPI.get_coin_account_info(instrument_id)
    usdt_available = float(account_info['currency:USDT']['available'])
    amount = math.floor(usdt_available / latest_price)
    if amount > 0:
        buy_order_id = False
        while not buy_order_id:
            buy_order_id = leverAPI.lever_buy_FOK(instrument_id, amount, latest_price)
            time.sleep(0.1)
        write_info('买入成功' + instrument_id.split(INSTRUMENT_ID_LINKER)[0], file_transaction)
        return buy_order_id
    thread.start_new_thread(send_email, ('usdt余额不足，买入失败', ))
    return False


def repay_coin():
    amount = 1
    while amount > 0:
        currency = instrument_id.split(INSTRUMENT_ID_LINKER)[0].upper()
        account_info = leverAPI.get_coin_account_info(instrument_id)
        write_info('还币, account_info:' + account_info, file_transaction)
        amount = float(account_info['currency:' + currency]['borrowed'])
        if amount > 0:
            repay_result = leverAPI.repay_coin(instrument_id, currency, amount)
            if repay_result and repay_result['result']:
                return True
            else:
                thread.start_new_thread(send_email, ('Warning: 尚有欠币未还：' + str(amount),))
                return True
        else:
            return True


def stop_lever_less():
    buy_coin()
    return repay_coin()


def write_info(info, file_name):
    print(info)
    with codecs.open(file_name, 'a+', 'utf-8') as f:
        f.writelines(info + '\n')


def on_message(ws, message):
    global latest_price, last_avg_price, less, deque_3s, deque_10s, deque_min,\
        deque_3m, ind_1s, ind_10s, ind_1min, ind_3m, write_lines, freeze_time, lever_sell_time, lever_sell_price

    ts = time.time()
    now_time = timestamp2string(ts)

    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    json_message = json.loads(message)
    for json_data in json_message['data']:
        print(json_data)
        latest_price = float(json_data['price'])
        deal_entity = DealEntity(json_data['trade_id'], latest_price, round(float(json_data['size']), 3), ts,
                                 json_data['side'])

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
        price_change_3m_ago = cal_rate(latest_price, deque_3m[0].price)
        print('price change 3m ago: %.3f%%' % price_change_3m_ago)

        # 做空
        if less == 0 and price_change_3m_ago > -5 \
                and check_do_future_less_test(price_3m_change, price_1m_change, price_10s_change):
            if do_lever_less():
                less = 1
                lever_sell_time = int(ts)
                lever_sell_price = latest_price
        if less == 1:
            if price_1m_change > 0 and int(ts) - lever_sell_time > 120:
                if stop_lever_less():
                    less = 0

            elif int(ts) - lever_sell_time > 60 and latest_price > lever_sell_price:
                if stop_lever_less():
                    less = 0

        price_info = deal_entity.type + u' now_price: %.4f, 3s_price: %.4f, 10s_price: %.4f, 1m_price: %.4f, ' \
                                        u'3min_price: %.4f' % (latest_price, avg_3s_price, avg_10s_price, avg_min_price,
                                                               avg_3m_price)
        vol_info = u'cur_vol: %.3f, 3s vol: %.3f, 10s vol: %.3f, 1min vol: %.3f, ask_vol: %.3f, bid_vol: %.3f, ' \
                   u'3s_ask_vol: %.3f, 3s_bid_vol: %.3f, 3min vol: %.3f, 3min_ask_vol: %.3f, 3min_bid_vol: %.3f' \
                   % (deal_entity.amount, ind_1s.vol, ind_10s.vol, ind_1min.vol, ind_1min.ask_vol, ind_1min.bid_vol,
                      ind_1s.ask_vol, ind_1s.bid_vol, ind_3m.vol, ind_3m.ask_vol, ind_3m.bid_vol)
        rate_info = u'10s_rate: %.2f%%, 1min_rate: %.2f%%, 3min_rate: %.2f%%' \
                    % (price_10s_change, price_1m_change, price_3m_change)
        print_message = price_info + u', ' + vol_info + u', ' + rate_info + u', ' + now_time + '\r\n'
        write_lines.append(print_message)
        if len(write_lines) >= 100:
            with codecs.open(file_deal, 'a+', 'UTF-8') as f:
                f.writelines(write_lines)
                write_lines = []

        print(price_info + '\r\n' + vol_info + '\r\n' + rate_info + u', ' + now_time)


def on_error(ws, error):
    traceback.write_info_exc()
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    print("websocket connected...")
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

    else:
        print('缺少参数 coin_name, config_file')
        print('for example: python monitor_spot etc config_mother')