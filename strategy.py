#!/usr/bin/python
# -*- coding: UTF-8 -*-

import pandas as pd
import numpy as np
from utils import timestamp2string


def calc_EMA(df, N):
    for i in range(len(df)):
        if i==0:
            df.ix[i,'ema']=float(df.ix[i,'close'])
        if i>0:
            df.ix[i,'ema']=((N-1)*df.ix[i-1,'ema']+2*float(df.ix[i,'close']))/(N+1)
    ema=list(df['ema'])
    return ema


def calc_MACD(df, short=12, long=26, M=9):
    emas = calc_EMA(df, short)
    emaq = calc_EMA(df, long)
    df['diff'] = pd.Series(emas) - pd.Series(emaq)
    for i in range(len(df)):
        if i==0:
            df.ix[i,'dea'] = df.ix[i,'diff']
        if i>0:
            df.ix[i,'dea'] = ((M-1)*df.ix[i-1,'dea'] + 2*df.ix[i,'diff'])/(M+1)
    df['macd'] = 2*(df['diff'] - df['dea'])
    return list(df['macd'])


def get_macd(okFuture, symbol, contract_type, type1, size=None):
    data = okFuture.future_kline(symbol, contract_type, type1, size)
    df = pd.DataFrame(data=data, columns=['timestamp', 'open', 'high', 'low', 'close', 'amount', 'amount2'])
    macd = calc_MACD(df, 7, 8, 3)
    return df


def get_spot_macd(spotAPI, instrument_id, gap):
    data = spotAPI.get_kline(instrument_id, '', '', gap)[::-1]
    df = pd.DataFrame(data=data, columns=['close', 'high', 'low', 'open', 'time', 'volume'])
    macd = calc_MACD(df, 7, 8, 3)
    return df


def check_trend(macd):
    if macd[-1] > macd[-2] > macd[-3]:
        return 'up'
    if macd[-1] < macd[-2] < macd[-3]:
        return 'down'


def get_macd_val(okFuture, symbol, contract_type, type1, size=None):
    data = okFuture.future_kline(symbol, contract_type, type1, size)
    df = pd.DataFrame(data=data, columns=['timestamp', 'open', 'high', 'low', 'close', 'amount', 'amount2'])
    macd = calc_MACD(df)
    macd_5min = macd[-1]
    diff_5min = list(df['diff'])[-1]
    dea_5min = list(df['dea'])[-1]
    last_5min_macd_ts = list(df['timestamp'])[-1]
    return macd_5min, diff_5min, dea_5min, last_5min_macd_ts


def calc_KDJ(df, n, ksgn='close'):
    '''
        【输入】
            df, pd.dataframe格式数据源
            n，时间长度
            ksgn，列名，一般是：close收盘价
        【输出】    
            df, pd.dataframe格式数据源,
            增加了一栏：_{n}，输出数据
    '''
    lowList = df['low'].rolling(n).min()
    # lowList = pd.rolling(df['low'], n).min()
    lowList.fillna(value=df['low'].expanding().min(), inplace=True)
    highList = df['high'].rolling(n).max()
    # highList = pd.rolling_max(df['high'], n)
    # highList.fillna(value=pd.expanding_max(df['high']), inplace=True)
    highList.fillna(value=df['high'].expanding().max(), inplace=True)

    rsv = (df[ksgn] - lowList) / (highList - lowList) * 100

    df['kdj_k'] = pd.ewma(rsv, com=2)
    df['kdj_d'] = pd.ewma(df['kdj_k'], com=2)
    df['kdj_j'] = 3.0 * df['kdj_k'] - 2.0 * df['kdj_d']
    # print('n df',len(df))
    return df


def KDJ(date,N=9,M1=3,M2=3):
    datelen=len(date)
    array=np.array(date)
    kdjarr=[]
    for i in range(datelen):
        if i-N<0:
            b=0
        else:
            b=i-N+1
        rsvarr=array[b:i+1,0:5]
        rsv=(float(rsvarr[-1,-1])-float(min(rsvarr[:,3])))/(float(max(rsvarr[:,2]))-float(min(rsvarr[:,3])))*100
        if i==0:
            k=rsv
            d=rsv
        else:
            k=1/float(M1)*rsv+(float(M1)-1)/M1*float(kdjarr[-1][2])
            d=1/float(M2)*k+(float(M2)-1)/M2*float(kdjarr[-1][3])
        j=3*k-2*d
        kdjarr.append(list((rsvarr[-1,0],rsv,k,d,j)))
    return kdjarr


if __name__ == '__main__':
    symbol = "etc_usd"
    contract_type = "quarter"
    type1 = "5min"
    # print(get_macd(symbol, contract_type, type1))
    from config_avg import okFuture
    data = okFuture.future_kline(symbol, contract_type, "5min", None)
    df = pd.DataFrame(data=data, columns=['timestamp', 'open', 'high', 'low', 'close', 'amount', 'amount2'])
    macd = calc_MACD(df)
    diff = list(df['diff'])
    dea = list(df['dea'])
    timestamp = list(df['timestamp'])

    for i in range(0, len(diff)):
        print("macd: %.6f, diff: %.6f, dea: %.6f, time: %s" % (2 * (diff[i] - dea[i]), diff[i], dea[i], timestamp2string(timestamp[i])))

    print(macd[-1], list(df['diff'])[-1], list(df['dea'])[-1], timestamp2string(timestamp[-1]))

    # symbol = "etc_usd"
    # contract_type = "quarter"
    # type1 = "5min"
    # data = okFuture.future_kline(symbol, contract_type, "5min", 300)
    # df = pd.DataFrame(data=data, columns=['timestamp', 'open', 'high', 'low', 'close', 'amount', 'amount2'])
    # macd = calc_MACD(df)
    # diff = list(df['diff'])
    # dea = list(df['dea'])
    # timestamp = list(df['timestamp'])
    #
    # for i in range(0, len(diff)):
    #     print("macd: %.6f, diff: %.6f, dea: %.6f, time: %s" % (2 * (diff[i] - dea[i]), diff[i], dea[i], timestamp2string(timestamp[i])))

    # print(macd[-1], diff[-1], dea[-1], timestamp2string(timestamp[-1]))
    #

    # macd_5min, diff_5min, dea_5min, last_5min_macd_ts = get_macd("etc_usd", "quarter", "5min")
    # print(macd_5min, diff_5min, dea_5min, timestamp2string(last_5min_macd_ts))

    # x = list(map(timestamp2string, list(df['timestamp'])))
    # time2macd = {}
    # for i in range(len(x)):
    #     time2macd[x[i]] = macd[i]
    #     if macd[i] > 0.003 or macd[i] < -0.003:
    #         print(x[i], macd[i])
    # print(x[-1])
    # print(time2macd['2018-10-17 22:22:00'])
    # print(time2macd['2018-10-01 03:00:00'])
    # plt.plot(x, macd)
    # plt.show()
    # print(macd)
