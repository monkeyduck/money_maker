# !/usr/bin/python
# -*- coding: UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from config_mother import leverAPI


if __name__ == '__main__':
    # print(leverAPI.borrow_coin("eos-usdt", "usdt", 1))
    print(leverAPI.get_coin_account_info("eos_usdt"))
