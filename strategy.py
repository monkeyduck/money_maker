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


def calc_N(df, num):
    for i in range(len(df)):
        if i == 0:
            df.ix[i, 'N'] = float(df.ix[i, 'high']) - float(df.ix[i, 'low'])
            df.ix[i, 'highest'] = float(df.ix[i, 'high'])
            df.ix[i, 'lowest'] = float(df.ix[i, 'low'])
        elif i < num:
            highest = 0
            lowest = 1000000
            sumN = 0
            for j in range(0, i):
                sumN += df.ix[j, 'N']
                highest = max(highest, float(df.ix[j, 'high']))
                lowest = min(lowest, float(df.ix[j, 'low']))
            high = float(df.ix[i, 'high'])
            low = float(df.ix[i, 'low'])
            pre_close = float(df.ix[i-1, 'close'])
            true_range = max(high - low, high - pre_close, pre_close - low)
            df.ix[i, 'N'] = (sumN + true_range) / (i + 1)
            df.ix[i, 'highest'] = highest
            df.ix[i, 'lowest'] = lowest
        else:
            sumN = 0
            high = float(df.ix[i, 'high'])
            low = float(df.ix[i, 'low'])
            pre_close = float(df.ix[i - 1, 'close'])
            highest = 0
            lowest = 1000000
            for j in range(1, num):
                sumN += df.ix[i-j, 'N']
                highest = max(highest, float(df.ix[i-j, 'high']))
                lowest = min(lowest, float(df.ix[i-j, 'low']))
            true_range = max(high - low, high - pre_close, pre_close - low)
            df.ix[i, 'highest'] = max(highest, float(df.ix[i, 'high']))
            df.ix[i, 'lowest'] = min(lowest, float(df.ix[i, 'low']))
            df.ix[i, 'N'] = (sumN + true_range) / num
    N = list(df['N'])
    return N


def get_future_Nval(okFuture, symbol, contract_type, type, size, window_size=20):
    data = okFuture.future_kline(symbol, contract_type, type, size)
    df = pd.DataFrame(data=data, columns=['timestamp', 'open', 'high', 'low', 'close', 'amount', 'amount2'])
    calc_N(df, window_size)
    return df


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


def get_spot_boll(spotAPI, instrument_id, gap):
    data = spotAPI.get_kline(instrument_id, '', '', gap)[::-1]
    df = pd.DataFrame(data=data, columns=['close', 'high', 'low', 'open', 'time', 'volume'])
    calc_boll(df, 26)
    return df


def check_trend(macd):
    if macd[-1] >= macd[-2] >= macd[-3] >= macd[-4]:
        return 'up'
    if macd[-1] <= macd[-2] <= macd[-3] <= macd[-4]:
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


# def RSI(t, periods=10):
#     length = len(t)
#     rsies = [np.nan]*length
#     #数据长度不超过周期，无法计算；
#     if length <= periods:
#         return rsies
#     #用于快速计算；
#     up_avg = 0
#     down_avg = 0
#
#     #首先计算第一个RSI，用前periods+1个数据，构成periods个价差序列;
#     first_t = t[:periods+1]
#     for i in range(1, len(first_t)):
#         #价格上涨;
#         if first_t[i] >= first_t[i-1]:
#             up_avg += first_t[i] - first_t[i-1]
#         #价格下跌;
#         else:
#             down_avg += first_t[i-1] - first_t[i]
#     up_avg = up_avg / periods
#     down_avg = down_avg / periods
#     rs = up_avg / down_avg
#     rsies[periods] = 100 - 100/(1+rs)
#
#     #后面的将使用快速计算；
#     for j in range(periods+1, length):
#         up = 0
#         down = 0
#         if t[j] >= t[j-1]:
#             up = t[j] - t[j-1]
#             down = 0
#         else:
#             up = 0
#             down = t[j-1] - t[j]
#         #类似移动平均的计算公式;
#         up_avg = (up_avg*(periods - 1) + up)/periods
#         down_avg = (down_avg*(periods - 1) + down)/periods
#         rs = up_avg/down_avg
#         rsies[j] = 100 - 100/(1+rs)
#     return rsies

def RSI(df, period=14):
    """
    Relative Strength Index
    """
    series = df['close']
    delta = series.diff().dropna()
    u = delta * 0
    d = u.copy()
    u[delta > 0] = delta[delta > 0]
    d[delta < 0] = -delta[delta < 0]
    u[u.index[period - 1]] = np.mean(u[:period]) # first value is sum of avg gains
    u = u.drop(u.index[:(period - 1)])
    d[d.index[period - 1]] = np.mean(d[:period]) # first value is sum of avg losses
    d = d.drop(d.index[:(period - 1)])
    avgGain = u.ewm(com=period - 1, adjust=False).mean()
    avgLoss = d.ewm(com=period - 1, adjust=False).mean()
    rs = avgGain / avgLoss
    result = 100 - 100 / (1 + rs)
    return result


def calc_boll(df, period=20):
    df['mid'] = df['close'].rolling(period).mean()
    df['tmp2'] = df['close'].rolling(period).std()
    df['top'] = df['mid'] + 2 * df['tmp2']
    df['bottom'] = df['mid'] - 2 * df['tmp2']
    return df


class future_kline_entity:
    def __init__(self, data):
        self.timestamp = data[0]
        self.open = data[1]
        self.high = data[2]
        self.low  = data[3]
        self.close = data[4]
        self.volume = data[5]
        self.currency_volume = data[6]


if __name__ == '__main__':
    symbol = "etc_usd"
    contract_type = "quarter"
    type1 = "5min"
    # print(get_macd(symbol, contract_type, type1))
    from config_avg import okFuture, spotAPI, futureAPI
    # N = get_future_Nval(okFuture, symbol, contract_type, '1h', 100)
    # print(N)
    # data = okFuture.future_kline(symbol, contract_type, "1min", 200)
    # df = pd.DataFrame(data=data, columns=['timestamp', 'open', 'high', 'low', 'close', 'amount', 'amount2'])
    # print(df)
    # df = get_future_Nval(okFuture, symbol, contract_type, "1min", 200)
    # print(list(df['lowest'])[-1])
    k_line = futureAPI.get_kline("BTC-USD-190329", 60, '2018-12-26T02:31:00Z', '2018-12-26T02:41:00Z')
    print(k_line)
    # k_line = k_line[::-1]
    # for i in range(1, len(k_line)):
    #     prev = future_kline_entity(k_line[i-1])
    #     if prev.open == prev.high and prev.close == prev.low and prev.high >= 1.003 * prev.low:
    #         print('前一分钟下跌')
    #         print(k_line[i])
    #     elif prev.open == prev.low and prev.close == prev.high and prev.high >= 1.003 * prev.low:
    #         print('前一分钟上涨')
    #         print(k_line[i-1])
    #         print(k_line[i])
    # print(k_line)
    kline = okFuture.future_kline("btc", "quarter", "1min", 200)
    print(kline)
    # df = Boll(df, 26)
    # for i in range(0,20):
    #     print('%.4f, %.4f, %s' % (list(df['mid'])[180 + i], list(df['top'])[180+i], timestamp2string(list(df['timestamp'])[180+i])))
    # # print('rsi: ', RSI(df))

    # ret = spotAPI.get_kline("eos_usdt", '', '', 60)
    # print(ret)

