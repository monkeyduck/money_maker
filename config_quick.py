#!/usr/bin/python
# -*- coding: UTF-8 -*-

from future import OKCoinFuture
from OKCoinSpot import OKCoinSpot

vol_3s_line = 5200
vol_3s_bal = 10
vol_1m_bal = 1
vol_1m_line = 100
incr_10s_rate = 0.01
incr_1m_rate = 0.4
incr_5m_rate = 0.5

# 子账户2api key
api_key = '35b6e55b-9158-4814-a5bb-3d2a2ddb309b'
secret_key = '416B1DBD9C5017852DFC6245BB23D510'


okFuture = OKCoinFuture(api_key, secret_key)
okSpot = OKCoinSpot(api_key, secret_key)