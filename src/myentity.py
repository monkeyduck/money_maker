#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os


class Coin:
    def __init__(self, name, refer):
        self.name = name
        self.refer = refer

    def gen_file_name(self):
        file_path = os.getcwd()
        transaction = file_path + '/' + self.name + '_transaction.txt'
        deal = file_path + '/' + self.name + '_deals.txt'
        return transaction, deal

    def gen_full_name(self):
        return self.name + "_" + self.refer


class DealEntity:
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
        return str(self.time) + ': ' + category + str(self.amount) + '\t at price: ' + str(self.price)


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