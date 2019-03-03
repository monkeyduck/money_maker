#!/usr/bin/python
# -*- coding: UTF-8 -*-

import json
import math
from utils import send_email, timestamp2string
import time
import codecs
import traceback
import os
from entity import Coin
try:
    import thread
except ImportError:
    import _thread as thread


batch_size = 1200
trade_log_path = os.getcwd() + '/trade_v3.log'


def log_trade_v3(log):
    print(log)
    with codecs.open(trade_log_path, 'a+', 'utf-8') as f:
        f.writelines(log + '\r\n')


def gen_orders_data(price, amount, trade_type, num):
    each_amount = int(amount / num)
    ret_data = "{price:%.3f,size:%d,type:%d,match_price:1}" % (price, each_amount, trade_type)
    data_list = [ret_data] * num
    orders_data = "[" + ",".join(data_list) + "]"
    return orders_data


def buyin_more(futureAPI, coin_name, time_type, buy_price=None, amount=None, lever_rate=20):
    try:
        if not amount:
            result = futureAPI.get_coin_account(coin_name)
            balance = float(result['equity'])
            amount = math.floor(balance * lever_rate * buy_price / 10)

        turn = int(amount / batch_size)

        if turn == 0 and amount >= 1:
            if buy_price:
                ret = futureAPI.take_order('', time_type, 1, buy_price, amount, 0, lever_rate)
            else:
                ret = futureAPI.take_order('', time_type, 1, buy_price, amount, 1, lever_rate)
            log_trade_v3(ret)

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
                log_trade_v3(ret)

                if ret and ret['result']:
                    email_msg = "下单做多%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                                % (coin_name, buy_price, amount, timestamp2string(time.time()), ret)
                    thread.start_new_thread(send_email, (email_msg,))
                    return ret["order_id"]
                amount = math.floor(amount * 0.95)
                time.sleep(1)
        return True
    except Exception as e:
        info = traceback.format_exc()
        log_trade_v3("In future buyinmore func, info: %s" % info)
        return False


def buyin_less(futureAPI, coin_name, time_type, buy_price, amount=None, lever_rate=20, taker=True):
    ts = time.time()
    now_time = timestamp2string(ts)
    try:
        coin_account = futureAPI.get_coin_account(coin_name)
        balance = float(coin_account['equity'])
        if balance < 1:
            log_trade_v3("In future buyin_less function, available balance less than 1, balance: %.2f" % balance)
            return False
        if not amount:
            amount = math.floor(balance * lever_rate * (buy_price - 0.1) / 10 * 0.95)
            log_trade_v3('In buyin_less function, plan to buyin amount: %d' % amount)

        if amount >= 1:
            if taker:
                ret = futureAPI.take_order('', time_type, 2, buy_price, amount, 1, lever_rate)
            else:
                ret = futureAPI.take_order('', time_type, 2, buy_price, amount, 0, lever_rate)

            log_trade_v3('In future_buyin_less function: %s, time: %s' % (ret, now_time))

            if ret and ret['result']:
                email_msg = "下单做空%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                            % (coin_name, buy_price, amount, now_time, ret)
                thread.start_new_thread(send_email, (email_msg,))
                return ret["order_id"]
        else:
            return False
    except Exception as e:
        info = traceback.format_exc()
        log_trade_v3("In future buyinless func, info: %s" % info)
        return False


def buyin_less_turn(futureAPI, coin_name, time_type, buy_price, amount=None, lever_rate=20, taker=True):
    try:
        coin_account = futureAPI.get_coin_account(coin_name)
        balance = float(coin_account['equity'])
        if not amount:
            amount = math.floor(balance * lever_rate * (buy_price - 0.1) / 10 * 0.95)

        turn = int(amount / batch_size)
        ts = time.time()
        now_time = timestamp2string(ts)

        if turn == 0 and amount >= 1:
            if taker:
                ret = futureAPI.take_order('', time_type, 2, buy_price, amount, 1, lever_rate)
            else:
                ret = futureAPI.take_order('', time_type, 2, buy_price, amount, 0, lever_rate)

            log_trade_v3('In future_buyin_less funciton: %s, time: %s' % (ret, now_time))

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
                log_trade_v3(ret)

                if ret and ret['result']:
                    email_msg = "下单做空%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                                % (coin_name, buy_price, amount, timestamp2string(time.time()), ret)
                    thread.start_new_thread(send_email, (email_msg,))
                    return ret["order_id"]
                amount = math.floor(amount * 0.95)
                time.sleep(1)
        return True
    except Exception as e:
        log_trade_v3(repr(e))
        return False


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
        log_trade_v3(ret)
        if ret and ret['result']:
            return True
        else:
            time.sleep(1)
            return cancel_uncompleted_order(futureAPI, coin_name, time_type, order_type)
    return False


def ensure_buyin_more(futureAPI, coin_name, time_type, price):
    try:
        retry = 3
        while retry > 0:
            time.sleep(2)
            retry -= 1
            cancel_uncompleted_order(futureAPI, coin_name, time_type, 1)
            time.sleep(1)
            if not buyin_more_batch(futureAPI, coin_name, time_type, price, 20):
                break
        time.sleep(5)
        cancel_uncompleted_order(futureAPI, coin_name, time_type, 1)
    except Exception as e:
        log_trade_v3("In ensure_buyin_more function, error: %s" % repr(e))
        return


def ensure_buyin_less(futureAPI, coin_name, time_type, buy_price, lever_rate=20):
    try:
        retry = 3
        while retry > 0:
            time.sleep(2)
            retry -= 1
            cancel_uncompleted_order(futureAPI, coin_name, time_type, 2)
            time.sleep(1)
            coin_account = futureAPI.get_coin_account(coin_name)
            balance = float(coin_account['total_avail_balance'])
            # 撤销所有未完成挂单后，若balance<1则认为已全仓买入
            if balance < 1:
                return
            amount = math.floor(balance * lever_rate * (buy_price - 0.1) / 10 * 0.95)
            if not buyin_less_batch(futureAPI, coin_name, time_type, buy_price, 20, amount):
                break
        time.sleep(5)
        cancel_uncompleted_order(futureAPI, coin_name, time_type, 2)
    except Exception as e:
        log_trade_v3("In ensure_buyin_less function, error: %s" % repr(e))
        return


def ensure_sell_more(futureAPI, coin_name, time_type, latest_price, buy_price, lever_rate=20):
    try:
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
    except Exception as e:
        log_trade_v3(repr(e))
        return False


def ensure_sell_less(futureAPI, coin_name, time_type, latest_price, buy_price, lever_rate=20):
    now_time = timestamp2string(time.time())
    try:
        sleep_time = 3
        while True:
            time.sleep(sleep_time)
            jRet = futureAPI.get_specific_position(time_type)

            if len(jRet["holding"]) > 0:
                cancel_uncompleted_order(futureAPI, coin_name, time_type)
                time.sleep(1)
                jRet = futureAPI.get_specific_position(time_type)
                short_available = int(jRet["holding"][0]["short_avail_qty"])
                if short_available == 0:
                    break
                futureAPI.take_order('', time_type, 4, latest_price, short_available, 1, lever_rate)
            else:
                break

        info = u'做空卖出成功！！！卖出价格：' + str(latest_price) + u', 收益: ' + str(buy_price - latest_price) \
               + ', ' + now_time
        thread.start_new_thread(send_email, (info,))
        file_transaction = coin_name + '_future_transaction.txt'
        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
            f.writelines(info + '\n')
    except Exception as e:
        log_trade_v3("In future ensure_sell_less function, error: %s\r\n traceback: %s\r\n time: %s"
                     % (repr(e), traceback.format_exc(), now_time))
        return False


def buyin_more_batch(futureAPI, coin_name, time_type, latest_price, lever_rate=20, amount=None):
    now_time = timestamp2string(time.time())
    try:
        result = futureAPI.get_coin_account(coin_name)
        balance = float(result['equity'])
        if not amount:
            amount = math.floor(balance * lever_rate * latest_price / 10)
        while amount >= 5:
            order_data = gen_orders_data(latest_price, amount, 1, 5)
            ret = futureAPI.take_orders(time_type, order_data, lever_rate)
            if ret and ret['result']:
                email_msg = "批量下单做多%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                            % (coin_name, latest_price, amount, now_time, ret)
                thread.start_new_thread(send_email, (email_msg,))
                return True
            amount *= math.floor(amount * 0.95)
        return False
    except Exception as e:
        log_trade_v3("In future buyin_more_batch function, error: %s, time: %s" % (repr(e), now_time))
        log_trade_v3(traceback.format_exc())
        return False


def buyin_less_batch(futureAPI, coin_name, time_type, buy_price, lever_rate=20, amount=None):
    now_time = timestamp2string(time.time())
    try:
        if not amount:
            coin_account = futureAPI.get_coin_account(coin_name)
            balance = float(coin_account['total_avail_balance'])
            if balance < 1:
                log_trade_v3(
                    'In future buyin_less_batch function, %s balance less than 1, balance: %.2f' % (coin_name, balance))
                return False
            amount = math.floor(balance * lever_rate * (buy_price - 0.1) / 10 * 0.95)
        while amount >= 5:
            order_data = gen_orders_data(buy_price, amount, 2, 5)
            ret = futureAPI.take_orders(time_type, order_data, lever_rate)
            if ret and ret['result']:
                email_msg = "批量下单做空%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                            % (coin_name, buy_price, amount, now_time, ret)
                thread.start_new_thread(send_email, (email_msg,))
                return True
            amount *= math.floor(amount * 0.95)
        return False
    except Exception as e:
        log_trade_v3("In future buyin_less_batch func, error info: %s, time: %s" % (repr(e), now_time))
        log_trade_v3(traceback.format_exc())
        return False


def sell_more_batch(futureAPI, time_type, latest_price, lever_rate=20):
    try:
        jRet = futureAPI.get_specific_position(time_type)
        log_trade_v3(jRet)
        while len(jRet["holding"]) > 0:
            amount = int(jRet["holding"][0]["long_avail_qty"])
            if amount == 0:
                return True
            turn = int(amount / batch_size)
            if turn == 0:
                ret = futureAPI.take_order('', time_type, 3, latest_price, amount, 1, lever_rate)
                log_trade_v3("In future sell_more_batch func, sell more result: %s" % ret)
                if ret and ret['result']:
                    return True
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
                    return True
                else:
                    return False
        return True
    except Exception as e:
        log_trade_v3("In sell_more_batch function, error: %s" % repr(e))
        return False


def sell_less_batch(futureAPI, time_type, latest_price, lever_rate=20):
    try:
        jRet = futureAPI.get_specific_position(time_type)
        log_trade_v3('In sell_less_batch function, get %s position: %s' % (time_type, jRet))
        while len(jRet["holding"]) > 0:
            amount = int(jRet["holding"][0]["short_avail_qty"])
            turn = int(amount / batch_size)
            if turn == 0:
                ret = futureAPI.take_order('', time_type, 4, latest_price, amount, 1, lever_rate)
                log_trade_v3('In sell_less_batch function, sell result: %s' % ret)
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
    except Exception as e:
        log_trade_v3('In sell_less_batch func, error: ' + repr(e))
        return False


def sell_less(futureAPI, time_type, lever_rate=20):
    now_time = timestamp2string(time.time())
    try:
        position = futureAPI.get_specific_position(time_type)
        log_trade_v3('In sell_less func, %s position: %s' % (time_type, position))
        while len(position["holding"]) > 0:
            amount = int(position["holding"][0]["short_avail_qty"])
            if amount == 0:
                return True
            ret = futureAPI.take_order('', time_type, 4, '', amount, 1, lever_rate)
            log_trade_v3('In future sell_less func, sell less result: %s, time: %s' % (ret, now_time))
            if ret and ret['result']:
                break
            else:
                return False
        return True
    except Exception as e:
        info = traceback.format_exc()
        log_trade_v3("In future sell_less func, error: %s\r\n traceback: %s\r\n time: %s" % (repr(e), info, now_time))
        return False


if __name__ == '__main__':

    from config_mother import futureAPI
    time_type = "EOS-USD-190329"
    coin_name = "eos"
    # future api test
    coin = Coin(coin_name, "usdt")
    future_instrument_id = coin.get_future_instrument_id()
    result = futureAPI.get_coin_account(coin.name)
    print(result)
    # result = buyin_less(futureAPI, coin.name, future_instrument_id, 0.3)
    # time.sleep(3)
    # thread.start_new_thread(ensure_buyin_less, (futureAPI, coin.name, future_instrument_id, 0.3))
    # while True:
    #     time.sleep(10)
    #     holding_position = futureAPI.get_specific_position(future_instrument_id)
    #     log_trade_v3 (holding_position)
