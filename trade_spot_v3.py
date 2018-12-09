#!/usr/bin/python
# -*- coding: UTF-8 -*-

import json
import math
from utils import send_email,timestamp2string
import time
import codecs
try:
    import thread
except ImportError:
    import _thread as thread


def spot_buy(spotAPI, instrument_id, amount, price):
    ret = spotAPI.take_order('limit', 'buy', instrument_id, amount, margin_trading=1, client_oid='', price=price, funds='', )
    if ret and ret['result']:
        return ret["order_id"]
    return False


def spot_sell(spotAPI, instrument_id, amount, price):
    ret = spotAPI.take_order('limit', 'sell', instrument_id, amount, margin_trading=1, client_oid='', price=price, funds='', )
    if ret and ret['result']:
        return ret["order_id"]
    return False


def spot_revoke(spotAPI, instrument_id, order_id):
    ret = spotAPI.revoke_order(instrument_id, order_id)
    print(ret)
    return ret


if __name__ == '__main__':

    from config_avg import spotAPI

    instrument_id = "eos_usdt"
    # future api test
    # result = buyin_more_batch(spotAPI, coin_name, time_type, 7, 20, 5)
    # result = spotAPI.get_coin_account("etc")
    # result = buyin_less(spotAPI, coin_name, time_type, 6.4, 1, 20)

    # result = spot_sell(spotAPI, instrument_id, 0.1, 8.059)
    result = spotAPI.get_ledger_record_paging("eos", 1, '', 100)
    print('count: %d' % len(result))
    for each_r in result:
        o_id = each_r['details']['order_id']
        spotAPI.get_fills(o_id, instrument_id, 1, '', 100)
    print(result)
    # time.sleep(10)
    # ret = spot_revoke(spotAPI, instrument_id, '1924000642830336')
    # print('finished:', ret)
    