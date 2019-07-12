#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
from collections import deque

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


class Coin:
    def __init__(self, name, refer):
        self.name = name
        self.refer = refer
        self.deque_3s = deque()
        self.deque_30s = deque()
        self.deque_5min = deque()
        self.ind_3s = Indicator(3)
        self.ind_60s = Indicator(60)
        self.ind_5min = Indicator(300)

    def gen_file_name(self):
        file_path = os.getcwd()
        transaction = file_path + '/' + self.name + '_transaction.txt'
        deal = file_path + '/' + self.name + '_deals.txt'
        return transaction, deal

    def gen_future_file_name(self):
        file_path = os.getcwd()
        transaction = file_path + '/' + self.name + '_future_transaction.txt'
        deal = file_path + '/' + self.name + '_future_deals.txt'
        return transaction, deal

    def gen_full_name(self):
        return self.name + "_" + self.refer

    def get_depth_filename(self):
        file_path = os.getcwd()
        depth = file_path + '/' + self.name + '_future_depth.txt'
        return depth

    def get_instrument_id(self):
        return self.name + "_" + self.refer

    def get_future_instrument_id(self):
        return self.name.upper() + "-USD-190628"

    def process_entity(self, entity, now_time_second):
        self.handle_deque(self.deque_3s, entity, now_time_second, self.ind_3s)
        self.handle_deque(self.deque_30s, entity, now_time_second, self.ind_60s)
        self.handle_deque(self.deque_5min, entity, now_time_second, self.ind_5min)

    def handle_deque(self, deq, entity, ts, ind):
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

    def get_avg_price_3s(self):
        return self.ind_3s.cal_avg_price()

    def get_avg_price_60s(self):
        return self.ind_60s.cal_avg_price()

    def get_avg_price_5min(self):
        return self.ind_5min.cal_avg_price()


class IndexEntity:
    def __init__(self, _coin_name, _index, _timestamp):
        self.coin_name = _coin_name
        self.index = _index
        self.timestamp = _timestamp


class IndexIndicator:
    def __init__(self, coin_name, interval):
        self.coin_name = coin_name
        self.interval = interval
        self.index = 0
        self.index_num = 0

    def add_index(self, index_entity):
        self.index += index_entity.index
        self.index_num += 1

    def minus_index(self, index_entity):
        self.index -= index_entity.index
        self.index_num -= 1

    def cal_avg_price(self):
        if self.index_num != 0:
            return round(float(self.index) / float(self.index_num), 4)
        else:
            return 0


class DealEntity:
    def __init__(self, _id, _price, _amount, _time, _type):
        self.id = _id
        self.price = _price
        self.amount = _amount
        self.time = _time
        self.type = _type

    def detail(self):
        return str(self.time) + ': ' + self.type + str(self.amount) + '\t at price: ' + str(self.price)


class Indicator:
    def __init__(self, interval):
        self.interval = interval
        self.vol = 0
        self.avg_price = 0
        self.price = 0
        self.price_num = 0
        self.bid_vol = 0
        self.ask_vol = 0

    def cal_avg_price(self):
        if self.price_num != 0:
            return round(float(self.price) / float(self.price_num), 4)
        else:
            return 0

    def add_vol(self, deal_entity):
        self.vol += deal_entity.amount
        if deal_entity.type == 'ask':
            self.ask_vol += deal_entity.amount
        elif deal_entity.type == 'bid':
            self.bid_vol += deal_entity.amount

    def minus_vol(self, deal_entity):
        self.vol -= deal_entity.amount
        if deal_entity.type == 'ask':
            self.ask_vol -= deal_entity.amount
        elif deal_entity.type == 'bid':
            self.bid_vol -= deal_entity.amount

    def add_price(self, deal_entity):
        self.price_num += 1
        self.price += deal_entity.price

    def minus_price(self, deal_entity):
        self.price_num -= 1
        self.price -= deal_entity.price


class Order:
    def __init__(self, order_id, price, amount, type, order_time):
        self.order_id = order_id
        self.price = price
        self.amount = amount
        self.type = type
        self.order_time = order_time

    def detail(self):
        return self.type + " " + str(self.amount) + ' at price ' + str(self.price) + ', order_id: ' + self.order_id


class Position:
    def __init__(self, price, amount, stop_loss, time, side):
        self.price = price
        self.amount = amount
        self.stop_loss = stop_loss
        self.time = time
        self.side = side