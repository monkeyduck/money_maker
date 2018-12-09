#!/usr/bin/python
# -*- coding: UTF-8 -*-

from future import OKCoinFuture
from OKCoinSpot import OKCoinSpot
import future_api_v3 as future_v3


vol_3s_line = 6000
vol_3s_bal = 10
vol_1m_bal = 10
vol_1m_line = 40000
incr_10s_rate = 0.01
incr_1m_rate = 0.2
incr_5m_rate = 0.5

# vol_3s_line = 5000
# vol_3s_bal = 10
# vol_1m_bal = 10
# vol_1m_line = 10000
# incr_10s_rate = 0.01
# incr_1m_rate = 0.2
# incr_5m_rate = 0.5

# 母账户api key
api_key = '51dd7319-c8f9-4a94-bee7-c9bbfe0032e2'
secret_key = 'E0E759CAD668C3579827DB41D9F6F083'


okFuture = OKCoinFuture(api_key, secret_key)
okSpot = OKCoinSpot(api_key, secret_key)


# v3版本母账户
api_key_v3 = '45ecd234-120f-4524-ba4f-8fc3915f7766'
secret_key_v3 = 'B0C923CED05D73698DCC4524965AF0DF'
passphrase = 'while(1);'

futureAPI = future_v3.FutureAPI(api_key_v3, secret_key_v3, passphrase, True)
