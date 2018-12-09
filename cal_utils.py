#!/usr/bin/python
# -*- coding: UTF-8 -*-


def cal_rate(cur_price, last_price):
    if last_price != 0:
        return round((cur_price - last_price) / last_price, 4) * 100
    else:
        return 0