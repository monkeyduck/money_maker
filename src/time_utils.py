# !/urs/bin/python
# -*- coding: UTF-8 -*-

import datetime


def timestamp2string(ts):
    time_stamp = int(ts)
    try:
        if len(str(time_stamp)) > 10:
            ts = float(time_stamp) / 1000
        else:
            ts = time_stamp
        d = datetime.datetime.fromtimestamp(ts)
        str1 = d.strftime("%Y-%m-%d %H:%M:%S")
        return str1
    except Exception as e:
        print(e)
        return ''
