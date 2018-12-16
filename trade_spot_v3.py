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


def buy_all_position(spotAPI, instrument_id, buy_price):
    usdt_account = spotAPI.get_coin_account_info("usdt")
    usdt_available = float(usdt_account['available'])
    amount = math.floor(usdt_available / buy_price)
    if amount > 1:
        return spot_buy(spotAPI, instrument_id, amount, buy_price)
    return False


def sell_all_position(spotAPI, instrument_id, sell_price):
    coin = instrument_id.split('_')[0]
    coin_account = spotAPI.get_coin_account_info(coin)
    coin_available = float(coin_account['available'])
    return spot_sell(spotAPI, instrument_id, coin_available, sell_price)



def stat_deal_detail():
    total_fee = 0
    total_coin = 0
    total_usdt = 0
    start = 1
    ret_count = 100
    count = 0
    while ret_count >= 99:
        result = spotAPI.get_ledger_record_paging("eos", start, '', 100)
        ret_count = len(result[0])
        print('count: %d' % ret_count)
        start = result[1]['before']
        for each_r in result[0]:
            if each_r['type'] == 'trade':
                count += 1
                o_id = each_r['details']['order_id']
                print('get deal details of order_id: %s' % o_id)
                ret = spotAPI.get_fills(o_id, instrument_id, '', '', 100)
                item = ret[0]
                fee_item = item[0]
                coin_item = item[1]
                usdt_itme = item[2]
                coin_size = float(coin_item['size'])
                usdt_size = float(usdt_itme['size'])
                total_fee += float(fee_item['fee'])
                price = float(coin_item['price'])
                created_at = fee_item['created_at']
                if coin_item['side'] == 'buy' and usdt_itme['side'] == 'sell':
                    total_coin += coin_size
                    total_usdt -= usdt_size
                    print('%s: buy %.1f eos at price: %.4f, usdt: -%.4f' % (created_at, coin_size, price, usdt_size))
                elif coin_item['side'] == 'sell' and usdt_itme['side'] == 'buy':
                    total_coin -= coin_size
                    total_usdt += usdt_size
                    print('%s: sell %.1f eos at price: %.4f, usdt: +%.4f' % (created_at, coin_size, price, usdt_size))
                time.sleep(0.1)
        print('after %d transactions, total_coin: %.4f, total_usdt: %.4f, total_fee: %.4f\r\n' % (
        count, total_coin, total_usdt, total_fee))
        time.sleep(1)


if __name__ == '__main__':

    from config_avg import spotAPI

    instrument_id = "eos_usdt"
    ret = spotAPI.get_kline(instrument_id, '', '', 60)
    print(ret)
    ret = spotAPI.get_specific_ticker(instrument_id)
    print(ret)


