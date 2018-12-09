# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate
from trade import buyin_less, buyin_more, ensure_buyin_less, \
    ensure_buyin_more, okFuture, cancel_uncompleted_order, gen_orders_data, send_email, buyin_more_price, \
    buyin_less_price, pend_order, buyin_moreandless, acquire_orderId_by_type, get_order_info, pend_order_price
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

last_minute_ts = 0
last_second_ts = 0
buy_sell_ratio = 0.5

write_lines = []
order_id_queue = []


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
    global latest_price, last_avg_price, buy_price, more, less, deque_3s, deque_10s, deque_min, buy_sell_ratio, \
        deque_5m, ind_3s, ind_10s, ind_1min, ind_5m, write_lines, last_minute_ts, last_second_ts, order_id_queue, now_time
    jmessage = json.loads(message)

    ts = time.time()
    now_time = timestamp2string(ts)

    for each_message in jmessage:
        for jdata in each_message['data']:
            latest_price = float(jdata[1])
            exe_second(ts)
            exe_minute(ts)

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

            # 单边上涨行情持有做多单，达到卖出条件
            if more == 1:
                if price_1m_change <= -0.2 or price_5m_change <= 0:
                    if sell_more_batch(coin.name, time_type, latest_price):
                        more = 0
                        thread.start_new_thread(ensure_sell_more, (coin.name, time_type,))
            # 单边下跌行情持有做空单，达到卖出条件
            elif less == 1:
                if price_1m_change >= 0.2 or price_5m_change >= 0:
                    if sell_less_batch(coin.name, time_type, latest_price):
                        less = 0
                        thread.start_new_thread(ensure_sell_less, (coin.name, time_type,))
            # 单边上涨行情
            if price_1m_change >= incr_1m_rate and price_5m_change >= incr_5m_rate:
                # 撤单开空、平多单
                cancel_uncompleted_order(coin.name, time_type, 2)
                cancel_uncompleted_order(coin.name, time_type, 3)
                # 撤单平空单
                cancel_uncompleted_order(coin.name, time_type, 4)
                # 空单全部卖出
                if sell_less_batch(coin.name, time_type, latest_price):
                    thread.start_new_thread(ensure_sell_less, (coin.name, time_type,))
                # 做多买入
                if buyin_more(coin.name, time_type, latest_price):
                    more = 1
                    thread.start_new_thread(ensure_buyin_more, (coin.name, time_type, latest_price))

            # 单边下跌行情
            elif price_1m_change < -incr_1m_rate and price_5m_change < -incr_5m_rate:
                # 撤单开多，平空单
                cancel_uncompleted_order(coin.name, time_type, 1)
                cancel_uncompleted_order(coin.name, time_type, 4)
                # 撤单平多单
                cancel_uncompleted_order(coin.name, time_type, 3)
                # 多单全部卖出
                if sell_more_batch(coin.name, time_type, latest_price):
                    thread.start_new_thread(ensure_sell_more, (coin.name, time_type,))
                # 做空买入
                if buyin_less(coin.name, time_type, latest_price):
                    less = 1
                    thread.start_new_thread(ensure_buyin_less, (coin.name, time_type, latest_price))

            if -0.05 < price_1m_change < 0.05 and -0.02 < price_10s_change < 0.02 and ind_1min.vol < 6000 and ind_10s.vol < 1000:
                more_order_id, less_order_id = buyin_moreandless(coin.name, time_type, latest_price, 20, buy_sell_ratio)

                if more_order_id:
                    order_id_queue.append(more_order_id)
                    print('more order_id: %s' % more_order_id)

                if less_order_id:
                    order_id_queue.append(less_order_id)
                    print('less order_id: %s' % less_order_id)


def exe_second(ts):
    global last_second_ts
    if int(ts) - int(last_second_ts) >= 1:
        last_second_ts = int(ts)
        del_list = []
        # 获取未完成订单
        print("order id list: ", order_id_queue)
        for order_id in order_id_queue:
            order_info = get_order_info(coin.name, time_type, order_id)
            # 完全成交的订单
            if order_info['status'] == 2:
                deal_amount = float(order_info['deal_amount'])
                price_avg = float(order_info['price_avg'])
                order_type = int(order_info['type'])
                del_list.append(order_id)
                if order_type == 1 or order_type == 2:
                    if order_type == 1:
                        order_price = price_avg * 1.0008
                        info = u'做多买入成交！！！买入价格：' + str(price_avg) + u', 买入数量：' + str(deal_amount) + u', ' + now_time
                        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                            f.writelines(info + '\n')
                        print(info)
                    else:
                        order_price = price_avg * 0.9992
                        info = u'做空买入成交！！！买入价格：' + str(price_avg) + u', 买入数量：' + str(deal_amount) + u', ' + now_time
                        with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                            f.writelines(info + '\n')
                        print(info)
                    pend_order_price(coin.name, time_type, order_type + 2, deal_amount, order_price)

            # 已撤销的订单
            elif order_info['status'] == -1:
                del_list.append(order_id)
            # 已经生成超过10s的订单
            elif int(ts) > int(order_info['create_date'] / 1000) + 10:
                order_info = get_order_info(coin.name, time_type, order_id)
                okFuture.future_cancel(coin.name + "_usd", time_type, order_id)
                deal_amount = float(order_info['deal_amount'])
                price_avg = float(order_info['price_avg'])
                order_type = int(order_info['type'])
                if order_type == 1 or order_type == 2:
                    if order_type == 1:
                        order_price = price_avg * 1.001
                    else:
                        order_price = price_avg * 0.999
                    pend_order_price(coin.name, time_type, order_type + 2, deal_amount, order_price)
        for del_order_id in del_list:
            order_id_queue.remove(del_order_id)


def exe_minute(ts):
    global last_minute_ts, buy_sell_ratio
    if int(ts) - int(last_minute_ts) >= 60:
        last_minute_ts = int(ts)
        ret = okFuture.future_orderinfo(coin.name + "_usd", time_type, -1, 1, None, None)
        for each_order in json.loads(ret)["orders"]:
            if each_order['price'] > latest_price * 1.005 or each_order['price'] < latest_price * 0.995:
                okFuture.future_cancel(coin.name + "_usd", time_type, each_order['order_id'])

        ret = json.loads(okFuture.future_position_4fix("etc_usd", "quarter", "1"))
        print(ret)
        if len(ret["holding"]) > 0:
            buy_amount = ret["holding"][0]["buy_amount"]
            sell_amount = ret["holding"][0]["sell_amount"]
            if buy_amount > 0:
                buy_sell_ratio = buy_amount / (buy_amount + sell_amount)
                more_profit_ratio = float(ret["holding"][0]["buy_profit_lossratio"])
                buy_available = ret["holding"][0]["buy_available"]
                print("多仓盈亏: %.2f%%, 多仓可平仓数量: %d" % (more_profit_ratio, buy_available))
                if more_profit_ratio < -20:
                    cancel_uncompleted_order(coin.name, time_type, 3)
                    thread.start_new_thread(ensure_sell_more, (coin.name, time_type))
                    real_profit = float(buy_amount * more_profit_ratio / 20)
                    info = "多仓止损，亏损: %.4fETC" % real_profit
                    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                        f.writelines(info + '\n')
                    print(info)
                elif more_profit_ratio > 3:
                    cancel_uncompleted_order(coin.name, time_type, 3)
                    pend_order_price(coin.name, time_type, 3, buy_amount, latest_price)

                elif buy_available > 0:
                    buy_price_avg = ret["holding"][0]["buy_price_avg"] * 1.001
                    pend_order_price(coin.name, time_type, 3, buy_available, buy_price_avg)
            if sell_amount > 0:
                buy_sell_ratio = buy_amount / (buy_amount + sell_amount)
                less_profit_ratio = float(ret["holding"][0]["sell_profit_lossratio"])
                sell_available = ret["holding"][0]["sell_available"]
                print("空仓盈亏: %.2f%%, 空仓可平仓数量: %d" % (less_profit_ratio, sell_available))
                if less_profit_ratio < -20:
                    cancel_uncompleted_order(coin.name, time_type, 4)
                    thread.start_new_thread(ensure_sell_less, (coin.name, time_type))
                    real_profit = float(sell_amount * less_profit_ratio / 20)
                    info = "空仓止损，亏损: %.4fETC" % real_profit
                    with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                        f.writelines(info + '\n')
                    print(info)
                if less_profit_ratio > 3:
                    cancel_uncompleted_order(coin.name, time_type, 3)
                    pend_order_price(coin.name, time_type, 3, buy_amount, latest_price)
                if sell_available > 0:
                    sell_price_avg = ret["holding"][0]["sell_price_avg"] * 0.999
                    pend_order_price(coin.name, time_type, 4, sell_available, sell_price_avg)
            print("持仓多空比: %.2f" % buy_sell_ratio)
        else:
            print("确认未持仓")


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
            cancel_uncompleted_order(coin_name, time_type, 3)
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
            cancel_uncompleted_order(coin_name, time_type, 4)
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
        ws.run_forever(ping_interval=30, ping_timeout=20)