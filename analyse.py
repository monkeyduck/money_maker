#!/usr/bin/python
# -*- coding: UTF-8 -*-

import codecs
import json
import datetime
import time
from trade import okSpot


class ticker:
    def __init__(self, json):
        self.channel = json['channel']
        self.data = json['data']
        for json_data in json.loads(self.data):
            self.transactions.append()


buy_amount = [0.0, 0.0, 0.0]
sell_amount = [0.0, 0.0, 0.0]
buy_count = [0, 0, 0]
sell_count = [0, 0, 0]


class dealEntity:
    def __init__(self, _id, _price, _amount, _time, _type):
        self.id = _id
        self.price = _price
        self.amount = _amount
        self.time = _time
        self.type = _type

    def detail(self):
        if self.type == 'ask':
            category = 'sell '
        else:
            category = 'buy  '
        return self.time + ': ' + category + self.amount + '\t at price: ' + self.price

    def filter_high(self):
        if float(self.amount) > 2000:
            if self.type == 'ask':
                sell_count[0] += 1
                sell_amount[0] += float(self.amount)
            else:
                buy_count[0] += 1
                buy_amount[0] += float(self.amount)
        elif float(self.amount) > 500:
            if self.type == 'ask':
                sell_count[1] += 1
                sell_amount[1] += float(self.amount)
            else:
                buy_count[1] += 1
                buy_amount[1] += float(self.amount)
        elif float(self.amount) < 100:
            if self.type == 'ask':
                sell_count[2] += 1
                sell_amount[2] += float(self.amount)
            else:
                buy_count[2] += 1
                buy_amount[2] += float(self.amount)


class depthEntity:
    def __init__(self, json):
        self.asks = json['asks']
        self.bids = json['bids']
        self.timestamp = json['timestamp']

    def print_detail(self):
        print (timestamp2string(self.timestamp))
        for i in range(0, 20):
            print ('sell' + str(20 - i) + '\t' + self.asks[i][0] + ':\t' + self.asks[i][1])
        for i in range(0, 20):
            print ('buy ' + str(i + 1) + '\t' + self.bids[i][0] + ':\t' + self.bids[i][1])

    def cal_ratio(self):
        bid = 0.0
        ask = 0.0
        bid10 = 0.0
        ask10 = 0.0
        bid5 = 0.0
        ask5 = 0.0
        for i in range(0, 20):
            if i < 10:
                ask10 += float(self.asks[19 - i][1])
                bid10 += float(self.bids[i][1])
            if i < 5:
                ask5 += float(self.asks[19 - i][1])
                bid5 += float(self.bids[i][1])
            bid += float(self.bids[i][1])
            ask += float(self.asks[i][1])
        ratio20 = (bid - ask) / (bid + ask) * 100
        ratio10 = (bid10 - ask10) / (bid10 + ask10) * 100
        ratio5 = (bid5 - ask5) / (bid5 + ask5) * 100
        print ('5: ' + str(ratio5))
        print ('10: ' + str(ratio10))
        print ('20: ' + str(ratio20))


class tickerEntity:
    def __init__(self, json):
        self.high = json['high']
        self.low = json['low']
        self.vol = json['vol']
        self.last = json['last']
        self.buy = json['buy']
        self.change = json['change']
        self.sell = json['sell']
        self.dayLow = json['dayLow']
        self.close = json['close']
        self.dayHigh = json['dayHigh']
        self.open = json['open']
        self.timestamp = json['timestamp']


def read_file(file_path):
    with codecs.open(file_path, 'r', 'UTF-8') as f:
        lines = f.readlines()
    return lines


def check_3s_vol(line, val):
    segs = line.split(',')
    try:
        vol = segs[5].split(':')[1]
        if float(vol) > val:
            print (line)
    except:
        print ('exception')


def check_1min_vol(line, val):
    segs = line.split(',')
    vol = segs[8].split(':')[1]
    if float(vol) > val:
        return True
    return False


def check_ask_bid(line):
    segs = line.split(',')
    if len(segs) > 10:
        ask_vol = float(segs[9].split(':')[1])
        bid_vol = float(segs[10].split(':')[1])
        ths_vol = float(segs[8].split(':')[1])
        if ths_vol > 100000:
            if ask_vol > 2 * bid_vol or bid_vol > 2 * ask_vol:
                return True
    return False


def check_incr_rate(line):
    segs = line.split(',')
    if len(segs) > 10:
        price_3s = float(segs[1].split(':')[1])
        price_10s= float(segs[2].split(':')[1])
        price_1m = float(segs[3].split(':')[1])
        price_5m = float(segs[4].split(':')[1])
        if price_3s > price_1m * 1.003 and price_3s > price_10s * 1.001:
            return True


def check_decr_rate(line):
    segs = line.split(',')
    if len(segs) > 10:
        price_3s = float(segs[1].split(':')[1])
        price_10s= float(segs[2].split(':')[1])
        price_1m = float(segs[3].split(':')[1])
        price_5m = float(segs[4].split(':')[1])
        if price_3s < price_1m * 0.997 and price_3s < price_10s * 0.999:
            return True


def extract_time(line):
    segs = line.split(',')
    n = len(segs)
    return segs[n - 1].strip()


def query_24h_vol():
    avg_vol = float(okSpot.ticker("eos_usdt")['ticker']['vol']) / 24 / 60
    print(avg_vol)

if __name__=='__main__':
    # query_24h_vol()
    path = '/Users/linchuanli/PycharmProjects/moneymaker'
    lines = read_file(path + '/etc_deals_20180919.txt')
    last_time = ''
    last_line = ''
    for line in lines:
    #     if last_line != '':
    #         last_time = extract_time(last_line)
    #         this_time = extract_time(line)
    #         # print(time.mktime(time.strptime(last_time,'%Y-%m-%d %H:%M:%S')))
    #         if time.mktime(time.strptime(this_time,'%Y-%m-%d %H:%M:%S')) - time.mktime(time.strptime(last_time, '%Y-%m-%d %H:%M:%S')) > 10:
    #             print(last_line)
    #             print(line + '\n')
    #     last_line = line

        if check_1min_vol(line, 16000):
            if check_incr_rate(line) or check_decr_rate(line):
                # if check_ask_bid(line):
                # print(line)
                    stime = extract_time(line)
                    if stime != last_time:
                        print(line)
                        last_time = stime