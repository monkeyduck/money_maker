# !/usr/bin/python
# -*- coding: UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from config_mother import leverAPI, swapAPI
import time
from utils import write_info_into_file
from entity import Coin


def stop_swap_more():
    swap_price_latest = float(swapAPI.get_specific_ticker(swap_instrument_id)['best_bid'])
    size = 1
    swap_order_result = swapAPI.take_order(swap_instrument_id, size, 3, 0, swap_price_latest, None, None)
    time.sleep(0.5)
    if swap_order_result and swap_order_result['result'] == 'true':
        swap_order_id = swap_order_result['order_id']
        return swap_order_id
    return False


if __name__ == '__main__':
    # 默认币种handle_deque
    coin = Coin("eos", "usdt")
    instrument_id = coin.get_instrument_id()
    future_instrument_id = coin.get_future_instrument_id()
    swap_instrument_id = coin.name.upper() + '-USD-SWAP'
    print('swap_instrument_id: ' + swap_instrument_id)
    print(swapAPI.get_specific_position(swap_instrument_id))