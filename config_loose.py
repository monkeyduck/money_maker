#!/usr/bin/python
# -*- coding: UTF-8 -*-

from future import OKCoinFuture
from OKCoinSpot import OKCoinSpot
import future_api_v3 as future_v3


vol_3s_line = 15000
vol_3s_bal = 9
vol_1m_bal = 6
vol_1m_line = 30000
incr_10s_rate = 0
incr_1m_rate = 0.2
incr_5m_rate = 0.2

# 子账户1api key
api_key = '2de78a3d-25d4-4ee3-8509-ae900249d10d'
secret_key = 'AAF6BCD07FC0B2F5D93FAC3F79700B7F'


okFuture = OKCoinFuture(api_key, secret_key)
okSpot = OKCoinSpot(api_key, secret_key)

# v3版本子账户1
api_key_v3 = '7aab0b51-bbdc-4279-be55-c29ad9c03419'
secret_key_v3 = '91E0E9A60590D8C66203DC6D744B7C7A'
passphrase = 'while(1);'

futureAPI = future_v3.FutureAPI(api_key_v3, secret_key_v3, passphrase, True)