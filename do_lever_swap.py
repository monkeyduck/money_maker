# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate, send_email, write_info_into_file
from entity import Coin, Indicator, DealEntity, INSTRUMENT_ID_LINKER
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
more = 0
last_avg_price = 0

lever_sell_time = 0
lever_sell_price = 0
lever_more_time = 0
lever_more_price = 0

swap_more_price = 0
swap_less_price = 0
swap_more_time = 0
swap_less_time = 0

swap_size = 1
swap_latest_price = 0

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
    if price_3m_change < price_1m_change <= -0.4 and price_10s_change <= -0.05 \
            and ind_1min.ask_vol > 2 * ind_1min.bid_vol and ind_1min.vol > 300000 \
            and ind_10s.ask_vol > ind_10s.bid_vol:
        return True
    return False


def check_do_future_more_test(price_3m_change, price_1m_change, price_10s_change):
    if price_3m_change < price_1m_change < -0.1 and price_10s_change <= -0.01:
        return True


def check_do_future_less_test(price_3m_change, price_1m_change, price_10s_change):
    if price_3m_change > price_1m_change > 0.1 and price_10s_change >= 0.01:
        return True


def check_do_future_more(price_3m_change, price_1m_change, price_10s_change):
    if ind_1min.vol < 100000 and price_3m_change < price_1m_change <= -0.3 and price_10s_change >= 0.03 \
            and ind_10s.bid_vol > 10 * ind_10s.ask_vol:
        return True


def do_lever_less():
    borrow_coin()
    return sell_coin()


def do_lever_more():
    borrow_usdt()
    return buy_coin()


def init_swap():
    swapAPI.set_leverage(swap_instrument_id, 5, "1")


def on_message(ws, message):
    global latest_price, last_avg_price, less, deque_3s, deque_10s, deque_min, instrument_id, \
        deque_3m, ind_1s, ind_10s, ind_1min, ind_3m, write_lines, freeze_time, swap_less_time, \
        swap_more_price, swap_more_time, more, swap_more_price, swap_less_price, swap_latest_price

    ts = time.time()
    now_time = timestamp2string(ts)

    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    json_message = json.loads(message)
    for json_data in json_message['data']:
        ins_id = json_data['instrument_id']
        if ins_id == swap_instrument_id:
            swap_latest_price = float(json_data['last'])
            continue
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

        # 做空
        if less == 0 and check_do_future_less_test(price_3m_change, price_1m_change, price_10s_change):
            i = 1
            while True:
                swap_less_order_id = do_swap_less()
                write_info_into_file('第' + str(i) + '次做空尝试, id: ' + str(swap_less_order_id), file_transaction)
                i += 1
                if swap_less_order_id:
                    swap_order_info = swapAPI.get_order_info(swap_instrument_id, swap_less_order_id)
                    write_info_into_file('做空 order info: ' + str(swap_order_info), file_transaction)
                    if swap_order_info['state'] == '2':
                        less = 1
                        swap_less_time = int(ts)
                        swap_less_price = float(swap_order_info['price_avg'])
                        thread.start_new_thread(send_email, ('合约做空，价格：' + str(swap_less_price),))
                        break
                    elif swap_order_info['state'] == '-1':
                        continue
                    else:
                        swapAPI.revoke_order(swap_less_order_id, swap_instrument_id)

        if more == 0 and check_do_future_more_test(price_3m_change, price_1m_change, price_10s_change):
            i = 1
            while True:
                swap_more_order_id = do_swap_more()
                write_info_into_file('第' + str(i) + '次做多尝试, id: ' + str(swap_more_order_id), file_transaction)
                i += 1
                if swap_more_order_id:
                    swap_order_info = swapAPI.get_order_info(swap_instrument_id, swap_more_order_id)
                    write_info_into_file('做多 order info: ' + str(swap_order_info), file_transaction)
                    if swap_order_info['state'] == '2':
                        more = 1
                        swap_more_time = int(ts)
                        swap_more_price = float(swap_order_info['price_avg'])
                        thread.start_new_thread(send_email, ('合约做多, 价格：' + str(swap_more_price),))
                        break
                    elif swap_order_info['state'] == '-1':
                        continue
                    else:
                        swapAPI.revoke_order(swap_more_order_id, swap_instrument_id)
        if less == 1:
            if int(ts) - swap_less_time > 60 and price_1m_change > 0.1:
                if stop_swap_less():
                    less = 0

        elif more == 1:
            if int(ts) - swap_more_time > 60 and price_1m_change < -0.1:
                if stop_swap_more():
                    more = 0
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
        print('less: %d, more: %d' % (less, more))
        print(price_info + '\r\n' + vol_info + '\r\n' + rate_info + u', ' + now_time)


def do_swap_more():
    swap_price_latest = float(swapAPI.get_specific_ticker(swap_instrument_id)['best_ask'])
    # take_order(self, instrument_id, size, type, order_type, price, client_oid, match_price):
    size = swap_size
    write_info_into_file('ready to swap more, size :' + str(size), file_transaction)
    swap_order_result = swapAPI.take_order(swap_instrument_id, size, 1, 0, swap_price_latest, None, None)
    time.sleep(0.5)
    if swap_order_result and swap_order_result['result']:
        swap_order_id = swap_order_result['order_id']
        write_info_into_file('合约做多订单id: ' + str(swap_order_id), file_transaction)
        return swap_order_id
    return False


def do_swap_less():
    swap_price_latest = float(swapAPI.get_specific_ticker(swap_instrument_id)['best_bid'])
    # take_order(self, instrument_id, size, type, order_type, price, client_oid, match_price):
    size = swap_size
    write_info_into_file('ready to swap less, size :' + str(size), file_transaction)
    swap_order_result = swapAPI.take_order(swap_instrument_id, size, 2, 0, swap_price_latest, None, None)
    time.sleep(0.5)
    if swap_order_result and swap_order_result['result']:
        swap_order_id = swap_order_result['order_id']
        write_info_into_file('合约做空订单id: ' + str(swap_order_id), file_transaction)
        return swap_order_id
    return False


def stop_swap_more():
    swap_price_latest = float(swapAPI.get_specific_ticker(swap_instrument_id)['best_bid'])
    size = swap_size
    swap_order_result = swapAPI.take_order(swap_instrument_id, size, 3, 0, swap_price_latest, None, None)
    time.sleep(0.5)
    if swap_order_result and swap_order_result['result'] == 'true':
        swap_order_id = swap_order_result['order_id']
        write_info_into_file('做多卖出order_id: ' + str(swap_order_id), file_transaction)
        a = swapAPI.get_order_info('EOS-USD-SWAP', swap_order_id)
        if a['state'] == '2':
            profit = float(a['price_avg']) - swap_more_price
            write_info_into_file('做多卖出成功，收益: ' + str(profit), file_transaction)
            return True
        elif a['state'] == '-1':
            return False
        else:
            swapAPI.revoke_order(swap_order_id, swap_instrument_id)
            return False
    return False


def stop_swap_less():
    swap_price_latest = float(swapAPI.get_specific_ticker(swap_instrument_id)['best_ask'])
    size = swap_size
    swap_order_result = swapAPI.take_order(swap_instrument_id, size, 4, 0, swap_price_latest, None, None)
    time.sleep(0.5)
    if swap_order_result and swap_order_result['result'] == 'true':
        swap_order_id = swap_order_result['order_id']
        write_info_into_file('做空卖出order_id: ' + str(swap_order_id), file_transaction)
        order_info = swapAPI.get_order_info('EOS-USD-SWAP', swap_order_id)
        if order_info['state'] == '2':
            profit = swap_less_price - float(order_info['price_avg'])
            write_info_into_file('做空卖出成功，收益： ' + str(profit), file_transaction)
            return True
        elif order_info['state'] == '-1':
            return False
        else:
            swapAPI.revoke_order(swap_order_id, swap_instrument_id)
            return False
    return False


def stop_lever_less():
    if buy_coin():
        return repay_coin(instrument_id.split(INSTRUMENT_ID_LINKER)[0].upper())
    else:
        return False


def stop_lever_more():
    if sell_coin():
        return repay_coin("USDT")
    else:
        return False


def borrow_coin():
    currency = instrument_id.split(INSTRUMENT_ID_LINKER)[0]
    query_available_result = leverAPI.query_lever_available(instrument_id)
    result = query_available_result[0]
    borrow_num = int(float(result['currency:' + currency.upper()]['available']))
    if borrow_num > 0:
        borrow_result = leverAPI.borrow_coin(instrument_id, currency, borrow_num)
        if borrow_result and borrow_result['result']:
            write_info_into_file('借币成功 %s，num: %s' % (currency, str(borrow_num)), file_transaction)
            return borrow_num
    else:
        write_info_into_file("无可借币", file_transaction)


def borrow_usdt():
    currency = instrument_id.split(INSTRUMENT_ID_LINKER)[1]
    query_available_result = leverAPI.query_lever_available(instrument_id)
    result = query_available_result[0]
    borrow_num = int(float(result['currency:USDT']['available']))
    if borrow_num > 0:
        borrow_result = leverAPI.borrow_coin(instrument_id, currency, borrow_num)
        if borrow_result and borrow_result['result']:
            write_info_into_file('借币成功 %s，num: %s' % (currency, str(borrow_num)), file_transaction)
            return borrow_num
    else:
        write_info_into_file("无可借币", file_transaction)


def sell_coin():
    global lever_sell_price, swap_size
    currency = instrument_id.split(INSTRUMENT_ID_LINKER)[0]
    coin_account = leverAPI.get_coin_account_info(instrument_id)
    coin_available = int(float(coin_account['currency:' + currency.upper()]['available']))
    # swap_size = int(coin_available * latest_price / 10)
    swap_size = 1
    coin_to_sell = float(swap_size * 10 / latest_price)
    if coin_to_sell >= 1:
        write_info_into_file('start to sell %s: %.2f' % (currency, coin_to_sell), file_transaction)
        sell_order_id = leverAPI.lever_sell_market(instrument_id, coin_to_sell)
        time.sleep(1)
        if sell_order_id:
            write_info_into_file('sell order id:%s' % str(sell_order_id), file_transaction)
            sell_order_info = leverAPI.get_order_info(sell_order_id, instrument_id)
            if sell_order_info['state'] == '2':
                lever_sell_price = float(sell_order_info['price_avg'])
                sell_info = '杠杆卖出成功，num: ' + str(coin_available) + ', price: ' + str(lever_sell_price)
                write_info_into_file(sell_info, file_transaction)
                thread.start_new_thread(send_email, (sell_info,))
                return True
            else:
                leverAPI.revoke_order(instrument_id, sell_order_id)
                return False
        else:
            return False
    return True


def buy_coin():
    global lever_more_price
    currency = instrument_id.split(INSTRUMENT_ID_LINKER)[0]
    account_info = leverAPI.get_coin_account_info(instrument_id)
    time.sleep(0.1)
    usdt_available = float(account_info['currency:USDT']['available'])
    amount = float(round(usdt_available / latest_price, 1))
    if usdt_available <= 1:
        return True
    buy_order_id = leverAPI.lever_buy_market(instrument_id, amount, usdt_available)
    if buy_order_id:
        time.sleep(1)
        buy_order_info = leverAPI.get_order_info(buy_order_id, instrument_id)
        if buy_order_info['state'] == '2':
            buy_info = '杠杆买入成功%s, num: %d' % (currency, amount)
            write_info_into_file(buy_info, file_transaction)
            thread.start_new_thread(send_email, (buy_info, ))
            lever_more_price = float(buy_order_info['price_avg'])
            return True
        else:
            leverAPI.revoke_order(instrument_id, buy_order_id)
            time.sleep(0.2)
            return False
    else:
        return False


def repay_coin(currency_upper):
    amount = 1
    while amount > 0:
        account_info = leverAPI.get_coin_account_info(instrument_id)
        amount = float(account_info['currency:' + currency_upper]['borrowed'])
        write_info_into_file("还币: " + str(amount), file_transaction)
        if amount > 0:
            repay_result = leverAPI.repay_coin(instrument_id, currency_upper, amount)
            if repay_result and repay_result['result']:
                write_info_into_file('还币成功，num: ' + str(amount), file_transaction)
                return True
            else:
                thread.start_new_thread(send_email, ('Warning: 尚有' + currency_upper + '欠币未还：' + str(amount),))
                return True
        else:
            return True


def on_error(ws, error):
    traceback.write_info_exc()
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    print("websocket connected...")
    ws.send("{\"op\": \"subscribe\", \"args\": [\"spot/trade:%s-USDT\"]}" % (coin.name.upper()))
    ws.send("{\"op\": \"subscribe\", \"args\": [\"swap/ticker:%s-USD-SWAP\"]}" % (coin.name.upper()))


if __name__ == '__main__':
    if len(sys.argv) > 2:
        coin_name = sys.argv[1]
        # 默认币种handle_deque
        coin = Coin(coin_name, "usdt")
        instrument_id = coin.get_instrument_id()
        future_instrument_id = coin.get_future_instrument_id()
        swap_instrument_id = coin.name.upper() + '-USD-SWAP'
        print('swap_instrument_id: ' + swap_instrument_id)
        file_transaction, file_deal = coin.gen_file_name()
        config_file = sys.argv[2]
        if config_file == 'config_mother':
            from config_mother import leverAPI, futureAPI, swapAPI
        # elif config_file == 'config_son1':
        #     from config_son1 import spotAPI, okFuture, futureAPI
        # elif config_file == 'config_son3':
        #     from config_son3 import spotAPI, okFuture, futureAPI
        else:
            print('输入config_file有误，请输入config_mother or config_son1 or config_son3')
            sys.exit()
        while True:
            ws = websocket.WebSocketApp("wss://real.OKEx.com:8443/ws/v3?compress=true",
                                        on_message=on_message,
                                        on_error=on_error,
                                        on_close=on_close)
            ws.on_open = on_open
            ws.run_forever(ping_interval=15, ping_timeout=10)

    else:
        print('缺少参数 coin_name, config_file')
        print('for example: python monitor_spot etc config_mother')