# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from collections import deque
import websocket
from utils import cal_rate, timestamp2string
import codecs
from trade import buyin_less, buyin_more, json, ensure_buyin_less, \
    ensure_buyin_more,okFuture, cancel_uncompleted_order, gen_orders_data, send_email
from entity import Coin, Indicator, DealEntity, IndexEntity, IndexIndicator
import time

# 默认币种
coin = Coin("eth", "usdt")
time_type = "quarter"
latest_price = 210

file_transaction, file_deal = coin.gen_future_file_name()

btc_weight = 0.5
eth_weight = 0.3
ltc_weight = 0.2

btc_deque_1s = deque()
btc_deque_1min = deque()
btc_deque_5min = deque()

eth_deque_1s = deque()
eth_deque_1min = deque()
eth_deque_5min = deque()

ltc_deque_1s = deque()
ltc_deque_1min = deque()
ltc_deque_5min = deque()

btc_ind_1s = IndexIndicator("btc", 1)
btc_ind_1min = IndexIndicator("btc", 60)
btc_ind_5min = IndexIndicator("btc", 300)

eth_ind_1s = IndexIndicator("eth", 1)
eth_ind_1min = IndexIndicator("eth", 60)
eth_ind_5min = IndexIndicator("eth", 300)

ltc_ind_1s = IndexIndicator("ltc", 1)
ltc_ind_1min = IndexIndicator("ltc", 60)
ltc_ind_5min = IndexIndicator("ltc", 300)

more = 0
less = 0
buy_price = 0
incr_5m_rate = 0.5
incr_1m_rate = 0.3
write_lines = []
processing = False


def handle_deque(deq, entity, ind):
    while len(deq) > 0:
        left = deq.popleft()
        if left.timestamp + ind.interval * 1000 > entity.timestamp:
            deq.appendleft(left)
            break
        ind.minus_index(left)
    deq.append(entity)
    ind.add_index(entity)


def sell_more_suc():
    global more
    ts = time.time()
    now_time = timestamp2string(ts)
    info = u'发出卖出信号！！！卖出价格：' + str(latest_price) + u', 收益: ' + str(latest_price - buy_price) \
           + ', ' + now_time
    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
        f.writelines(info + '\n')
    more = 0


def sell_more_batch(coin_name, time_type, latest_price, lever_rate = 20):
    global processing
    processing = True
    jRet = json.loads(okFuture.future_position_4fix(coin_name+"_usd", time_type, "1"))
    print(jRet)
    flag = True
    ret = u'没有做多订单'
    while len(jRet["holding"]) > 0:
        cancel_uncompleted_order(coin_name, time_type)
        if flag:
            flag = False
            amount = jRet["holding"][0]["buy_available"]
            order_data = gen_orders_data(latest_price, amount, 3, 5)
            ret = okFuture.future_batchTrade(coin_name + "_usd", time_type, order_data, lever_rate)
        else:
            buy_available = jRet["holding"][0]["buy_available"]
            ret = okFuture.future_trade(coin_name + "_usd", time_type, '', buy_available, 3, 1, lever_rate)
        if 'true' in ret:
            time.sleep(2)
            jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))

    sell_more_suc()
    email_msg = "做多%s批量卖出成交, 时间: %s, 成交结果: %s" \
                % (coin_name, timestamp2string(time.time()), ret)
    thread.start_new_thread(send_email, (email_msg,))
    processing = False
    return True


def sell_less_suc():
    global less
    ts = time.time()
    now_time = timestamp2string(ts)
    info = u'发出卖出信号！！！卖出价格：' + str(latest_price) + u', 收益: ' + str(buy_price - latest_price) \
           + ', ' + now_time
    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
        f.writelines(info + '\n')
    less = 0


def sell_less_batch(coin_name, time_type, latest_price, lever_rate = 20):
    global processing
    processing = True
    jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))
    flag = True
    ret = u'没有做空订单'
    while len(jRet["holding"]) > 0:
        cancel_uncompleted_order(coin_name, time_type)
        if flag:
            amount = jRet["holding"][0]["sell_available"]
            order_data = gen_orders_data(latest_price, amount, 4, 5)
            ret = okFuture.future_batchTrade(coin_name + "_usd", time_type, order_data, lever_rate)
            flag = False
        else:
            sell_available = jRet["holding"][0]["sell_available"]
            ret = okFuture.future_trade(coin_name + "_usd", time_type, '', sell_available, 4, 1, lever_rate)
        if 'true' in ret:
            time.sleep(2)
            jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))

    sell_less_suc()
    email_msg = "做空%s批量卖出成交, 时间: %s, 成交结果: %s" \
                % (coin_name, timestamp2string(time.time()), ret)
    thread.start_new_thread(send_email, (email_msg,))
    processing = False
    return True


def connect():
    ws = websocket.WebSocket()
    ws_address = "wss://real.okex.com"
    ws_port = 10441
    ws.connect(ws_address, http_proxy_host="websocket", http_proxy_port=ws_port)


def on_message(ws, message):
    if 'pong' in message or 'addChannel' in message:
        return
    global more, less, buy_price, write_lines
    jmessage = json.loads(message)
    coin_name = jmessage[0]['channel'].split('_')[3]
    data = jmessage[0]['data']
    index = float(data['futureIndex'])
    timestamp = int(data['timestamp'])
    now_time = timestamp2string(timestamp)
    index_entity = IndexEntity(coin_name, index, timestamp)
    coin_info = "coin: %s, index: %.2f, time: %s" % (coin_name, index, now_time)

    if coin_name == 'btc':
        handle_deque(btc_deque_1s, index_entity, btc_ind_1s)
        handle_deque(btc_deque_1min, index_entity, btc_ind_1min)
        handle_deque(btc_deque_5min, index_entity, btc_ind_5min)
    elif coin_name == 'eth':
        handle_deque(eth_deque_1s, index_entity, eth_ind_1s)
        handle_deque(eth_deque_1min, index_entity, eth_ind_1min)
        handle_deque(eth_deque_5min, index_entity, eth_ind_5min)
    elif coin_name == 'ltc':
        handle_deque(ltc_deque_1s, index_entity, ltc_ind_1s)
        handle_deque(ltc_deque_1min, index_entity, ltc_ind_1min)
        handle_deque(ltc_deque_5min, index_entity, ltc_ind_5min)

    btc_avg_1s_price = btc_ind_1s.cal_avg_price()
    btc_avg_min_price = btc_ind_1min.cal_avg_price()
    btc_avg_5m_price = btc_ind_5min.cal_avg_price()

    eth_avg_1s_price = eth_ind_1s.cal_avg_price()
    eth_avg_min_price = eth_ind_1min.cal_avg_price()
    eth_avg_5m_price = eth_ind_5min.cal_avg_price()

    ltc_avg_1s_price = ltc_ind_1s.cal_avg_price()
    ltc_avg_min_price = ltc_ind_1min.cal_avg_price()
    ltc_avg_5m_price = ltc_ind_5min.cal_avg_price()

    btc_1m_change = cal_rate(btc_avg_1s_price, btc_avg_min_price)
    btc_5m_change = cal_rate(btc_avg_1s_price, btc_avg_5m_price)

    eth_1m_change = cal_rate(eth_avg_1s_price, eth_avg_min_price)
    eth_5m_change = cal_rate(eth_avg_1s_price, eth_avg_5m_price)

    ltc_1m_change = cal_rate(ltc_avg_1s_price, ltc_avg_min_price)
    ltc_5m_change = cal_rate(ltc_avg_1s_price, ltc_avg_5m_price)

    weighted_1min_rate = btc_1m_change * btc_weight + eth_1m_change * eth_weight + ltc_1m_change * ltc_weight
    weighted_5min_rate = btc_5m_change * btc_weight + eth_5m_change * eth_weight + ltc_5m_change * ltc_weight

    if more == 1 and not processing:
        if weighted_5min_rate <= 0:
            thread.start_new_thread(sell_more_batch, (coin.name, time_type, latest_price,))
    elif less == 1 and not processing:
        if weighted_5min_rate >= 0:
            thread.start_new_thread(sell_less_batch, (coin.name, time_type, latest_price,))

    elif weighted_1min_rate >= incr_1m_rate and weighted_5min_rate >= incr_5m_rate \
            and btc_5m_change >= incr_1m_rate and eth_5m_change >= incr_1m_rate and ltc_5m_change >= incr_1m_rate:
        if buyin_more(coin.name, time_type, latest_price):
            more = 1
            thread.start_new_thread(ensure_buyin_more, (coin.name, time_type, latest_price,))
            buy_price = latest_price
            info = u'发出做多信号！！！买入价格：' + str(buy_price) + u', ' + now_time
            with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                f.writelines(info + '\n')
    elif weighted_1min_rate <= -incr_1m_rate and weighted_5min_rate <= -incr_5m_rate \
            and btc_5m_change < -incr_1m_rate and eth_5m_change < -incr_1m_rate and ltc_5m_change < -incr_1m_rate:
        if buyin_less(coin.name, time_type, latest_price):
            less = 1
            thread.start_new_thread(ensure_buyin_less, (coin.name, time_type, latest_price,))
            buy_price = latest_price
            info = u'发出做空信号！！！买入价格：' + str(buy_price) + u', ' + now_time
            with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                f.writelines(info + '\n')

    btc_rate_info = u'btc      1min_rate: %.2f%%, 5min_rate: %.2f%%' % (btc_1m_change, btc_5m_change)

    eth_rate_info = u'eth      1min_rate: %.2f%%, 5min_rate: %.2f%%' % (eth_1m_change, eth_5m_change)

    ltc_rate_info = u'ltc      1min_rate: %.2f%%, 5min_rate: %.2f%%' % (ltc_1m_change, ltc_5m_change)

    weighted_rate_info = u'weighted 1min_rate: %.3f%%, 5min_rate: %.3f%%' % (weighted_1min_rate, weighted_5min_rate)

    print(coin_info)
    print(btc_rate_info)
    print(eth_rate_info)
    print(ltc_rate_info)
    print(weighted_rate_info)
    write_info = coin_info + '\n' + btc_rate_info + '\n' + eth_rate_info + '\n' + ltc_rate_info + '\n' \
                 + weighted_rate_info + '\r\n'
    write_lines.append(write_info)
    if len(write_lines) >= 10:
        with codecs.open(file_deal, 'a+', 'UTF-8') as f:
            f.writelines(write_lines)
            write_lines = []


def on_error(ws, error):
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    def run(*args):
        ws.send("[{'event':'addChannel','channel':'ok_sub_futureusd_btc_index'},"
                "{'event':'addChannel','channel':'ok_sub_futureusd_eth_index'},"
                "{'event':'addChannel','channel':'ok_sub_futureusd_ltc_index'}]")
        print("thread starting...")

    thread.start_new_thread(run, ())


if __name__ == '__main__':
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp("wss://real.okex.com:10441/websocket",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    while True:
        ws.run_forever(ping_interval=20, ping_timeout=10)
        print("write left lines into file...")
        with codecs.open(file_deal, 'a+', 'UTF-8') as f:
            f.writelines(write_lines)
            write_lines = []