# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate, get_timestamp, string2timestamp
from trade_spot_v3 import buy_all_position, sell_all_position, spot_buy
from trade_v3 import buyin_less, sell_less, ensure_buyin_less, ensure_sell_less, get_latest_future_price, buyin_more, \
    sell_more, ensure_buyin_more, ensure_sell_more
from entity import Coin, Indicator, DealEntity
from strategy import get_spot_macd
import time
import json
import traceback
from collections import deque
import websocket
import codecs
import sys
import math
import asyncio
import websockets
import json
import requests
import dateutil.parser as dp
import hmac
import base64
import zlib
import datetime

deque_min = deque()
deque_10s = deque()
deque_3s = deque()
deque_3m = deque()
latest_price = 0
ind_1min = Indicator(60)
ind_10s = Indicator(10)
ind_1s = Indicator(1)
ind_3m = Indicator(180)
less = 0
lessless = 0
lessmore = 0
last_3min_macd_ts = 0

last_avg_price = 0

future_buy_time = 0
future_buy_price = 0
future_more_buy_price = 0

spot_buy_time = 0
spot_buy_price = 0

write_lines = []


def handle_deque(deq, entity, ts, ind):
    while len(deq) > 0:
        left = deq.popleft()
        if float(left.time + ind.interval) > float(ts):
            deq.appendleft(left)
            break
        ind.minus_vol(left)
        ind.minus_price(left)
    deq.append(entity)
    ind.add_price(entity)
    ind.add_vol(entity)


def check_do_future_less(price_3m_change, price_1m_change, price_10s_change):
    if ind_1min.vol > 300000 and ind_1min.ask_vol > 1.5 * ind_1min.bid_vol \
            and ind_3m.vol > 500000 and ind_3m.ask_vol > 1.3 * ind_3m.bid_vol and -1.2 < price_1m_change \
            and price_3m_change < price_1m_change < -0.3 and price_10s_change <= -0.05 and new_macd < 0:
        return True
    elif ind_1min.vol > 200000 and ind_1min.ask_vol > 3 * ind_1min.bid_vol \
            and ind_3m.vol > 300000 and ind_3m.ask_vol > 2 * ind_3m.bid_vol \
            and price_3m_change < price_1m_change < -0.3 and price_10s_change <= -0.05 \
            and new_macd < 0:
        return True
    return False


def process_message(message):
    global latest_price, last_avg_price, less, deque_3s, deque_10s, deque_min, future_buy_price,\
        deque_3m, ind_3s, ind_10s, ind_1min, ind_3m, write_lines, last_3min_macd_ts, new_macd, lessless,\
        future_buy_time, spot_buy_time, spot_sell_price, spot_buy_price, lessmore, future_more_buy_price
    jmessage = json.loads(message)
    print(jmessage)
    ts = time.time()
    now_time = timestamp2string(ts)

    for each_message in jmessage:
        for jdata in each_message['data']:
            latest_price = float(jdata[1])
            deal_entity = DealEntity(jdata[0], float(jdata[1]), round(float(jdata[2]), 3), ts, jdata[4])

            handle_deque(deque_3s, deal_entity, ts, ind_1s)
            handle_deque(deque_10s, deal_entity, ts, ind_10s)
            handle_deque(deque_min, deal_entity, ts, ind_1min)
            handle_deque(deque_3m, deal_entity, ts, ind_3m)

            avg_3s_price = ind_1s.cal_avg_price()
            avg_10s_price = ind_10s.cal_avg_price()
            avg_min_price = ind_1min.cal_avg_price()
            avg_3m_price = ind_3m.cal_avg_price()
            price_10s_change = cal_rate(avg_3s_price, avg_10s_price)
            price_1m_change = cal_rate(avg_3s_price, avg_min_price)
            price_3m_change = cal_rate(avg_3s_price, avg_3m_price)

            # 做空
            if less == 0 and check_do_future_less(price_3m_change, price_1m_change, price_10s_change):
                sell_id = sell_all_position(spotAPI, instrument_id, latest_price - 0.001)
                if sell_id:
                    spot_buy_time = int(ts)
                    time.sleep(1)
                    sell_order_info = spotAPI.get_order_info(sell_id, instrument_id)
                    if sell_order_info['status'] == 'filled' or sell_order_info['status'] == 'part_filled':
                        less = 1
                        spot_sell_price = float(sell_order_info['price'])
                        info = now_time + u' 现货全部卖出！！！spot_sell_price：' + str(spot_sell_price)
                        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                            f.writelines(info + '\n')
                    else:
                        spotAPI.revoke_order_exception(instrument_id, sell_id)
            if less == 1:
                if price_1m_change > 0 and new_macd > 0:
                    usdt_account = spotAPI.get_coin_account_info("usdt")
                    usdt_available = float(usdt_account['available'])
                    amount = math.floor(usdt_available / latest_price)
                    if amount > 0:
                        buy_id = spot_buy(spotAPI, instrument_id, amount, latest_price)
                        if buy_id:
                            time.sleep(3)
                            order_info = spotAPI.get_order_info(buy_id, instrument_id)
                            if order_info['status'] == 'filled':
                                less = 0
                                spot_buy_price = order_info['price']
                                info = u'macd > 0, 买入现货止盈！！！买入价格：' + str(spot_buy_price) + u', ' + now_time
                                with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                                    f.writelines(info + '\n')
                            else:
                                attempts = 5
                                while attempts > 0:
                                    attempts -= 1
                                    spotAPI.revoke_order_exception(instrument_id, buy_id)
                                    time.sleep(1)
                                    order_info = spotAPI.get_order_info(buy_id, instrument_id)
                                    if order_info['status'] == 'cancelled':
                                        break
                    else:
                        less = 0

                if int(ts) - spot_buy_time > 60:
                    if latest_price > spot_sell_price and price_1m_change >= 0 and price_10s_change >= 0 \
                            and (ind_1min.bid_vol > ind_1min.ask_vol or price_3m_change >= 0):
                        usdt_account = spotAPI.get_coin_account_info("usdt")
                        usdt_available = float(usdt_account['available'])
                        amount = math.floor(usdt_available / latest_price)
                        if amount > 0:
                            buy_id = spot_buy(spotAPI, instrument_id, amount, latest_price)
                            if buy_id:
                                time.sleep(3)
                                order_info = spotAPI.get_order_info(buy_id, instrument_id)
                                if order_info['status'] == 'filled':
                                    less = 0
                                    spot_buy_price = order_info['price']
                                    info = u'macd > 0, 买入现货止损！！！买入价格：' + str(spot_buy_price) + u', ' + now_time
                                    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                                        f.writelines(info + '\n')
                                else:
                                    attempts = 5
                                    while attempts > 0:
                                        attempts -= 1
                                        spotAPI.revoke_order_exception(instrument_id, buy_id)
                                        time.sleep(1)
                                        order_info = spotAPI.get_order_info(buy_id, instrument_id)
                                        if order_info['status'] == 'cancelled':
                                            break
                        else:
                            less = 0

            holding_status = 'spot_less: %d' % less
            price_info = deal_entity.type + u' now_price: %.4f, 3s_price: %.4f, 10s_price: %.4f, 1m_price: %.4f, ' \
                                            u'3min_price: %.4f' \
                         % (latest_price, avg_3s_price, avg_10s_price, avg_min_price, avg_3m_price)
            vol_info = u'cur_vol: %.3f, 3s vol: %.3f, 10s vol: %.3f, 1min vol: %.3f, ask_vol: %.3f, bid_vol: %.3f, ' \
                       u'3s_ask_vol: %.3f, 3s_bid_vol: %.3f, 3min vol: %.3f, 3min_ask_vol: %.3f, 3min_bid_vol: %.3f' \
                       % (deal_entity.amount, ind_1s.vol, ind_10s.vol, ind_1min.vol, ind_1min.ask_vol, ind_1min.bid_vol,
                          ind_1s.ask_vol, ind_1s.bid_vol, ind_3m.vol, ind_3m.ask_vol, ind_3m.bid_vol)
            rate_info = u'10s_rate: %.2f%%, 1min_rate: %.2f%%, 3min_rate: %.2f%%, new_macd: %.6f' \
                        % (price_10s_change, price_1m_change, price_3m_change, new_macd)
            write_info = holding_status + u', ' + price_info + u', ' + vol_info + u', ' + rate_info + u', ' + now_time + '\r\n'
            write_lines.append(write_info)
            if len(write_lines) >= 100:
                with codecs.open(file_deal, 'a+', 'UTF-8') as f:
                    f.writelines(write_lines)
                    write_lines = []

            print(holding_status + '\r\n' + price_info + '\r\n' + vol_info + '\r\n' + rate_info + u', ' + now_time)


def run_websocket(coin_name):
    channels = ["swap/trade:%s-USD-SWAP" % coin_name.upper()]
    url = 'wss://real.okex.com:8443/ws/v3'

    loop = asyncio.get_event_loop()

    # 公共数据 不需要登录（行情，K线，交易数据，资金费率，限价范围，深度数据，标记价格等频道）
    loop.run_until_complete(subscribe_without_login(url, channels))

    # 个人数据 需要登录（用户账户，用户交易，用户持仓等频道）
    # loop.run_until_complete(subscribe(url, api_key, passphrase, secret_key, channels))

    loop.close()


# subscribe channels un_need login
async def subscribe_without_login(url, channels):
    while True:
        try:
            async with websockets.connect(url) as ws:
                sub_param = {"op": "subscribe", "args": channels}
                sub_str = json.dumps(sub_param)
                await ws.send(sub_str)

                while True:
                    try:
                        res_b = await asyncio.wait_for(ws.recv(), timeout=25)
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed) as e:
                        try:
                            await ws.send('ping')
                            res_b = await ws.recv()
                            timestamp = get_timestamp()
                            res = inflate(res_b).decode('utf-8')
                            print(timestamp + res)
                            continue
                        except Exception as e:
                            timestamp = get_timestamp()
                            print(timestamp + "正在重连……")
                            print(e)
                            break

                    timestamp = get_timestamp()
                    res = inflate(res_b).decode('utf-8')
                    print(timestamp + res)
                    process_message(res)


        except Exception as e:
            timestamp = get_timestamp()
            print(timestamp + "连接断开，正在重连……")
            print(e)
            continue


if __name__ == '__main__':
    if len(sys.argv) > 2:
        coin_name = sys.argv[1]
        # 默认币种handle_deque
        coin = Coin(coin_name, "usdt")
        instrument_id = coin.get_instrument_id()
        future_instrument_id = coin.get_future_instrument_id()
        file_transaction, file_deal = coin.gen_file_name()
        config_file = sys.argv[2]
        if config_file == 'config_mother':
            from config_mother import spotAPI, okFuture, futureAPI
        # elif config_file == 'config_son1':
        #     from config_son1 import spotAPI, okFuture, futureAPI
        # elif config_file == 'config_son3':
        #     from config_son3 import spotAPI, okFuture, futureAPI
        else:
            print('输入config_file有误，请输入config_mother or config_son1 or config_son3')
            sys.exit()
        run_websocket(coin_name)

    else:
        print('缺少参数 coin_name, config_file')
        print('for example: python monitor_spot etc config_mother')



# url = 'wss://real.okex.com:8443/ws/v3?brokerId=9999'

# 现货
# 用户币币账户频道
# channels = ["spot/account:USDT"]
# 用户杠杆账户频道
# channels = ["spot/margin_account:BTC-USDT"]
# 用户委托策略频道
# channels = ["spot/order_algo:BTC-USDT"]
# 用户交易频道
# channels = ["spot/order:BTC-USDT"]
# 公共-Ticker频道
# channels = ["spot/ticker:BTC-USDT"]
# 公共-5档深度频道
# channels = ["spot/depth5:BTC-USDT"]
# 公共-400档深度频道
# channels = ["spot/depth:BTC-USDT"]
# 公共-400档增量数据频道
# channels = ["spot/depth_l2_tbt:BTC-USDT"]

# 交割合约
# 用户持仓频道
# channels = ["futures/position:BTC-USD-200327"]
# 用户账户频道
# channels = ["futures/account:BTC"]
# 用户交易频道
# channels = ["futures/order:BTC-USD-200626"]
# 用户委托策略频道
# channels = ["futures/order_algo:BTC-USD-200327"]
# 公共-全量合约信息频道
# channels = ["futures/instruments"]
# 公共-Ticker频道
# channels = ["futures/ticker:BTC-USD-200626"]
# 公共-K线频道
# channels = ["futures/candle60s:BTC-USD-200626"]
# 公共-交易频道
# channels = ["futures/trade:BTC-USD-200117"]
# 公共-预估交割价频道
# channels = ["futures/estimated_price:BTC-USD-200228"]
# 公共-限价频道
# channels = ["futures/price_range:BTC-USD-200327"]
# 公共-5档深度频道
# channels = ["futures/depth5:BTC-USD-200327"]
# 公共-400档深度频道
# channels = ["futures/depth:BTC-USD-200327"]
# 公共-400档增量数据频道
# channels = ["futures/depth_l2_tbt:BTC-USD-200327"]
# 公共-标记价格频道
# channels = ["futures/mark_price:BTC-USD-200327"]

# 永续合约
# 用户持仓频道
# channels = ["swap/position:BTC-USD-SWAP"]
# 用户账户频道
# channels = ["swap/account:BTC-USD-SWAP"]
# 用户交易频道
# channels = ["swap/order:BTC-USD-SWAP"]
# 用户委托策略频道
# channels = ["swap/order_algo:BTC-USD-SWAP"]
# 公共-Ticker频道
# channels = ["swap/ticker:BTC-USD-SWAP"]
# 公共-K线频道
# channels = ["swap/candle60s:BTC-USD-SWAP"]
# 公共-交易频道
# channels = ["swap/trade:BTC-USD-SWAP"]
# 公共-资金费率频道
# channels = ["swap/funding_rate:BTC-USD-SWAP"]
# 公共-限价频道
# channels = ["swap/price_range:BTC-USD-SWAP"]
# 公共-5档深度频道
# channels = ["swap/depth5:BTC-USD-SWAP"]
# 公共-400档深度频道
# channels = ["swap/depth:BTC-USDT-SWAP"]
# 公共-400档增量数据频道
# channels = ["swap/depth_l2_tbt:BTC-USD-SWAP"]
# 公共-标记价格频道
# channels = ["swap/mark_price:BTC-USD-SWAP"]

# 期权合约
# 用户持仓频道
# channels = ["option/position:BTC-USD"]
# 用户账户频道
# channels = ["option/account:BTC-USD"]
# 用户交易频道
# channels = ["option/order:BTC-USD"]
# 公共-合约信息频道
# channels = ["option/instruments:BTC-USD"]
# 公共-期权详细定价频道
# channels = ["option/summary:BTC-USD"]
# 公共-K线频道
# channels = ["option/candle60s:BTC-USD-200327-11000-C"]
# 公共-最新成交频道
# channels = ["option/trade:BTC-USD-200327-11000-C"]
# 公共-Ticker频道
# channels = ["option/ticker:BTC-USD-200327-11000-C"]
# 公共-5档深度频道
# channels = ["option/depth5:BTC-USD-200327-11000-C"]
# 公共-400档深度频道
# channels = ["option/depth:BTC-USD-200327-11000-C"]
# 公共-400档增量数据频道
# channels = ["option/depth_l2_tbt:BTC-USD-200327-11000-C"]

# ws公共指数频道
# 指数行情
# channels = ["index/ticker:BTC-USD"]
# 指数K线
# channels = ["index/candle60s:BTC-USD"]

# WebSocket-获取系统升级状态
# channels = ["system/status"]

