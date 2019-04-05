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


batch_size = 400
trade_log_path = os.getcwd() + '/trade_v3.log'
BUY_MORE_TYPE = 1
BUY_LESS_TYPE = 2
SELL_MORE_TYPE = 3
SELL_LESS_TYPE = 4


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


def buyin_more(future_api, coin_name, time_type, buy_price, amount=None, lever_rate=20, taker=True):
    ts = time.time()
    now_time = timestamp2string(ts)
    try:
        coin_account = future_api.get_coin_account(coin_name)
        balance = float(coin_account['equity'])
        if balance < 1:
            log_trade_v3("In future buyin_more function, available balance less than 1, balance: %.2f" % balance)
            return False
        if not amount:
            amount = math.floor(balance * lever_rate * (buy_price - 0.1) / 10 * 0.99)
            log_trade_v3('In buyin_more function, plan to buyin amount: %d' % amount)

        if amount >= 1:
            if taker:
                ret = future_api.take_order('', time_type, BUY_MORE_TYPE, buy_price, amount, 1, lever_rate)
            else:
                ret = future_api.take_order('', time_type, BUY_MORE_TYPE, buy_price, amount, 0, lever_rate)

            log_trade_v3('In future_buyin_more function: %s, time: %s' % (ret, now_time))

            if ret and ret['result']:
                email_msg = "下单做多%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                            % (coin_name, buy_price, amount, now_time, ret)
                thread.start_new_thread(send_email, (email_msg,))
                return ret["order_id"]
        else:
            return False
    except Exception as e:
        info = traceback.format_exc()
        log_trade_v3("In future buyin_more func, info: %s" % info)
        return False


def buyin_less(future_api, coin_name, time_type, buy_price, amount=None, lever_rate=20, taker=True):
    ts = time.time()
    now_time = timestamp2string(ts)
    try:
        coin_account = future_api.get_coin_account(coin_name)
        balance = float(coin_account['equity'])
        if balance < 1:
            log_trade_v3("In future buyin_less function, available balance less than 1, balance: %.2f" % balance)
            return False
        if not amount:
            amount = math.floor(balance * lever_rate * (buy_price - 0.1) / 10 * 0.99)
            log_trade_v3('In buyin_less function, plan to buyin amount: %d' % amount)

        if amount >= 1:
            if taker:
                ret = future_api.take_order('', time_type, BUY_LESS_TYPE, buy_price, amount, 1, lever_rate)
            else:
                ret = future_api.take_order('', time_type, BUY_LESS_TYPE, buy_price, amount, 0, lever_rate)

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


def buyin_less_turn(future_api, coin_name, time_type, buy_price, amount=None, lever_rate=20, taker=True):
    try:
        coin_account = future_api.get_coin_account(coin_name)
        balance = float(coin_account['equity'])
        if not amount:
            amount = math.floor(balance * lever_rate * (buy_price - 0.1) / 10 * 0.99)

        turn = int(amount / batch_size)
        ts = time.time()
        now_time = timestamp2string(ts)

        if turn == 0 and amount >= 1:
            if taker:
                ret = future_api.take_order('', time_type, BUY_LESS_TYPE, buy_price, amount, 1, lever_rate)
            else:
                ret = future_api.take_order('', time_type, BUY_LESS_TYPE, buy_price, amount, 0, lever_rate)

            log_trade_v3('In future_buyin_less_turn funciton: %s, time: %s' % (ret, now_time))

            if ret and ret['result']:
                email_msg = "下单做空%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                            % (coin_name, buy_price, amount, timestamp2string(time.time()), ret)
                thread.start_new_thread(send_email, (email_msg,))
                return ret["order_id"]
        else:
            amount -= turn * batch_size
            while turn > 0:
                future_api.take_order('', time_type, BUY_LESS_TYPE, '', batch_size, 1, lever_rate)
                time.sleep(0.3)
                turn -= 1
            while amount >= 1:
                ret = future_api.take_order('', time_type, BUY_LESS_TYPE, buy_price, amount, 1, lever_rate)
                log_trade_v3(ret)

                if ret and ret['result']:
                    email_msg = "下单做空%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                                % (coin_name, buy_price, amount, timestamp2string(time.time()), ret)
                    thread.start_new_thread(send_email, (email_msg,))
                    return ret["order_id"]
                amount = math.floor(amount * 0.99)
                time.sleep(1)
        return True
    except Exception as e:
        log_trade_v3(repr(e))
        return False


# status 0 wait to deal, status 1 part dealed
def acquire_orderId_by_type(future_api, time_type, order_type):
    ret = future_api.get_order_list(0, None, None, None, time_type)
    order_id_list = []
    for each_order in ret["order_info"]:
        if order_type == 0:
            order_id_list.append(str(each_order['order_id']))
        elif int(each_order['type']) == order_type:
            order_id_list.append(str(each_order['order_id']))
    ret = future_api.get_order_list(1, None, None, None, time_type)
    for each_order in ret["order_info"]:
        if order_type == 0:
            order_id_list.append(str(each_order['order_id']))
        elif int(each_order['type']) == order_type:
            order_id_list.append(str(each_order['order_id']))
    return order_id_list


# status_code,1:未完成的订单 2:已完成的订单
def cancel_uncompleted_order(future_api, coin_name, time_type, order_type=0):
    order_id_list = acquire_orderId_by_type(future_api, time_type, order_type)
    if len(order_id_list) > 0:
        ret = future_api.revoke_orders(time_type, order_id_list)
        log_trade_v3("In cancel_uncompleted_order func, revoke result: %s" % ret)
        if ret and ret['result']:
            return True
        else:
            time.sleep(1)
            return cancel_uncompleted_order(future_api, coin_name, time_type, order_type)
    return False


def ensure_buyin_more(future_api, coin_name, time_type, price):
    try:
        retry = 3
        while retry > 0:
            time.sleep(2)
            retry -= 1
            cancel_uncompleted_order(future_api, coin_name, time_type, BUY_MORE_TYPE)
            time.sleep(1)
            if not buyin_more_batch(future_api, coin_name, time_type, price, 20):
                break
        time.sleep(5)
        cancel_uncompleted_order(future_api, coin_name, time_type, BUY_MORE_TYPE)
    except Exception as e:
        log_trade_v3("In ensure_buyin_more function, error: %s" % repr(e))
        return


def ensure_buyin_more(future_api, coin_name, time_type, buy_price, order_id, lever_rate=20):
    now_time = timestamp2string(time.time())
    try:
        retry = 3
        while retry > 0:
            time.sleep(2)
            retry -= 1
            if order_id:
                future_api.revoke_order(time_type, order_id)
            else:
                cancel_uncompleted_order(future_api, coin_name, time_type, BUY_MORE_TYPE)
            time.sleep(1)
            coin_account = future_api.get_coin_account(coin_name)
            balance = float(coin_account['total_avail_balance'])
            # 撤销所有未完成挂单后，若balance<1则认为已全仓买入
            if balance < 1:
                return
            amount = math.floor(balance * lever_rate * buy_price / 10 * 0.99)
            if not buyin_more_batch(future_api, coin_name, time_type, buy_price, 20, amount):
                break
        time.sleep(5)
        cancel_uncompleted_order(future_api, coin_name, time_type, BUY_MORE_TYPE)
    except Exception as e:
        log_trade_v3("In ensure_buyin_less function, error: %s, time: %s" % (traceback.format_exc(), now_time))
        return


def ensure_buyin_less(future_api, coin_name, time_type, buy_price, order_id, lever_rate=20):
    now_time = timestamp2string(time.time())
    try:
        retry = 3
        while retry > 0:
            time.sleep(2)
            retry -= 1
            if order_id:
                future_api.revoke_order(time_type, order_id)
            else:
                cancel_uncompleted_order(future_api, coin_name, time_type, BUY_LESS_TYPE)
            time.sleep(1)
            coin_account = future_api.get_coin_account(coin_name)
            balance = float(coin_account['total_avail_balance'])
            # 撤销所有未完成挂单后，若balance<1则认为已全仓买入
            if balance < 1:
                return
            amount = math.floor(balance * lever_rate * buy_price / 10 * 0.99)
            if not buyin_less_batch(future_api, coin_name, time_type, buy_price, 20, amount):
                break
        time.sleep(5)
        cancel_uncompleted_order(future_api, coin_name, time_type, BUY_LESS_TYPE)
    except Exception as e:
        log_trade_v3("In ensure_buyin_less function, error: %s, time: %s" % (traceback.format_exc(), now_time))
        return


def ensure_sell_more(future_api, coin_name, time_type, latest_price, buy_price, lever_rate=20):
    now_time = timestamp2string(time.time())
    try:
        sleep_time = 3
        while True:
            time.sleep(sleep_time)
            jRet = future_api.get_specific_position(time_type)

            if len(jRet["holding"]) > 0:
                cancel_uncompleted_order(future_api, coin_name, time_type)
                time.sleep(1)
                jRet = future_api.get_specific_position(time_type)
                short_available = int(jRet["holding"][0]["long_avail_qty"])
                if short_available == 0:
                    break
                future_api.take_order('', time_type, SELL_MORE_TYPE, latest_price, short_available, 1, lever_rate)
            else:
                break

        info = u'做多卖出成功！！！卖出价格：' + str(latest_price) + u', 收益: ' + str(latest_price - buy_price) \
               + ', ' + now_time
        thread.start_new_thread(send_email, (info,))
        file_transaction = coin_name + '_future_transaction.txt'
        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
            f.writelines(info + '\n')
    except Exception as e:
        log_trade_v3("In future ensure_sell_more function, error: %s\r\n traceback: %s\r\n time: %s"
                     % (repr(e), traceback.format_exc(), now_time))
        return False


def ensure_sell_less(future_api, coin_name, time_type, latest_price, buy_price, lever_rate=20):
    now_time = timestamp2string(time.time())
    try:
        sleep_time = 3
        while True:
            time.sleep(sleep_time)
            jRet = future_api.get_specific_position(time_type)

            if len(jRet["holding"]) > 0:
                cancel_uncompleted_order(future_api, coin_name, time_type)
                time.sleep(1)
                jRet = future_api.get_specific_position(time_type)
                short_available = int(jRet["holding"][0]["short_avail_qty"])
                if short_available == 0:
                    break
                future_api.take_order('', time_type, SELL_LESS_TYPE, latest_price, short_available, 1, lever_rate)
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


def buyin_more_batch(future_api, coin_name, time_type, latest_price, lever_rate=20, amount=None):
    now_time = timestamp2string(time.time())
    try:
        result = future_api.get_coin_account(coin_name)
        balance = float(result['equity'])
        if not amount:
            amount = math.floor(balance * lever_rate * latest_price / 10)
        while amount >= 5:
            order_data = gen_orders_data(latest_price, amount, BUY_MORE_TYPE, 5)
            ret = future_api.take_orders(time_type, order_data, lever_rate)
            if ret and ret['result']:
                email_msg = "批量下单做多%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                            % (coin_name, latest_price, amount, now_time, ret)
                thread.start_new_thread(send_email, (email_msg,))
                return True
            amount = math.floor(amount * 0.99)
        return False
    except Exception as e:
        log_trade_v3("In future buyin_more_batch function, error: %s, time: %s" % (repr(e), now_time))
        log_trade_v3(traceback.format_exc())
        return False


def buyin_less_batch(future_api, coin_name, time_type, buy_price, lever_rate=20, amount=None):
    now_time = timestamp2string(time.time())
    try:
        if not amount:
            coin_account = future_api.get_coin_account(coin_name)
            balance = float(coin_account['total_avail_balance'])
            if balance < 1:
                log_trade_v3(
                    'In future buyin_less_batch function, %s balance less than 1, balance: %.2f' % (coin_name, balance))
                return False
            amount = math.floor(balance * lever_rate * buy_price / 10 * 0.99)
        while amount >= 5:
            order_data = gen_orders_data(buy_price, amount, BUY_LESS_TYPE, 5)
            ret = future_api.take_orders(time_type, order_data, lever_rate)
            if ret and ret['result']:
                email_msg = "批量下单做空%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                            % (coin_name, buy_price, amount, now_time, ret)
                thread.start_new_thread(send_email, (email_msg,))
                return True
            amount = math.floor(amount * 0.99)
        return False
    except Exception as e:
        log_trade_v3("In future buyin_less_batch func, error info: %s, time: %s" % (repr(e), now_time))
        log_trade_v3(traceback.format_exc())
        return False


def sell_more_batch(future_api, time_type, latest_price, lever_rate=20):
    try:
        jRet = future_api.get_specific_position(time_type)
        log_trade_v3(jRet)
        while len(jRet["holding"]) > 0:
            amount = int(jRet["holding"][0]["long_avail_qty"])
            if amount == 0:
                return True
            turn = int(amount / batch_size)
            if turn == 0:
                ret = future_api.take_order('', time_type, SELL_MORE_TYPE, latest_price, amount, 1, lever_rate)
                log_trade_v3("In future sell_more_batch func, sell more result: %s" % ret)
                if ret and ret['result']:
                    return True
                else:
                    return False
            else:
                amount -= turn * batch_size
                while turn > 0:
                    future_api.take_order('', time_type, SELL_MORE_TYPE, latest_price, batch_size, 1, lever_rate)
                    time.sleep(0.1)
                    turn -= 1
                ret = future_api.take_order('', time_type, SELL_MORE_TYPE, latest_price, amount, 1, lever_rate)
                if ret and ret['result']:
                    return True
                else:
                    return False
        return True
    except Exception as e:
        log_trade_v3("In sell_more_batch function, error: %s" % repr(e))
        return False


def sell_less_batch(future_api, time_type, latest_price, lever_rate=20):
    try:
        jRet = future_api.get_specific_position(time_type)
        log_trade_v3('In sell_less_batch function, get %s position: %s' % (time_type, jRet))
        while len(jRet["holding"]) > 0:
            amount = int(jRet["holding"][0]["short_avail_qty"])
            turn = int(amount / batch_size)
            if turn == 0:
                ret = future_api.take_order('', time_type, SELL_LESS_TYPE, latest_price, amount, 1, lever_rate)
                log_trade_v3('In sell_less_batch function, sell result: %s' % ret)
                if ret and ret['result']:
                    break
                else:
                    return False
            else:
                amount -= turn * batch_size
                while turn > 0:
                    future_api.take_order('', time_type, SELL_LESS_TYPE, latest_price, batch_size, 1, lever_rate)
                    time.sleep(0.1)
                    turn -= 1
                ret = future_api.take_order('', time_type, SELL_LESS_TYPE, latest_price, amount, 1, lever_rate)
                if ret and ret['result']:
                    break
                else:
                    return False
        return True
    except Exception as e:
        log_trade_v3('In sell_less_batch func, error: ' + repr(e))
        return False


def sell_less(future_api, time_type, lever_rate=20):
    now_time = timestamp2string(time.time())
    try:
        position = future_api.get_specific_position(time_type)
        log_trade_v3('In sell_less func, %s position: %s' % (time_type, position))
        while len(position["holding"]) > 0:
            amount = int(position["holding"][0]["short_avail_qty"])
            if amount == 0:
                return True
            ret = future_api.take_order('', time_type, SELL_LESS_TYPE, '', amount, 1, lever_rate)
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


def sell_more(future_api, time_type, lever_rate=20):
    now_time = timestamp2string(time.time())
    try:
        position = future_api.get_specific_position(time_type)
        log_trade_v3('In sell_more func, %s position: %s' % (time_type, position))
        while len(position["holding"]) > 0:
            amount = int(position["holding"][0]["long_avail_qty"])
            if amount == 0:
                return True
            ret = future_api.take_order('', time_type, SELL_MORE_TYPE, '', amount, 1, lever_rate)
            log_trade_v3('In future sell_more func, sell more result: %s, time: %s' % (ret, now_time))
            if ret and ret['result']:
                break
            else:
                return False
        return True
    except Exception as e:
        info = traceback.format_exc()
        log_trade_v3("In future sell_more func, error: %s\r\n traceback: %s\r\n time: %s" % (repr(e), info, now_time))
        return False


def get_latest_future_price(future_api, future_instrument_id):
    try:
        ticker = future_api.get_specific_ticker(future_instrument_id)
        latest_future_price = float(ticker['last'])
        return latest_future_price
    except Exception as e:
        info = traceback.format_exc()
        log_trade_v3("In get_latest_future_price func, error: %s \r\n traceback: %s" % (repr(e), info))
        return False


if __name__=='__main__':
    from config_mother import futureAPI
    coin_name = "eos"
    coin = Coin(coin_name, "usdt")
    print(coin.get_future_instrument_id())
    print(get_latest_future_price(futureAPI, coin.get_future_instrument_id()))
