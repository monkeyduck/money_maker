#!/usr/bin/python
# -*- coding: UTF-8 -*-

import json
import math
from utils import send_email,timestamp2string
import time
import codecs
try:
    import thread
except ImportError:
    import _thread as thread


batch_size = 400


def gen_orders_data(price, amount, trade_type, num):
    each_amount = int(amount / num)
    ret_data = "{price:%.3f,size:%d,type:%d,match_price:1}" % (price, each_amount, trade_type)
    data_list = [ret_data] * num
    orders_data = "[" + ",".join(data_list) + "]"
    return orders_data


def buyin_more(futureAPI, coin_name, time_type, buy_price=None, amount=None, lever_rate=20):
    if not amount:
        result = futureAPI.get_coin_account(coin_name)
        balance = float(result['total_avail_balance'])
        amount = math.floor(balance * lever_rate * buy_price / 10)

    turn = int(amount / batch_size)

    if turn == 0 and amount >= 1:
        if buy_price:
            ret = futureAPI.take_order('', time_type, 1, buy_price, amount, 0, lever_rate)
        else:
            ret = futureAPI.take_order('', time_type, 1, buy_price, amount, 1, lever_rate)
        print(ret)

        if ret and ret['result']:
            email_msg = "下单做多%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                        % (coin_name, buy_price, amount, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            return ret["order_id"]
    else:
        amount -= turn * batch_size
        while turn > 0:
            futureAPI.take_order('', time_type, 1, buy_price, batch_size, 1, lever_rate)
            time.sleep(0.3)
            turn -= 1
        while amount >= 1:
            ret = futureAPI.take_order('', time_type, 1, buy_price, amount, 1, lever_rate)
            print(ret)

            if ret and ret['result']:
                email_msg = "下单做多%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                            % (coin_name, buy_price, amount, timestamp2string(time.time()), ret)
                thread.start_new_thread(send_email, (email_msg,))
                return ret["order_id"]
            amount = math.floor(amount * 0.95)
            time.sleep(1)
    return True


def buyin_less(futureAPI, coin_name, time_type, buy_price=None, amount=None, lever_rate=20):
    result = futureAPI.get_coin_account(coin_name)
    balance = float(result['total_avail_balance'])
    if not amount:
        amount = math.floor(balance * lever_rate * buy_price / 10)

    turn = int(amount / batch_size)

    if turn == 0 and amount >= 1:
        if buy_price:
            ret = futureAPI.take_order('', time_type, 2, buy_price, amount, 0, lever_rate)
        else:
            ret = futureAPI.take_order('', time_type, 2, buy_price, amount, 1, lever_rate)
        print(ret)

        if ret and ret['result']:
            email_msg = "下单做空%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                        % (coin_name, buy_price, amount, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            return ret["order_id"]
    else:
        amount -= turn * batch_size
        while turn > 0:
            futureAPI.take_order('', time_type, 2, '', batch_size, 1, lever_rate)
            time.sleep(0.3)
            turn -= 1
        while amount >= 1:
            ret = futureAPI.take_order('', time_type, 2, buy_price, amount, 1, lever_rate)
            print(ret)

            if ret and ret['result']:
                email_msg = "下单做空%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                            % (coin_name, buy_price, amount, timestamp2string(time.time()), ret)
                thread.start_new_thread(send_email, (email_msg,))
                return ret["order_id"]
            amount = math.floor(amount * 0.95)
            time.sleep(1)
    return True


# status 0 wait to deal, status 1 part dealed
def acquire_orderId_by_type(futureAPI, time_type, order_type):
    ret = futureAPI.get_order_list(0, None, None, None, time_type)
    order_id_list = []
    for each_order in ret["order_info"]:
        if order_type == 0:
            order_id_list.append(str(each_order['order_id']))
        elif int(each_order['type']) == order_type:
            order_id_list.append(str(each_order['order_id']))
    ret = futureAPI.get_order_list(1, None, None, None, time_type)
    for each_order in ret["order_info"]:
        if order_type == 0:
            order_id_list.append(str(each_order['order_id']))
        elif int(each_order['type']) == order_type:
            order_id_list.append(str(each_order['order_id']))
    return order_id_list


# status_code,1:未完成的订单 2:已完成的订单
def cancel_uncompleted_order(futureAPI, coin_name, time_type, order_type=0):
    order_id_list = acquire_orderId_by_type(futureAPI, time_type, order_type)
    if len(order_id_list) > 0:
        ret = futureAPI.revoke_orders(time_type, order_id_list)
        print(ret)
        if ret and ret['result']:
            return True
        else:
            time.sleep(1)
            return cancel_uncompleted_order(futureAPI, coin_name, time_type, order_type)
    return False


def ensure_buyin_more(futureAPI, coin_name, time_type, price):
    retry = 3
    while retry > 0:
        time.sleep(3)
        retry -= 1
        cancel_uncompleted_order(futureAPI, coin_name, time_type, 1)
        if not buyin_more_batch(futureAPI, coin_name, time_type, price, 20):
            break
    time.sleep(5)
    cancel_uncompleted_order(futureAPI, coin_name, time_type, 1)


def ensure_buyin_less(futureAPI, coin_name, time_type, price):
    retry = 3
    while retry > 0:
        time.sleep(3)
        retry -= 1
        cancel_uncompleted_order(futureAPI, coin_name, time_type, 2)
        if not buyin_less_batch(futureAPI, coin_name, time_type, price, 20):
            break
    time.sleep(5)
    cancel_uncompleted_order(futureAPI, coin_name, time_type, 2)


def ensure_sell_more(futureAPI, coin_name, time_type, latest_price, buy_price, lever_rate=20):
    sleep_time = 10
    while sleep_time > 0:
        time.sleep(sleep_time)
        jRet = futureAPI.get_specific_position(time_type)

        if len(jRet["holding"]) > 0:
            cancel_uncompleted_order(futureAPI, coin_name, time_type)
            time.sleep(1)
            jRet = futureAPI.get_specific_position(time_type)
            buy_available = int(jRet["holding"][0]["long_avail_qty"])
            futureAPI.take_order('', time_type, 3, latest_price, buy_available, 1, lever_rate)
        else:
            break
    ts = time.time()
    now_time = timestamp2string(ts)
    info = u'做多卖出成功！！！卖出价格：' + str(latest_price) + u', 收益: ' + str(latest_price - buy_price) \
           + ', ' + now_time
    thread.start_new_thread(send_email, (info,))
    file_transaction = coin_name + '_future_transaction.txt'
    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
        f.writelines(info + '\n')


def ensure_sell_less(futureAPI, coin_name, time_type, latest_price, buy_price, lever_rate=20):
    sleep_time = 10
    while sleep_time > 0:
        time.sleep(sleep_time)
        jRet = futureAPI.get_specific_position(time_type)

        if len(jRet["holding"]) > 0:
            cancel_uncompleted_order(futureAPI, coin_name, time_type)
            time.sleep(1)
            jRet = futureAPI.get_specific_position(time_type)
            buy_available = int(jRet["holding"][0]["short_avail_qty"])
            futureAPI.take_order('', time_type, 4, latest_price, buy_available, 1, lever_rate)
        else:
            break
    ts = time.time()
    now_time = timestamp2string(ts)
    info = u'做空卖出成功！！！卖出价格：' + str(latest_price) + u', 收益: ' + str(buy_price - latest_price) \
           + ', ' + now_time
    thread.start_new_thread(send_email, (info,))
    file_transaction = coin_name + '_future_transaction.txt'
    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
        f.writelines(info + '\n')


def buyin_more_batch(futureAPI, coin_name, time_type, latest_price, lever_rate=20, amount=None):
    result = futureAPI.get_coin_account(coin_name)
    balance = float(result['total_avail_balance'])
    if not amount:
        amount = math.floor(balance * lever_rate * latest_price / 10)
    while amount >= 5:
        order_data = gen_orders_data(latest_price, amount, 1, 5)
        ret = futureAPI.take_orders(time_type, order_data, lever_rate)
        if ret and ret['result']:
            email_msg = "批量下单做多%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                        % (coin_name, latest_price, amount, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            return True
        amount *= math.floor(amount * 0.95)
    return False


def buyin_less_batch(futureAPI, coin_name, time_type, latest_price, lever_rate=20, amount=None):
    result = futureAPI.get_coin_account(coin_name)
    balance = float(result['total_avail_balance'])
    if not amount:
        amount = math.floor(balance * lever_rate * latest_price / 10)
    while amount >= 5:
        order_data = gen_orders_data(latest_price, amount, 2, 5)
        ret = futureAPI.take_orders(time_type, order_data, lever_rate)
        if ret and ret['result']:
            email_msg = "批量下单做空%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                        % (coin_name, latest_price, amount, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            return True
        amount *= math.floor(amount * 0.95)
    return False


def sell_more_batch(futureAPI, time_type, latest_price, lever_rate=20):
    jRet = futureAPI.get_specific_position(time_type)
    print(jRet)
    while len(jRet["holding"]) > 0:
        amount = int(jRet["holding"][0]["long_avail_qty"])
        turn = int(amount / batch_size)
        if turn == 0:
            ret = futureAPI.take_order('', time_type, 3, latest_price, amount, 1, lever_rate)
            print(ret)
            if ret and ret['result']:
                break
            else:
                return False
        else:
            amount -= turn * batch_size
            while turn > 0:
                futureAPI.take_order('', time_type, 3, latest_price, batch_size, 1, lever_rate)
                time.sleep(0.1)
                turn -= 1
            ret = futureAPI.take_order('', time_type, 3, latest_price, amount, 1, lever_rate)
            if ret and ret['result']:
                break
            else:
                return False
    return True


def sell_less_batch(futureAPI, time_type, latest_price, lever_rate=20):
    jRet = futureAPI.get_specific_position(time_type)
    print(jRet)
    while len(jRet["holding"]) > 0:
        amount = int(jRet["holding"][0]["short_avail_qty"])
        turn = int(amount / batch_size)
        if turn == 0:
            ret = futureAPI.take_order('', time_type, 4, latest_price, amount, 1, lever_rate)
            print(ret)
            if ret and ret['result']:
                break
            else:
                return False
        else:
            amount -= turn * batch_size
            while turn > 0:
                futureAPI.take_order('', time_type, 4, latest_price, batch_size, 1, lever_rate)
                time.sleep(0.1)
                turn -= 1
            ret = futureAPI.take_order('', time_type, 4, latest_price, amount, 1, lever_rate)
            if ret and ret['result']:
                break
            else:
                return False
    return True


if __name__ == '__main__':

    from config_strict import futureAPI
    time_type = "ETC-USD-190329"
    coin_name = "etc"
    # future api test
    # result = buyin_more_batch(futureAPI, coin_name, time_type, 7, 20, 5)
    # result = futureAPI.get_coin_account("etc")
    # result = buyin_less(futureAPI, coin_name, time_type, 6.4, 1, 20)
    # result = futureAPI.get_order_info("1837919127969793", time_type)
    # order_list = []
    # oid = buyin_less(futureAPI, coin_name, time_type, 7.55, 1, 20)
    # if sell_less_batch(futureAPI, time_type, 7.43):
    #     print('sucess')
    # if buyin_more(futureAPI, coin_name, time_type, 7.4)
    # order_list.append(oid)
    # oid = buyin_less(futureAPI, coin_name, time_type, 8.55, 1, 20)
    # order_list.append(oid)
    # time.sleep(10)
    # cancel_uncompleted_order(futureAPI, coin_name, time_type, 0)
    # print(result)
    # result = sell_less_batch(futureAPI, time_type, 7.55)
    # print(result)
    # result = futureAPI.get_specific_position("ETC-USD-181228")
    # result = "{'result': True, 'holding': [{'long_qty': '0', 'long_avail_qty': '0', 'long_margin': '0', 'long_liqui_price': '0', 'long_pnl_ratio': '-0.169', 'long_avg_cost': '7.619', 'long_settlement_price': '7.619', 'realised_pnl': '-0.346', 'short_qty': '2', 'short_avail_qty': '2', 'short_margin': '0.132', 'short_liqui_price': '7.869', 'short_pnl_ratio': '0', 'short_avg_cost': '7.555', 'short_settlement_price': '7.555', 'instrument_id': 'ETC-USD-181228', 'long_leverage': '20', 'short_leverage': '20', 'created_at': '2018-11-05T08:39:15.0Z', 'updated_at': '2018-11-15T08:30:34.0Z', 'margin_mode': 'fixed'}], 'margin_mode': 'fixed'}"
    # print(result)
    # print(result['total_avail_balance'])
    # result = "{'total_avail_balance': '4.159', 'contracts': [{'available_qty': '4.159', 'fixed_balance': '0.479', 'instrument_id': 'ETC-USD-181228', 'margin_for_unfilled': '0.00000014', 'margin_frozen': '0.132', 'realized_pnl': '-0.346', 'unrealized_pnl': '0'}], 'equity': '4.292', 'margin_mode': 'fixed'}"
    # print(result)
    #result = futureAPI.get_coin_account('btc')
    #result = futureAPI.get_leverage('btc')
    #result = futureAPI.set_leverage(symbol='BTC', instrument_id='BCH-USD-181026', direction=1, leverage=10)

    # orders = []
    # order1 = {"type": "2", "price": "7", "size": "1", "match_price": "1"}
    # order2 = {"type": "2", "price": "7", "size": "1", "match_price": "1"}
    # orders.append(order1)
    # orders.append(order2)
    # orders_data = json.dumps(orders)
    # print(orders_data)
    # orders_data = gen_orders_data(7,2,2,2)
    # result = futureAPI.take_orders('ETC-USD-181228', orders_data=orders_data, leverage=20)
    # print(result)

    #result = futureAPI.get_ledger('btc')
    #result = futureAPI.get_products()
    #result = futureAPI.get_depth('BTC-USD-181019', 1)
    #result = futureAPI.get_ticker()
    # result = futureAPI.get_specific_ticker('ETC-USD-190329')

    #result = futureAPI.get_specific_ticker('ETC-USD-181026')
    #result = futureAPI.get_trades('ETC-USD-181026', 1, 3, 10)
    result = futureAPI.get_kline('ETC-USD-190329', 60)
    #result = futureAPI.get_index('EOS-USD-181019')
    #result = futureAPI.get_products()
    # result = futureAPI.take_order("ccbce5bb7f7344288f32585cd3adf357", time_type,'2','7.1','1','1','20')
    # result = futureAPI.take_order("ccbce5bb7f7344288f32585cd3adf351",time_type,2,7.55,1,0,20)
    print(result)

    #result = futureAPI.get_trades('BCH-USD-181019')
    #result = futureAPI.get_rate()
    #result = futureAPI.get_estimated_price('BTC-USD-181019')
    #result = futureAPI.get_holds('BTC-USD-181019')
    #result = futureAPI.get_limit('BTC-USD-181019')
    #result = futureAPI.get_liquidation('BTC-USD-181019', 0)
    #result = futureAPI.get_holds_amount('BCH-USD-181019')
    #result = futureAPI.get_currencies()