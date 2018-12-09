# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from collections import deque
from utils import timestamp2string, cal_rate
from trade import buyin_less, buyin_more, json, ensure_buyin_less, \
    ensure_buyin_more, okFuture, cancel_uncompleted_order, gen_orders_data, send_email
from entity import Coin, Indicator, DealEntity, handle_deque
import time
import websocket
import codecs


# 默认币种
coin = Coin("etc", "usdt")
time_type = "quarter"
file_transaction, file_deal = coin.gen_file_name()

deque_min = deque()
deque_10s = deque()
deque_3s = deque()
deque_5m = deque()
latest_price = 0
ind_1min = Indicator(60)
ind_10s = Indicator(10)
ind_3s = Indicator(3)
ind_5m = Indicator(300)
more = 0
less = 0
more2less = 0
less2more = 0
last_avg_price = 0
buy_price = 0
last_last_price = 0
incr_5m_rate = 0.6
incr_1m_rate = 0.3
write_lines = []
processing = False


def connect():
    ws = websocket.WebSocket()
    ws_address = "wss://real.okex.com"
    ws_port = 10441
    ws.connect(ws_address, http_proxy_host="websocket", http_proxy_port=ws_port)


def sell_more_suc():
    global more, less2more
    more = 0
    less2more = 0
    ts = time.time()
    now_time = timestamp2string(ts)
    info = u'发出卖出信号！！！卖出价格：' + str(latest_price) + u', 收益: ' + str(latest_price - buy_price) \
           + ', ' + now_time
    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
        f.writelines(info + '\n')


def sell_more_batch(coin_name, time_type, latest_price, lever_rate = 20):
    global processing, more2less
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
            time.sleep(5)
            jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))

    sell_more_suc()
    if more2less == 1:
        if buyin_less(coin_name, time_type, latest_price):
            info = u'发出反手做空信号！！！买入价格：' + str(latest_price)
            with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                f.writelines(info + '\n')
        else:
            more2less = 0
    email_msg = "做多%s批量卖出成交, 时间: %s, 成交结果: %s" \
                % (coin_name, timestamp2string(time.time()), ret)
    thread.start_new_thread(send_email, (email_msg,))
    processing = False
    return True


def sell_less_suc():
    global less, more2less
    less = 0
    more2less = 0
    ts = time.time()
    now_time = timestamp2string(ts)
    info = u'发出卖出信号！！！卖出价格：' + str(latest_price) + u', 收益: ' + str(buy_price - latest_price) \
           + ', ' + now_time
    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
        f.writelines(info + '\n')


def sell_less_batch(coin_name, time_type, latest_price, lever_rate = 20):
    global processing, less2more
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
            time.sleep(5)
            jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))

    sell_less_suc()
    if less2more == 1:
        if buyin_more(coin_name, time_type, latest_price):
            info = u'发出反手做多信号！！！买入价格：' + str(latest_price)
            with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                f.writelines(info + '\n')
        else:
            less2more = 0
    email_msg = "做空%s批量卖出成交, 时间: %s, 成交结果: %s" \
                % (coin_name, timestamp2string(time.time()), ret)
    thread.start_new_thread(send_email, (email_msg,))
    processing = False
    return True


def on_message(ws, message):
    if 'pong' in message or 'addChannel' in message:
        return
    print(message)
    global latest_price, last_avg_price, buy_price, last_last_price, more, less, deque_3s, deque_10s, deque_min, \
        deque_5m, ind_3s, ind_10s, ind_1min, ind_5m, write_lines, less2more, more2less
    jmessage = json.loads(message)
    ts = time.time()
    now_time = timestamp2string(ts)
    for each_message in jmessage:
        for jdata in each_message['data']:
            latest_price = float(jdata[1])
            deal_entity = DealEntity(jdata[0], float(jdata[1]), round(float(jdata[2]), 3), ts, jdata[4])

            handle_deque(deque_3s, deal_entity, ts, ind_3s)
            handle_deque(deque_10s, deal_entity, ts, ind_10s)
            handle_deque(deque_min, deal_entity, ts, ind_1min)
            handle_deque(deque_5m, deal_entity, ts, ind_5m)

            avg_3s_price = ind_3s.cal_avg_price()
            avg_10s_price = ind_10s.cal_avg_price()
            avg_min_price = ind_1min.cal_avg_price()
            avg_5m_price = ind_5m.cal_avg_price()
            price_10s_change = cal_rate(avg_3s_price, avg_10s_price)
            price_1m_change = cal_rate(avg_3s_price, avg_min_price)
            price_5m_change = cal_rate(avg_3s_price, avg_5m_price)

            if more == 1 and not processing:
                if avg_3s_price <= 1.001 * avg_5m_price or price_1m_change <= -incr_1m_rate:
                    # 反手做空
                    if price_1m_change <= -incr_1m_rate:
                        more2less = 1
                    sell_more_batch(coin.name, time_type, latest_price)

            elif less == 1 and not processing:
                if avg_3s_price >= 0.999 * avg_5m_price or price_1m_change >= incr_1m_rate:
                    # 反手做多
                    if price_1m_change >= incr_1m_rate:
                        less2more = 1
                    sell_less_batch(coin.name, time_type, latest_price)

            elif more2less == 1 and not processing:
                if price_1m_change >= 0:
                    sell_less_batch(coin.name, time_type, latest_price)

            elif less2more == 1 and not processing:
                if price_1m_change <= 0:
                    sell_more_batch(coin.name, time_type, latest_price)

            elif check_vol():
                if latest_price > avg_3s_price > avg_10s_price > last_avg_price > last_last_price \
                        and incr_1m_rate <= price_1m_change < price_5m_change and incr_5m_rate <= price_5m_change < 1.5 \
                        and 0.05 <= price_10s_change <= 0.2\
                        and ind_1min.bid_vol > float(2 * ind_1min.ask_vol) \
                        and ind_3s.bid_vol > float(5 * ind_3s.ask_vol):
                    if buyin_more(coin.name, time_type, latest_price):
                        more = 1
                        thread.start_new_thread(ensure_buyin_more, (coin.name, time_type, latest_price,))
                        buy_price = latest_price
                        info = u'发出做多信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                            f.writelines(info + '\n')

                elif latest_price < avg_3s_price < avg_10s_price < last_avg_price < last_last_price \
                        and -1.5 < price_5m_change <= -incr_5m_rate and price_5m_change < price_1m_change <= -incr_1m_rate \
                        and -0.2 <= price_10s_change <= -0.05 \
                        and ind_1min.ask_vol > float(4 * ind_1min.bid_vol) and ind_3s.ask_vol > float(5 * ind_3s.bid_vol):
                    if buyin_less(coin.name, time_type, latest_price):
                        less = 1
                        thread.start_new_thread(ensure_buyin_less, (coin.name, time_type, latest_price,))
                        buy_price = latest_price
                        info = u'发出做空信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                            f.writelines(info + '\n')

            if last_avg_price != avg_10s_price:
                last_last_price = last_avg_price
                last_avg_price = avg_10s_price

            price_info = deal_entity.type + u' now_price: %.4f, 3s_price: %.4f, 10s_price: %.4f, 1m_price: %.4f, ' \
                                            u'5min_price: %.4f' \
                         % (latest_price, avg_3s_price, avg_10s_price, avg_min_price, avg_5m_price)
            vol_info = u'cur_vol: %.3f, 3s vol: %.3f, 10s vol: %.3f, 1min vol: %.3f, ask_vol: %.3f, bid_vol: %.3f, 3s_ask_vol: %.3f, 3s_bid_vol: %.3f' \
                       % (deal_entity.amount, ind_3s.vol, ind_10s.vol, ind_1min.vol, ind_1min.ask_vol, ind_1min.bid_vol, ind_3s.ask_vol, ind_3s.bid_vol)
            rate_info = u'10s_rate: %.2f%%, 1min_rate: %.2f%%, 5min_rate: %.2f%%' \
                        % (price_10s_change, price_1m_change, price_5m_change)
            write_info = price_info + u', ' + vol_info + u', ' + rate_info + u', ' + now_time + '\r\n'
            write_lines.append(write_info)
            if len(write_lines) >= 100:
                with codecs.open(file_deal, 'a+', 'UTF-8') as f:
                    f.writelines(write_lines)
                    write_lines = []

            print(price_info + '\r\n' + vol_info + '\r\n' + rate_info + u', ' + now_time)


def check_vol():
    if ind_3s.vol > 1000:
        if ind_1min.vol > 16000:
            if ind_1min.bid_vol > 2 * ind_1min.ask_vol or ind_1min.ask_vol > 2 * ind_1min.bid_vol:
                return True
        elif ind_1min.vol > 12000:
            if ind_1min.bid_vol > 3 * ind_1min.ask_vol or ind_1min.ask_vol > 3 * ind_1min.bid_vol:
                return True
        elif ind_1min.vol > 8000:
            if ind_1min.bid_vol > 4 * ind_1min.ask_vol or ind_1min.ask_vol > 4 * ind_1min.bid_vol:
                return True
    return False


def on_error(ws, error):
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    def run(*args):
        ws.send("{'event':'addChannel','channel':'ok_sub_spot_%s_deals'}" % coin.gen_full_name())
        print("thread starting...")

    thread.start_new_thread(run, ())


if __name__ == '__main__':
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