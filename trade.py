#!/usr/bin/python
# -*- coding: UTF-8 -*-

import urllib
import json
import requests
import math
from future import OKCoinFuture
from OKCoinSpot import OKCoinSpot

api_key = 'your_api_key'
secret_key = 'your_secret_key'
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


def get_latest_price_this_week(type):
    eos_this_week = eos_ticker + u'this_week'
    r = requests.get(eos_this_week)
    result = json.loads(r.text)
    return float(result["ticker"][type])


def buyin_more(leverRate = 20):
    jRet = json.loads(okFuture.future_userinfo_4fix())
    balance = float(jRet["info"]["eos"]["balance"])
    amount = math.floor(balance * leverRate)
    while amount > 0:
        amount = math.floor(amount * 0.9)
        print(amount)
        ret = okFuture.future_trade("eos_usd", "this_week", None, amount, 1, 1, leverRate)
        print(ret)
        if 'true' in ret:
            return True


def buyin_less(leverRate = 20):
    jRet = json.loads(okFuture.future_userinfo_4fix())
    balance = float(jRet["info"]["eos"]["balance"])
    amount = math.floor(balance * leverRate)
    print(amount)
    while amount > 0:
        amount = math.floor(amount * 0.9)
        ret = okFuture.future_trade("eos_usd", "this_week", None, amount, 2, 1, leverRate)
        print(ret)
        if 'true' in ret:
            return True


def sell_more(leverRate = 20):
    jRet = json.loads(okFuture.future_position_4fix("eos_usd", "this_week", "1"))
    while len(jRet["holding"]) > 0:
        buy_available = jRet["holding"][0]["buy_available"]
        ret = okFuture.future_trade("eos_usd", "this_week", None, buy_available, 3, 1, leverRate)
        print (ret)
        if 'true' in ret:
            return True


def sell_less(leverRate = 20):
    jRet = json.loads(okFuture.future_position_4fix("eos_usd", "this_week", "1"))
    while len(jRet["holding"]) > 0:
        sell_available = jRet["holding"][0]["sell_available"]
        ret = okFuture.future_trade("eos_usd", "this_week", None, sell_available, 4, 1, leverRate)
        print(ret)
        if 'true' in ret:
            return True


if __name__ == '__main__':
    # jRet = json.loads(okFuture.future_userinfo_4fix())
    # print(jRet["info"]["eos"])
    # balance = float(jRet["info"]["eos"]["balance"])
    # print(balance)
    # print(buyin_more())
    # jRet = json.loads(okFuture.future_position_4fix("eos_usd", "this_week", "1"))
    # print(jRet)
    # buyin_less()
    # sell_more()
    # buyin_less()
    sell_less()
    # buyin_more()