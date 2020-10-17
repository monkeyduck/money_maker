import asyncio
import websockets
import json
import requests
import dateutil.parser as dp
import hmac
import base64
import zlib
import datetime
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


def get_timestamp():
    now = datetime.datetime.now()
    t = now.isoformat("T", "milliseconds")
    return t + "Z"


def get_server_time():
    url = "https://www.okex.com/api/general/v3/time"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()['iso']
    else:
        return ""


def server_timestamp():
    server_time = get_server_time()
    parsed_t = dp.parse(server_time)
    timestamp = parsed_t.timestamp()
    return timestamp


def login_params(timestamp, api_key, passphrase, secret_key):
    message = timestamp + 'GET' + '/users/self/verify'

    mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    d = mac.digest()
    sign = base64.b64encode(d)

    login_param = {"op": "login", "args": [api_key, passphrase, timestamp, sign.decode("utf-8")]}
    login_str = json.dumps(login_param)
    return login_str


def inflate(data):
    decompress = zlib.decompressobj(
            -zlib.MAX_WBITS  # see above
    )
    inflated = decompress.decompress(data)
    inflated += decompress.flush()
    return inflated


def partial(res, timestamp):
    data_obj = res['data'][0]
    bids = data_obj['bids']
    asks = data_obj['asks']
    instrument_id = data_obj['instrument_id']
    # print(timestamp + '全量数据bids为：' + str(bids))
    # print('档数为：' + str(len(bids)))
    # print(timestamp + '全量数据asks为：' + str(asks))
    # print('档数为：' + str(len(asks)))
    return bids, asks, instrument_id


def update_bids(res, bids_p, timestamp):
    # 获取增量bids数据
    bids_u = res['data'][0]['bids']
    print(timestamp + '增量数据bids为：' + str(bids_u))
    # print('档数为：' + str(len(bids_u)))
    # bids合并
    for i in bids_u:
        bid_price = i[0]
        for j in bids_p:
            if bid_price == j[0]:
                if i[1] == '0':
                    bids_p.remove(j)
                    break
                else:
                    del j[1]
                    j.insert(1, i[1])
                    break
        else:
            if i[1] != "0":
                bids_p.append(i)
    else:
        bids_p.sort(key=lambda price: sort_num(price[0]), reverse=True)
        # print(timestamp + '合并后的bids为：' + str(bids_p) + '，档数为：' + str(len(bids_p)))
    return bids_p


def update_asks(res, asks_p, timestamp):
    # 获取增量asks数据
    asks_u = res['data'][0]['asks']
    print(timestamp + '增量数据asks为：' + str(asks_u))
    # print('档数为：' + str(len(asks_u)))
    # asks合并
    for i in asks_u:
        ask_price = i[0]
        for j in asks_p:
            if ask_price == j[0]:
                if i[1] == '0':
                    asks_p.remove(j)
                    break
                else:
                    del j[1]
                    j.insert(1, i[1])
                    break
        else:
            if i[1] != "0":
                asks_p.append(i)
    else:
        asks_p.sort(key=lambda price: sort_num(price[0]))
        # print(timestamp + '合并后的asks为：' + str(asks_p) + '，档数为：' + str(len(asks_p)))
    return asks_p


def sort_num(n):
    if n.isdigit():
        return int(n)
    else:
        return float(n)


def check(bids, asks):
    # 获取bid档str
    bids_l = []
    bid_l = []
    count_bid = 1
    while count_bid <= 25:
        if count_bid > len(bids):
            break
        bids_l.append(bids[count_bid-1])
        count_bid += 1
    for j in bids_l:
        str_bid = ':'.join(j[0 : 2])
        bid_l.append(str_bid)
    # 获取ask档str
    asks_l = []
    ask_l = []
    count_ask = 1
    while count_ask <= 25:
        if count_ask > len(asks):
            break
        asks_l.append(asks[count_ask-1])
        count_ask += 1
    for k in asks_l:
        str_ask = ':'.join(k[0 : 2])
        ask_l.append(str_ask)
    # 拼接str
    num = ''
    if len(bid_l) == len(ask_l):
        for m in range(len(bid_l)):
            num += bid_l[m] + ':' + ask_l[m] + ':'
    elif len(bid_l) > len(ask_l):
        # bid档比ask档多
        for n in range(len(ask_l)):
            num += bid_l[n] + ':' + ask_l[n] + ':'
        for l in range(len(ask_l), len(bid_l)):
            num += bid_l[l] + ':'
    elif len(bid_l) < len(ask_l):
        # ask档比bid档多
        for n in range(len(bid_l)):
            num += bid_l[n] + ':' + ask_l[n] + ':'
        for l in range(len(bid_l), len(ask_l)):
            num += ask_l[l] + ':'

    new_num = num[:-1]
    int_checksum = zlib.crc32(new_num.encode())
    fina = change(int_checksum)
    return fina


def change(num_old):
    num = pow(2, 31) - 1
    if num_old > num:
        out = num_old - num * 2 - 2
    else:
        out = num_old
    return out


# subscribe channels un_need login
async def subscribe_without_login(url, channels):
    l = []
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

                    res = eval(res)
                    if 'event' in res:
                        continue
                    for i in res:
                        if 'depth' in res[i] and 'depth5' not in res[i]:
                            # 订阅频道是深度频道
                            if res['action'] == 'partial':
                                for m in l:
                                    if res['data'][0]['instrument_id'] == m['instrument_id']:
                                        l.remove(m)
                                # 获取首次全量深度数据
                                bids_p, asks_p, instrument_id = partial(res, timestamp)
                                d = {}
                                d['instrument_id'] = instrument_id
                                d['bids_p'] = bids_p
                                d['asks_p'] = asks_p
                                l.append(d)

                                # 校验checksum
                                checksum = res['data'][0]['checksum']
                                # print(timestamp + '推送数据的checksum为：' + str(checksum))
                                check_num = check(bids_p, asks_p)
                                # print(timestamp + '校验后的checksum为：' + str(check_num))
                                if check_num == checksum:
                                    print("校验结果为：True")
                                else:
                                    print("校验结果为：False，正在重新订阅……")

                                    # 取消订阅
                                    await unsubscribe_without_login(url, channels, timestamp)
                                    # 发送订阅
                                    async with websockets.connect(url) as ws:
                                        sub_param = {"op": "subscribe", "args": channels}
                                        sub_str = json.dumps(sub_param)
                                        await ws.send(sub_str)
                                        timestamp = get_timestamp()
                                        print(timestamp + f"send: {sub_str}")

                            elif res['action'] == 'update':
                                for j in l:
                                    if res['data'][0]['instrument_id'] == j['instrument_id']:
                                        # 获取全量数据
                                        bids_p = j['bids_p']
                                        asks_p = j['asks_p']
                                        # 获取合并后数据
                                        bids_p = update_bids(res, bids_p, timestamp)
                                        asks_p = update_asks(res, asks_p, timestamp)

                                        # 校验checksum
                                        checksum = res['data'][0]['checksum']
                                        # print(timestamp + '推送数据的checksum为：' + str(checksum))
                                        check_num = check(bids_p, asks_p)
                                        # print(timestamp + '校验后的checksum为：' + str(check_num))
                                        if check_num == checksum:
                                            print("校验结果为：True")
                                        else:
                                            print("校验结果为：False，正在重新订阅……")

                                            # 取消订阅
                                            await unsubscribe_without_login(url, channels, timestamp)
                                            # 发送订阅
                                            async with websockets.connect(url) as ws:
                                                sub_param = {"op": "subscribe", "args": channels}
                                                sub_str = json.dumps(sub_param)
                                                await ws.send(sub_str)
                                                timestamp = get_timestamp()
                                                print(timestamp + f"send: {sub_str}")
        except Exception as e:
            timestamp = get_timestamp()
            print(timestamp + "连接断开，正在重连……")
            print(e)
            continue


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


# subscribe channels need login
async def subscribe(url, api_key, passphrase, secret_key, channels):
    while True:
        try:
            async with websockets.connect(url) as ws:
                # login
                timestamp = str(server_timestamp())
                login_str = login_params(timestamp, api_key, passphrase, secret_key)
                await ws.send(login_str)
                # time = get_timestamp()
                # print(time + f"send: {login_str}")
                res_b = await ws.recv()
                res = inflate(res_b).decode('utf-8')
                time = get_timestamp()
                print(time + res)

                # subscribe
                sub_param = {"op": "subscribe", "args": channels}
                sub_str = json.dumps(sub_param)
                await ws.send(sub_str)
                time = get_timestamp()
                print(time + f"send: {sub_str}")

                while True:
                    try:
                        res_b = await asyncio.wait_for(ws.recv(), timeout=25)
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed) as e:
                        try:
                            await ws.send('ping')
                            res_b = await ws.recv()
                            time = get_timestamp()
                            res = inflate(res_b).decode('utf-8')
                            print(time + res)
                            continue
                        except Exception as e:
                            time = get_timestamp()
                            print(time + "正在重连……")
                            print(e)
                            break

                    time = get_timestamp()
                    res = inflate(res_b).decode('utf-8')
                    print(time + res)

        except Exception as e:
            time = get_timestamp()
            print(time + "连接断开，正在重连……")
            print(e)
            continue


# unsubscribe channels
async def unsubscribe(url, api_key, passphrase, secret_key, channels):
    async with websockets.connect(url) as ws:
        # login
        timestamp = str(server_timestamp())
        login_str = login_params(str(timestamp), api_key, passphrase, secret_key)
        await ws.send(login_str)
        # time = get_timestamp()
        # print(time + f"send: {login_str}")

        res_1 = await ws.recv()
        res = inflate(res_1).decode('utf-8')
        time = get_timestamp()
        print(time + res)

        # unsubscribe
        sub_param = {"op": "unsubscribe", "args": channels}
        sub_str = json.dumps(sub_param)
        await ws.send(sub_str)
        time = get_timestamp()
        print(time + f"send: {sub_str}")

        res_1 = await ws.recv()
        res = inflate(res_1).decode('utf-8')
        time = get_timestamp()
        print(time + res)


# unsubscribe channels
async def unsubscribe_without_login(url, channels, timestamp):
    async with websockets.connect(url) as ws:
        # unsubscribe
        sub_param = {"op": "unsubscribe", "args": channels}
        sub_str = json.dumps(sub_param)
        await ws.send(sub_str)
        print(timestamp + f"send: {sub_str}")

        res_1 = await ws.recv()
        res = inflate(res_1).decode('utf-8')
        print(timestamp + f"recv: {res}")

# channels = ["spot/candle60s:BTC-USDT"]
# 公共-交易频道
# channels = ["spot/trade:BTC-USDT"]
# 公共-K线频道

api_key = ""
secret_key = ""
passphrase = ""

url = 'wss://real.okex.com:8443/ws/v3'
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
            from config_mother import spotAPI
        else:
            print('输入config_file有误，请输入config_mother or config_son1 or config_son3')
            sys.exit()
        channels = ["spot/order:%s-USDT" % coin_name.upper()]
        loop = asyncio.get_event_loop()

        # 公共数据 不需要登录（行情，K线，交易数据，资金费率，限价范围，深度数据，标记价格等频道）
        loop.run_until_complete(subscribe_without_login(url, channels))

        # 个人数据 需要登录（用户账户，用户交易，用户持仓等频道）
        # loop.run_until_complete(subscribe(url, api_key, passphrase, secret_key, channels))

        loop.close()

    else:
        print('缺少参数 coin_name, config_file')
        print('for example: python monitor_spot etc config_mother')

