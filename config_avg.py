#!/usr/bin/python
# -*- coding: UTF-8 -*-

from future import OKCoinFuture
from OKCoinSpot import OKCoinSpot
import future_api_v3 as future_v3
import spot_v3

vol_3s_line = 500
vol_3s_bal = 10
vol_1m_bal = 10
vol_1m_line = 20000
incr_10s_rate = 0.01
incr_1m_rate = 0.2
incr_5m_rate = 0.3

# 子账户3 api key
api_key = '74b9b1b3-c607-4287-93a0-a739f3bd8e7e'
secret_key = '2271D02AD672318FBA7806FFDC24B56E'


okFuture = OKCoinFuture(api_key, secret_key)
okSpot = OKCoinSpot(api_key, secret_key)

# v3版本子账户3
api_key_v3 = 'fbf73e84-b152-4a67-b72d-a9481f7f618b'
secret_key_v3 = 'D2B15EC9115ECCD7F8D43F57F6C0D593'
passphrase = 'while(1);'

futureAPI = future_v3.FutureAPI(api_key_v3, secret_key_v3, passphrase, True)
spotAPI = spot_v3.SpotAPI(api_key_v3, secret_key_v3, passphrase, True)

