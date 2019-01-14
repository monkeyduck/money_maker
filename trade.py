#!/usr/bin/python
# -*- coding: UTF-8 -*-

import json
import math
from utils import send_email, timestamp2string
import time
try:
    import thread
except ImportError:
    import _thread as thread


def gen_orders_data(price, amount, trade_type, num):
    each_amount = amount / num
    ret_data = "{price:%.2f,amount:%d,type:%d,match_price:1}" % (price, each_amount, trade_type)
    data_list = [ret_data] * num
    orders_data = "[" + ",".join(data_list) + "]"
    return orders_data


def buyin_more(okFuture, coin_name, time_type, buy_price, amount=None, lever_rate=20, taker=False):
    json_ret = json.loads(okFuture.future_userinfo_4fix())
    balance = float(json_ret["info"][coin_name]["balance"])
    if not amount:
        amount = math.floor(balance * lever_rate * buy_price / 10)

    while amount >= 1:
        if taker:
            ret = okFuture.future_trade(coin_name + "_usd", time_type, '', amount, 1, 1, lever_rate)
        else:
            ret = okFuture.future_trade(coin_name + "_usd", time_type, buy_price, amount, 1, 0, lever_rate)
        print(ret)
        if 'true' in ret:
            email_msg = "下单做多%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                        % (coin_name, buy_price, amount, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            return json.loads(ret)["order_id"]
        amount = math.floor(amount * 0.95)

    return False


def buyin_more_price(okFuture, coin_name, time_type, buy_price, amount=None, lever_rate=20):
    json_ret = json.loads(okFuture.future_userinfo_4fix())
    balance = float(json_ret["info"][coin_name]["balance"])
    if not amount:
        amount = math.floor(balance * lever_rate * buy_price / 10)
    while amount >= 1:
        ret = okFuture.future_trade(coin_name + "_usd", time_type, buy_price, amount, 1, 0, lever_rate)
        print(ret)
        if 'true' in ret:
            return json.loads(ret)["order_id"]
        amount = math.floor(amount * 0.95)

    return False


def buyin_less_price(okFuture, coin_name, time_type, buy_price, amount=None, lever_rate=20):
    json_ret = json.loads(okFuture.future_userinfo_4fix())
    balance = float(json_ret["info"][coin_name]["balance"])
    if not amount:
        amount = math.floor(balance * lever_rate * buy_price / 10)
    while amount >= 1:
        ret = okFuture.future_trade(coin_name + "_usd", time_type, buy_price, amount, 2, 0, lever_rate)
        print(ret)
        if 'true' in ret:
            return json.loads(ret)["order_id"]
        amount = math.floor(amount * 0.95)

    return False


def buyin_more_batch(okFuture, coin_name, time_type, latest_price, lever_rate=20, amount=None):
    json_ret = json.loads(okFuture.future_userinfo_4fix())
    balance = float(json_ret["info"][coin_name]["balance"])
    if amount is None:
        amount = math.floor(balance * lever_rate * latest_price / 10 * 0.9)
    while amount >= 5:
        order_data = gen_orders_data(latest_price, amount, 1, 5)
        ret = okFuture.future_batchTrade(coin_name+"_usd", time_type, order_data, lever_rate)
        if 'true' in ret:
            email_msg = "批量下单做多%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                        % (coin_name, latest_price, amount, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            return True
        amount *= 0.95
    return False


def get_order_info(okFuture, coin_name, time_type, order_id):
    ret = json.loads(okFuture.future_orderinfo(coin_name + "_usd", time_type, order_id, 1, None, None))
    if ret["result"]:
        if len(ret["orders"]) > 0:
            # status = 0: 等待成交
            # status = 1: 部分成交
            # status = 2: 全部成交
            return ret["orders"][0]
    return False


# 若有成交单，返回挂单id；若无成交单，返回False
def pend_order(okFuture, coin_name, time_type, order_id, trade_type):
    retry_times = 50
    order_info = False
    while retry_times > 0:
        order_info = get_order_info(coin_name, time_type, order_id)
        print(order_info)
        if order_info:
            price = order_info['price']
            if order_info["status"] == 2:
                if trade_type == 'more':
                    return pend_more(coin_name, time_type, 20, price * 1.001)
                elif trade_type == 'less':
                    return pend_less(coin_name, time_type, 20, price * 9.999)
        retry_times -= 1

    # 尝试50次后仍未完全成交，则卖出部分成交份额
    okFuture.future_cancel(coin_name + "_usd", time_type, order_id)
    if order_info["status"] == 1 or order_info["status"] == 2:
        if trade_type == 'more':
            pend_more(coin_name, time_type, 20, price * 1.001)
        elif trade_type == 'less':
            pend_less(coin_name, time_type, 20, price * 9.999)
    if trade_type == 'more':
        cancel_uncompleted_order(okFuture, coin_name, time_type, 1)
    elif trade_type == 'less':
        cancel_uncompleted_order(okFuture, coin_name, time_type, 2)
    return False


def ensure_buyin_more(okFuture, coin_name, time_type, price):
    retry = 3
    while retry > 0:
        time.sleep(3)
        retry -= 1
        cancel_uncompleted_order(okFuture, coin_name, time_type, 1)
        if not buyin_more_batch(okFuture, coin_name, time_type, price, 20):
            break
    time.sleep(5)
    cancel_uncompleted_order(okFuture, coin_name, time_type, 1)


def buyin_less(okFuture, coin_name, time_type, buy_price, amount=None, lever_rate=20, taker=False):
    json_ret = json.loads(okFuture.future_userinfo_4fix())
    balance = float(json_ret["info"][coin_name]["balance"])
    if not amount:
        amount = math.floor(balance * lever_rate * buy_price / 10)
    while amount >= 1:
        if taker:
            ret = okFuture.future_trade(coin_name + "_usd", time_type, '', amount, 2, 1, lever_rate)
        else:
            ret = okFuture.future_trade(coin_name + "_usd", time_type, buy_price, amount, 2, 0, lever_rate)
        print(ret)
        if 'true' in ret:
            email_msg = "做空%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                        % (coin_name, buy_price, amount, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            return json.loads(ret)["order_id"]
        amount = math.floor(amount * 0.95)

    return False


def buyin_less_batch(okFuture, coin_name, time_type, latest_price, lever_rate=20, amount=None):
    json_ret = json.loads(okFuture.future_userinfo_4fix())
    balance = float(json_ret["info"][coin_name]["balance"])
    if amount is None:
        amount = math.floor(balance * lever_rate * latest_price / 10 * 0.9)
    while amount >= 5:
        order_data = gen_orders_data(latest_price, amount, 2, 5)
        ret = okFuture.future_batchTrade(coin_name+"_usd", time_type, order_data, lever_rate)
        if 'true' in ret:
            email_msg = "批量下单做空%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                        % (coin_name, latest_price, amount, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            print(ret)
            return True
        amount *= 0.95
    return False


def ensure_buyin_less(okFuture, coin_name, time_type, price):
    retry = 3
    while retry > 0:
        time.sleep(3)
        retry -= 1
        cancel_uncompleted_order(okFuture, coin_name, time_type, 2)
        if not buyin_less_batch(okFuture, coin_name, time_type, price, 20):
            break
    time.sleep(5)
    cancel_uncompleted_order(okFuture, coin_name, time_type, 2)


def acquire_orderId_by_type(okFuture, coin_name, time_type, order_type):
    ret = okFuture.future_orderinfo(coin_name + "_usd", time_type, -1, 1, None, None)
    order_id_list = []
    for each_order in json.loads(ret)["orders"]:
        if order_type == 0:
            order_id_list.append(str(each_order['order_id']))
        elif int(each_order['type']) == order_type:
            order_id_list.append(str(each_order['order_id']))
    return order_id_list


    # status_code,1:未完成的订单 2:已完成的订单
def cancel_uncompleted_order(okFuture, coin_name, time_type, order_type=0):
    order_id_list = acquire_orderId_by_type(okFuture, coin_name, time_type, order_type)
    if len(order_id_list) > 0:
        order_id = ",".join(order_id_list)
        ret = okFuture.future_cancel(coin_name+"_usd", time_type, order_id)
        print(ret)
        if 'true' in ret:
            return True
        elif 'false' in ret:
            time.sleep(1)
            return cancel_uncompleted_order(okFuture, coin_name, time_type)
        else:
            fail_list = json.loads(ret)["error"]
            if fail_list == "":
                return True
            else:
                return cancel_uncompleted_order(okFuture, coin_name, time_type)
    return False


def pend_order_price(okFuture, coin_name, time_type, order_type, amount, price=None):
    if amount > 0:
        okFuture.future_trade(coin_name + "_usd", time_type, price, amount, order_type, 0, 20)


def pend_more(okFuture, coin_name, time_type, lever_rate=20, price=None):
    jRet = json.loads(okFuture.future_position_4fix(coin_name+"_usd", time_type, "1"))
    while len(jRet["holding"]) > 0:
        buy_available = jRet["holding"][0]["buy_available"]
        if buy_available > 0:
            if price:
                ret = okFuture.future_trade(coin_name + "_usd", time_type, price, buy_available, 3, 0, lever_rate)
            else:
                ret = okFuture.future_trade(coin_name + "_usd", time_type, '', buy_available, 3, 1, lever_rate)
            if 'true' in ret:
                return True
            else:
                jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))
        else:
            return True
    return True


def pend_less(okFuture, coin_name, time_type, lever_rate=20, price=None):
    jRet = json.loads(okFuture.future_position_4fix(coin_name+"_usd", time_type, "1"))
    while len(jRet["holding"]) > 0:
        buy_available = jRet["holding"][0]["sell_available"]
        if buy_available > 0:
            if price:
                ret = okFuture.future_trade(coin_name + "_usd", time_type, price, buy_available, 4, 0, lever_rate)
            else:
                ret = okFuture.future_trade(coin_name + "_usd", time_type, '', buy_available, 4, 1, lever_rate)
            if 'true' in ret:
                return True
            else:
                jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))
        else:
            return True
    return True


def sell_more(okFuture, coin_name, time_type, price=None, lever_rate=20):
    jRet = json.loads(okFuture.future_position_4fix(coin_name+"_usd", time_type, "1"))
    while len(jRet["holding"]) > 0:
        print(jRet)
        cancel_uncompleted_order(okFuture, coin_name, time_type)
        buy_available = jRet["holding"][0]["buy_available"]
        if price:
            ret = okFuture.future_trade(coin_name+"_usd", time_type, price, buy_available, 3, 0, lever_rate)
        else:
            ret = okFuture.future_trade(coin_name+"_usd", time_type, '', buy_available, 3, 1, lever_rate)
        print(ret)
        if 'true' in ret:
            time.sleep(2)
            jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))

    email_msg = "卖出做多%s成功, 时间: %s, 成交结果: %s" \
                % (coin_name, timestamp2string(time.time()), ret)
    thread.start_new_thread(send_email, (email_msg,))
    return True


def sell_more_price(okFuture, coin_name, time_type, price, lever_rate=20):
    jRet = json.loads(okFuture.future_position_4fix(coin_name+"_usd", time_type, "1"))
    if len(jRet["holding"]) > 0:
        buy_available = jRet["holding"][0]["buy_available"]
        ret = okFuture.future_trade(coin_name+"_usd", time_type, price, buy_available, 3, 1, lever_rate)
        if 'true' in ret:
            return json.loads(ret)["order_id"]
    return False


def sell_less(okFuture, coin_name, time_type, price=None, lever_rate=20):
    jRet = json.loads(okFuture.future_position_4fix(coin_name+"_usd", time_type, "1"))

    while len(jRet["holding"]) > 0:
        print(jRet)
        cancel_uncompleted_order(okFuture, coin_name, time_type)
        sell_available = jRet["holding"][0]["sell_available"]
        if price:
            ret = okFuture.future_trade(coin_name+"_usd", time_type, price, sell_available, 4, 0, lever_rate)
        else:
            ret = okFuture.future_trade(coin_name+"_usd", time_type, '', sell_available, 4, 1, lever_rate)
        print(ret)
        if 'true' in ret:
            time.sleep(2)
            jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))

    email_msg = "卖出做空%s成功, 时间: %s, 成交结果: %s" \
                % (coin_name, timestamp2string(time.time()), ret)
    thread.start_new_thread(send_email, (email_msg,))
    return True


def sell_less_price(okFuture, coin_name, time_type, price, lever_rate=20):
    jRet = json.loads(okFuture.future_position_4fix(coin_name+"_usd", time_type, "1"))

    if len(jRet["holding"]) > 0:
        sell_available = jRet["holding"][0]["sell_available"]
        ret = okFuture.future_trade(coin_name+"_usd", time_type, price, sell_available, 4, 1, lever_rate)
        if 'true' in ret:
            return json.loads(ret)["order_id"]
    return False


def buyin_moreandless(okFuture, coin_name, time_type, buy_price, lever_rate=20, buy_ratio=0.5):
    json_ret = json.loads(okFuture.future_userinfo_4fix())
    balance = float(json_ret["info"][coin_name]["balance"])
    amount = math.floor(balance * lever_rate * buy_price / 10)
    buy_amount = math.floor(amount * (1 - buy_ratio))
    sell_amount = math.floor(amount * buy_ratio)
    order_id1 = False
    order_id2 = False
    if buy_amount > 0:
        ret1 = okFuture.future_trade(coin_name + "_usd", time_type, buy_price * 0.9998, buy_amount, 1, 0, lever_rate)
        if 'true' in ret1:
            order_id1 = json.loads(ret1)["order_id"]
    if sell_amount > 0:
        ret2 = okFuture.future_trade(coin_name + "_usd", time_type, buy_price * 1.0002, sell_amount, 2, 0, lever_rate)
        if 'true' in ret2:
            order_id2 = json.loads(ret2)["order_id"]
    return order_id1, order_id2


if __name__ == '__main__':
    coin_name = "etc"
    time_type = "quarter"
    from config_strict import okFuture
    result = okFuture.future_userinfo_4fix()
    print(result)
    # order_info = get_order_info(okFuture, coin_name, time_type, "1769187046398976")
    # ts = time.time()
    # if int(ts) > int(order_info['create_date'] / 1000) + 10:
    #     print(order_info)
    #     okFuture.future_cancel(okFuture, coin_name + "_usd", time_type, "1769187046398976")
    # print (okFuture.future_position_4fix(coin_name + "_usd", time_type, 1))
    # print(okFuture.future_userinfo_4fix())
    # oid = buyin_more_price(coin_name, time_type, 9.187, 20)
    # print(oid)
    # print(get_order_info(coin_name, time_type, '1758710351080448'))

    # pend_more(coin_name, time_type, 20, 9.17)
