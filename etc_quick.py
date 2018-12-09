# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate
from trade import buyin_less, buyin_more, ensure_buyin_less, \
    ensure_buyin_more, cancel_uncompleted_order, gen_orders_data, send_email, buyin_more_price, \
    buyin_less_price, pend_order
from strategy import get_macd
from entity import Coin, Indicator, DealEntity
from config_quick import vol_1m_line, vol_3s_line, vol_1m_bal, vol_3s_bal, incr_5m_rate, incr_1m_rate, incr_10s_rate
import time
import json

import traceback
from collections import deque
import websocket
import codecs

# 默认币种handle_deque
coin = Coin("etc", "usdt")
time_type = "quarter"
file_transaction, file_deal = coin.gen_future_file_name()

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
last_avg_price = 0
buy_price = 0

last_5min_macd = 0
last_5min_macd_ts = 0

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


def on_message(ws, message):
    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    if 'pong' in message or 'addChannel' in message:
        return
    global latest_price, last_avg_price, buy_price, more, less, deque_3s, deque_10s, deque_min, \
        deque_5m, ind_3s, ind_10s, ind_1min, ind_5m, write_lines, last_5min_macd, last_5min_macd_ts
    jmessage = json.loads(message)

    ts = time.time()
    now_time = timestamp2string(ts)
    if int(ts) - int(last_5min_macd_ts) >= 300:
        last_5min_macd_ts = int(ts)
        print(last_5min_macd_ts)
        if more == 0 and less == 0:
            ret = json.loads(okFuture.future_position_4fix("etc_usd", "quarter", "1"))
            print(ret)
            if len(ret["holding"]) > 0:
                buy_available = ret["holding"][0]["buy_available"]
                sell_available = ret["holding"][0]["sell_available"]
                if buy_available > 0:
                    thread.start_new_thread(ensure_sell_more, (coin.name, time_type,))
                if sell_available > 0:
                    thread.start_new_thread(ensure_sell_less, (coin.name, time_type,))
            else:
                print("确认未持仓")

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

            if more == 1:
                if price_10s_change < 0:
                    cancel_uncompleted_order(coin.name, time_type)
                    if sell_more_batch(coin.name, time_type, latest_price):
                        more = 0
                        thread.start_new_thread(ensure_sell_more, (coin.name, time_type,))

            elif less == 1:
                if price_10s_change > 0:
                    cancel_uncompleted_order(coin.name, time_type)
                    if sell_less_batch(coin.name, time_type, latest_price):
                        less = 0
                        thread.start_new_thread(ensure_sell_less, (coin.name, time_type,))

            elif check_vol():
                if price_10s_change > incr_10s_rate:
                    if ind_3s.bid_vol >= vol_3s_bal * ind_3s.ask_vol and ind_1min.bid_vol >= vol_1m_bal * ind_1min.ask_vol:
                        latest_order_id = buyin_more_price(coin.name, time_type, latest_price)
                        if latest_order_id:
                            more = 1
                            thread.start_new_thread(pend_order, (coin.name, time_type, latest_order_id, 'more',))
                            buy_price = latest_price
                            info = u'发出做多信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                            with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                                f.writelines(info + '\n')

                elif price_10s_change < -incr_10s_rate:
                    if ind_3s.ask_vol >= vol_3s_bal * ind_3s.bid_vol and ind_1min.ask_vol >= vol_1m_bal * ind_1min.bid_vol:
                        latest_order_id = buyin_less_price(coin.name, time_type, latest_price)
                        if latest_order_id:
                            less = 1
                            thread.start_new_thread(pend_order, (coin.name, time_type, latest_order_id, 'less',))
                            buy_price = latest_price
                            info = u'发出做空信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                            with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                                f.writelines(info + '\n')

            price_info = deal_entity.type + u' now_price: %.4f, 3s_price: %.4f, 10s_price: %.4f, 1m_price: %.4f, ' \
                                            u'5min_price: %.4f' \
                         % (latest_price, avg_3s_price, avg_10s_price, avg_min_price, avg_5m_price)
            vol_info = u'cur_vol: %.3f, 3s vol: %.3f, 10s vol: %.3f, 1min vol: %.3f, ask_vol: %.3f, bid_vol: %.3f, 3s_ask_vol: %.3f, 3s_bid_vol: %.3f' \
                       % (deal_entity.amount, ind_3s.vol, ind_10s.vol, ind_1min.vol, ind_1min.ask_vol, ind_1min.bid_vol,
                          ind_3s.ask_vol, ind_3s.bid_vol)
            rate_info = u'10s_rate: %.2f%%, 1min_rate: %.2f%%, 5min_rate: %.2f%%, 5min_macd: %.6f' \
                        % (price_10s_change, price_1m_change, price_5m_change, last_5min_macd)

            print(price_info + '\r\n' + vol_info + '\r\n' + rate_info + u', ' + now_time)


def sell_more_batch(coin_name, time_type, latest_price, lever_rate=20):
    jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))
    print(jRet)
    ret = u'没有做多订单'
    while len(jRet["holding"]) > 0:
        amount = jRet["holding"][0]["buy_available"]
        order_data = gen_orders_data(latest_price, amount, 3, 5)
        ret = okFuture.future_batchTrade(coin_name + "_usd", time_type, order_data, lever_rate)
        if 'true' in ret:
            break
        else:
            buy_available = jRet["holding"][0]["buy_available"]
            ret = okFuture.future_trade(coin_name + "_usd", time_type, '', buy_available, 3, 1, lever_rate)
            if 'true' in ret:
                break
            else:
                return False

    return True


def ensure_sell_more(coin_name, time_type, lever_rate=20):
    sleep_time = 3
    while sleep_time > 0:
        time.sleep(sleep_time)
        jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))
        if len(jRet["holding"]) > 0:
            cancel_uncompleted_order(coin_name, time_type)
            time.sleep(1)
            jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))
            buy_available = jRet["holding"][0]["buy_available"]
            okFuture.future_trade(coin_name + "_usd", time_type, '', buy_available, 3, 1, lever_rate)

        else:
            break
    ts = time.time()
    now_time = timestamp2string(ts)
    info = u'做多卖出成功！！！卖出价格：' + str(latest_price) + u', 收益: ' + str(latest_price - buy_price) \
           + ', ' + now_time
    thread.start_new_thread(send_email, (info,))
    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
        f.writelines(info + '\n')


def ensure_sell_less(coin_name, time_type, lever_rate=20):
    sleep_time = 30
    while sleep_time > 0:
        time.sleep(sleep_time)
        jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))
        if len(jRet["holding"]) > 0:
            cancel_uncompleted_order(coin_name, time_type)
            time.sleep(1)
            jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))
            sell_available = jRet["holding"][0]["sell_available"]
            okFuture.future_trade(coin_name + "_usd", time_type, '', sell_available, 4, 1, lever_rate)

        else:
            break
    ts = time.time()
    now_time = timestamp2string(ts)
    info = u'做空卖出成功！！！卖出价格：' + str(latest_price) + u', 收益: ' + str(buy_price - latest_price) \
           + ', ' + now_time
    thread.start_new_thread(send_email, (info,))
    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
        f.writelines(info + '\n')


def sell_less_batch(coin_name, time_type, latest_price, lever_rate=20):
    jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))
    ret = u'没有做空订单'
    while len(jRet["holding"]) > 0:
        amount = jRet["holding"][0]["sell_available"]
        order_data = gen_orders_data(latest_price, amount, 4, 5)
        ret = okFuture.future_batchTrade(coin_name + "_usd", time_type, order_data, lever_rate)
        if 'true' in ret:
            break
        else:
            sell_available = jRet["holding"][0]["sell_available"]
            ret = okFuture.future_trade(coin_name + "_usd", time_type, '', sell_available, 4, 1, lever_rate)
            if 'true' in ret:
                break
            else:
                return False

    return True


def check_vol():
    if ind_3s.vol > vol_3s_line and ind_1min.vol > vol_1m_line:
        return True
    else:
        return False


def on_error(ws, error):
    traceback.print_exc()
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    print("websocket connected...")
    ws.send("{'event':'addChannel','channel':'ok_sub_futureusd_etc_trade_quarter'}")


if __name__ == '__main__':
    ws = websocket.WebSocketApp("wss://real.okex.com:10440/websocket/okexapi?compress=true",
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