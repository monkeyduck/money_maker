#!/usr/bin/python
# -*- coding: UTF-8 -*-

import urllib
import json
import requests
import math
from future import OKCoinFuture
from OKCoinSpot import OKCoinSpot
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from time_utils import timestamp2string
from personal_info import api_key, secret_key
import time
try:
    import thread
except ImportError:
    import _thread as thread


ticker = u'https://www.okex.com/api/v1/future_ticker.do?symbol='
eos_ticker = u'https://www.okex.com/api/v1/future_ticker.do?symbol=eos_usd&contract_type='

okFuture = OKCoinFuture(api_key, secret_key)
okSpot = OKCoinSpot(api_key, secret_key)


def do_get(url):
    request = urllib.Request(url)
    response = urllib.urlopen(request)
    print(response.read())


def do_post(url, data):
    request = urllib.Request(url)
    response = urllib.urlopen(request, urllib.urlencode(data))
    print(response)


def get_latest_price_this_week(coin, type):
    this_week = ticker + coin.gen_full_name() + u'&contract_type=this_week'
    r = requests.get(this_week)
    result = json.loads(r.text)
    return float(result["ticker"][type])


def gen_orders_data(price, amount, trade_type, num):
    each_amount = int(amount / num)
    ret_data = "{price:%.2f,amount:%d,type:%d,match_price:1}" % (price, each_amount, trade_type)
    data_list = [ret_data] * num
    orders_data = "[" + ",".join(data_list) + "]"
    print(orders_data)
    return orders_data


def buyin_more(coin_name, time_type, latest_price, lever_rate=20):
    json_ret = json.loads(okFuture.future_userinfo_4fix())
    balance = float(json_ret["info"][coin_name]["balance"])
    amount = math.floor(balance * lever_rate * latest_price / 10)
    while amount > 0:
        amount = math.floor(amount * 0.95)
        ret = okFuture.future_trade(coin_name + "_usd", time_type, None, amount, 1, 1, lever_rate)
        print(ret)
        if 'true' in ret:
            email_msg = "做多%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                        % (coin_name, latest_price, amount, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            return True
    return False


def buyin_more_batch(coin_name, time_type, latest_price, lever_rate=20, amount=None):
    json_ret = json.loads(okFuture.future_userinfo_4fix())
    balance = float(json_ret["info"][coin_name]["balance"])
    if amount is None:
        amount = math.floor(balance * lever_rate * latest_price / 10)
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


def ensure_buyin_more(coin_name, time_type, price):
    retry = 3
    while retry > 0:
        time.sleep(1)
        retry -= 1
        if cancel_uncompleted_order(coin_name, time_type):
            buyin_more_batch(coin_name, time_type, price, 20)
        else:
            break


def ensure_buyin_less(coin_name, time_type, price):
    retry = 3
    while retry > 0:
        time.sleep(1)
        retry -= 1
        if cancel_uncompleted_order(coin_name, time_type):
            buyin_less_batch(coin_name, time_type, price, 20)
        else:
            break


def buyin_less(coin_name, time_type, latest_price, lever_rate=20):
    json_ret = json.loads(okFuture.future_userinfo_4fix())
    balance = float(json_ret["info"][coin_name]["balance"])
    amount = math.floor(balance * lever_rate * latest_price / 10)
    while amount > 0:
        amount = math.floor(amount * 0.95)
        ret = okFuture.future_trade(coin_name+"_usd", time_type, None, amount, 2, 1, lever_rate)
        print(ret)
        if 'true' in ret:
            email_msg = "做空%s成功，最新价格: %.4f, 成交张数: %d, 时间: %s, 成交结果: %s" \
                        % (coin_name, latest_price, amount, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            return True
    return False


def buyin_less_batch(coin_name, time_type, latest_price, lever_rate=20, amount=None):
    json_ret = json.loads(okFuture.future_userinfo_4fix())
    balance = float(json_ret["info"][coin_name]["balance"])
    if amount is None:
        amount = math.floor(balance * lever_rate * latest_price / 10)
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


    # status_code,1:未完成的订单 2:已完成的订单
def cancel_uncompleted_order(coin_name, time_type):
    ret = okFuture.future_orderinfo(coin_name+"_usd", time_type, -1, 1, None, None)
    order_id_list = []
    for each_order in json.loads(ret)["orders"]:
        order_id_list.append(str(each_order['order_id']))
    if len(order_id_list) > 0:
        order_id = ",".join(order_id_list)
        ret = okFuture.future_cancel(coin_name+"_usd", time_type, order_id)
        print(ret)
        if 'true' in ret:
            email_msg = "撤单%s成功, 时间: %s, 成交结果: %s" \
                        % (coin_name, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            return True
        else:
            email_msg = "撤单%s失败, 时间: %s, 失败详情: %s" \
                        % (coin_name, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            return cancel_uncompleted_order(coin_name, time_type)
    return False


def sell_more(coin_name, time_type, leverRate = 20):
    cancel_uncompleted_order(coin_name, time_type)
    jRet = json.loads(okFuture.future_position_4fix(coin_name+"_usd", time_type, "1"))

    while len(jRet["holding"]) > 0:
        buy_available = jRet["holding"][0]["buy_available"]
        ret = okFuture.future_trade(coin_name+"_usd", time_type, '', buy_available, 3, 1, leverRate)
        print(ret)
        if 'true' in ret:
            email_msg = "卖出做多%s成功, 时间: %s, 成交结果: %s" \
                        % (coin_name, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            return True
    return True


def sell_less(coin_name, time_type, leverRate = 20):
    cancel_uncompleted_order(coin_name, time_type)
    jRet = json.loads(okFuture.future_position_4fix(coin_name+"_usd", time_type, "1"))

    while len(jRet["holding"]) > 0:
        sell_available = jRet["holding"][0]["sell_available"]
        ret = okFuture.future_trade(coin_name+"_usd", time_type, '', sell_available, 4, 1, leverRate)
        print(ret)
        if 'true' in ret:
            email_msg = "卖出做空%s成功, 时间: %s, 成交结果: %s" \
                        % (coin_name, timestamp2string(time.time()), ret)
            thread.start_new_thread(send_email, (email_msg,))
            return True
    return True


def send_email(message):
    # 第三方 SMTP 服务
    mail_host = "smtp.163.com"  # 设置服务器
    mail_user = "lilinchuan2"  # 用户名
    mail_pass = "l1992l0202c2112"  # 口令

    sender = 'lilinchuan2@163.com'
    receivers = ['475900302@qq.com']  # 接收邮件，可设置为你的QQ邮箱或者其他邮箱

    msg = MIMEText(message, 'plain', 'utf-8')
    msg['From'] = Header("MoneyMaker <%s>" % sender)
    msg['To'] = Header("管理员 <%s>" % receivers[0])
    msg['Subject'] = Header("币圈操作提示", 'utf-8')

    try:
        smtpObj = smtplib.SMTP()
        smtpObj.connect(mail_host, 25)  # 25 为 SMTP 端口号
        smtpObj.login(mail_user, mail_pass)
        smtpObj.sendmail(sender, receivers, msg.as_string())
        print("邮件发送成功")
    except smtplib.SMTPException as e:
        print("Error: 无法发送邮件:", e)


if __name__ == '__main__':
    # coin_name = "eos"
    # latest_price = 4.88
    # amount = 654
    # email_msg = "做多%s成功，最新价格: %.2f, 成交张数: %d, 时间: %s" \
    #             % (coin_name, latest_price, amount, timestamp2string(time.time()))
    # thread.start_new_thread(send_email, (email_msg,))
    # time.sleep(10)
    # buyin_less("etc", "quarter", 10.4)
    # sell_less("etc", "quarter")
    # time.sleep(10)
    # gen_orders_data(5.1, 5, 2, 5)
    # buyin_more_batch("eos", "quarter", 5, 20, 5)
    # buyin_less_batch("etc", "quarter", 10, 20, 5)
    #
    # ret = okFuture.future_orderinfo("eos"+"_usd", "this_week", -1, 1, None, None)
    # print (ret)
    # time.sleep(10)
    # sell_less("etc", "quarter")
    # check_order_status("etc", "quarter", 1)
    # sell_more("eos", "quarter")
    # time.sleep(10)
    # jRet = json.loads(okFuture.future_userinfo_4fix())
    # print(jRet)
    # print(jRet["info"]["etc"])
    # balance = float(jRet["info"]["eos"]["balance"])
    # print(balance)
    # print(buyin_more())
    # jRet = json.loads(okFuture.future_position_4fix("eos_usd", "this_week", "1"))
    # print(jRet)
    coin_name = "eos"
    time_type = "this_week"
    ret = okFuture.future_orderinfo(coin_name+"_usd", time_type, -1, 1, None, None)
    print(ret)
    # print(okSpot.ticker("etc_usdt"))
