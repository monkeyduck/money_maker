#!/usr/bin/python
# -*- coding: UTF-8 -*-

import codecs
import json
import datetime
import time
from utils import timestamp2string
import os
from utils import cal_rate





def read_file(file_path):
    with codecs.open(file_path, 'r', 'UTF-8') as f:
        lines = f.readlines()
    return lines


def get_now_price(line):
    return float(line.split(',')[0].split(':')[1])


def get_3s_price(line):
    return float(line.split(',')[1].split(':')[1])


def get_10s_price(line):
    return float(line.split(',')[2].split(':')[1])


def get_1m_price(line):
    return float(line.split(',')[3].split(':')[1])


def get_5m_price(line):
    return float(line.split(',')[4].split(':')[1])


def get_3s_vol(line):
    return float(line.split(',')[6].split(':')[1])


def get_3s_ask_vol(line):
    return float(line.split(',')[11].split(':')[1])


def get_3s_bid_vol(line):
    return float(line.split(',')[12].split(':')[1])


def get_1m_ask_vol(line):
    return float(line.split(',')[9].split(':')[1])


def get_1m_bid_vol(line):
    return float(line.split(',')[10].split(':')[1])


def get_1m_vol(line):
    return float(line.split(',')[8].split(':')[1])


def get_10s_change(line):
    price_3s = get_3s_price(line)
    price_10s = get_10s_price(line)
    return cal_rate(price_3s, price_10s)


def get_1m_change(line):
    avg_3s_price = get_3s_price(line)
    avg_min_price = get_1m_price(line)
    return cal_rate(avg_3s_price, avg_min_price)


def get_5m_change(line):
    avg_3s_price = get_3s_price(line)
    avg_5m_price = get_5m_price(line)
    return cal_rate(avg_3s_price, avg_5m_price)


vol_3s_line = 500
vol_3s_bal = 10
vol_1m_bal = 10
vol_1m_line = 20000
incr_10s_rate = 0.01
incr_1m_rate = 0.2
incr_5m_rate = 0.3
plus = 0
minus = 0
buy_price = 0
moreless = 0

def load_file():
    path = os.getcwd()
    files = os.listdir(path)
    file_list = []
    for f in files:
        if 'etc_future_deals_201812' in f:
            file_list.append(f)
    return file_list

def sell_more(line):
    # return get_3s_price(line) < get_5m_price(line)
    if get_3s_price(line) > buy_price:
        return get_5m_change(line) < 0 and get_1m_change(line) <= -0.1
    else:
        return get_5m_change(line) < 0 or get_1m_change(line) <= -0.2


def sell_less(line):
    if moreless == 1:
        if get_now_price(line) < buy_price:
            return get_1m_change(line) > 0
        else:
            return get_10s_change(line) > 0.05 or get_1m_change(line) > 0
    # return get_3s_price(line) > get_5m_price(line)
    else:
        if get_now_price(line) < buy_price:
            return get_5m_change(line) > 0 and get_1m_change(line) >= 0.1
        else:
            return get_5m_change(line) > 0 or get_1m_change(line) >= 0.2

def check_vol(vol_3s, vol_1m):
    return vol_3s > vol_3s_line and vol_1m > vol_1m_line


def buy_more(line):
    vol_3s = get_3s_vol(line)
    vol_3s_ask = get_3s_ask_vol(line)
    vol_3s_bid = get_3s_bid_vol(line)
    vol_1m = get_1m_vol(line)
    vol_1m_ask = get_1m_ask_vol(line)
    vol_1m_bid = get_1m_bid_vol(line)
    price_10s_rate = get_10s_change(line)
    price_1m_rate = get_1m_change(line)
    price_5m_rate = get_5m_change(line)

    if 0.8 > price_1m_rate >= incr_1m_rate and 1.5 > price_5m_rate >= incr_5m_rate and price_10s_rate >= incr_10s_rate and price_10s_rate <= price_1m_rate <= price_5m_rate:
        if vol_3s_bid > vol_3s_bal * vol_3s_ask and vol_1m_bid > vol_1m_bal * vol_1m_ask and vol_3s > 1.5 * vol_3s_line:
            if check_vol(vol_3s, vol_1m):
                return True


def buy_less(line):
    global moreless
    vol_3s = get_3s_vol(line)
    vol_3s_ask = get_3s_ask_vol(line)
    vol_3s_bid = get_3s_bid_vol(line)
    vol_1m = get_1m_vol(line)
    vol_1m_ask = get_1m_ask_vol(line)
    vol_1m_bid = get_1m_bid_vol(line)
    price_10s_rate = get_10s_change(line)
    price_1m_rate = get_1m_change(line)
    price_5m_rate = get_5m_change(line)
    if price_1m_rate <= -incr_1m_rate and price_5m_rate <= -incr_5m_rate and price_10s_rate <= -incr_10s_rate and price_10s_rate >= price_1m_rate >= price_5m_rate:
        if vol_3s_ask > vol_3s_bal * vol_3s_bid and vol_1m_ask > vol_1m_bal * vol_1m_bid:
            if check_vol(vol_3s, vol_1m):
                return True
    # if price_10s_rate < -0.05 and price_1m_rate < -0.2 and price_5m_rate > 0.3 and vol_3s_ask > 10 * vol_3s_bid and vol_3s > 5000:
    #     moreless = 1
    #     return True


def get_time(line):
    return line.split(',')[-1]


def cal_profit(lines):
    global plus, minus, buy_price, moreless
    more = 0
    less = 0
    profit = 0
    for line in lines:
        if more == 1:
            if sell_more(line):
                sell_price = get_now_price(line)
                cur_profit = sell_price - buy_price
                more = 0
                profit += cur_profit
                if cur_profit > 0.01:
                    plus += 1
                elif cur_profit < -0.01:
                    minus += 1
                print("sell more, profit: %.3f, price: %.3f, time: %s" % (cur_profit, sell_price, get_time(line)), line)

        elif less == 1:
            if sell_less(line):
                sell_price = get_now_price(line)
                cur_profit = buy_price - sell_price
                less = 0
                moreless = 0
                if cur_profit > 0.01:
                    plus += 1
                elif cur_profit < -0.01:
                    minus += 1
                profit += cur_profit
                print("sell less, profit: %.3f, price: %.3f, time: %s" % (cur_profit, sell_price, get_time(line)), line)

        elif less == 0 and more == 0 and buy_more(line):
            more = 1
            buy_price = get_now_price(line) + 0.01
            print("buy more, price: %.3f, time: %s" % (buy_price, get_time(line)), line)

        elif more == 0 and less == 0 and buy_less(line):
            less = 1
            buy_price = get_now_price(line) - 0.01
            print("buy less, price: %.3f, time: %s" % (buy_price, get_time(line)), line)
    return profit


if __name__ == '__main__':
    # global vol_3s_line
    file_list = load_file()
    file_list.sort()
    # for vol_3s_line in range(5100,5400,50):
    money = 0
    plus = 0
    minus = 0
    for f in file_list:
        lines = read_file(f)
        money += cal_profit(lines)
    print(money, plus, minus)
