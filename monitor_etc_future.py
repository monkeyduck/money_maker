# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate
from trade import buyin_less, buyin_more, ensure_buyin_less, \
    ensure_buyin_more, cancel_uncompleted_order, gen_orders_data, send_email
from strategy import get_future_Nval, get_macd
from entity import Coin, Indicator, DealEntity
import time
import json
import traceback
from collections import deque
import websocket
import codecs
import sys
import numpy as np

deque_min = deque()
deque_10s = deque()
deque_3s = deque()
deque_5m = deque()
deque_3m = deque()
latest_price = 0
ind_1min = Indicator(60)
ind_10s = Indicator(10)
ind_3s = Indicator(1)
ind_3m = Indicator(180)
ind_5m = Indicator(300)
more = 0
less = 0
moreless = 0
lessmore = 0
lessless = 0
last_avg_price = 0
buy_price = 0
highest = 0
lowest = 10000
last_5min_macd = 0
last_5min_macd_ts = 0
last_1min_ts = 0
new_macd = 0
less_trend = False

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


def coin_avg_price_change(coin_list, time_gap):
    t_rate = []
    for c_name in coin_list:
        c = Coin(c_name, "usdt")
        k_line = spotAPI.get_kline(c.get_instrument_id(), '', '', 60)
        now = float(k_line[0]['close'])
        last = float(k_line[time_gap]['open'])
        rate = (now - last) / last * 100
        t_rate.append(rate)
    return t_rate


def on_message(ws, message):
    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    if 'pong' in message or 'addChannel' in message:
        return
    global latest_price, last_avg_price, buy_price, more, less, deque_3s, deque_10s, deque_min, moreless, lessmore, \
        lessless, deque_5m, ind_3s, ind_10s, ind_1min, ind_5m, write_lines, last_5min_macd, last_5min_macd_ts, highest, \
        lowest, vol_24h, new_macd, less_trend, last_1min_ts
    jmessage = json.loads(message)

    ts = time.time()
    now_time = timestamp2string(ts)
    if int(ts) - int(last_1min_ts) >= 5:
        coin_list = ["etc", "btc", "eth", "eos", "ltc", "xrp"]
        weight_list = [0.2, 0.3, 0.2, 0.1, 0.1, 0.1]
        last_1min_ts = int(ts)
        rate_list = coin_avg_price_change(coin_list, 1)
        all_coins_1min_price_change = np.sum([rate_list[i] * weight_list[i] for i in range(len(coin_list))])
        avg_info = ''
        for i in range(len(coin_list)):
            avg_info += coin_list[i] + ': ' + str(rate_list[i]) + ' '
        avg_info += ('avg: %.3f\r\n' % all_coins_1min_price_change)
        print(avg_info)
        write_lines.append(avg_info)
        if all_coins_1min_price_change < -0.5:
            less_trend = True
        else:
            less_trend = False

    if int(ts) - int(last_5min_macd_ts) >= 300:
        last_5min_macd_ts = int(ts)
        ticker = futureAPI.get_specific_ticker(coin.get_future_instrument_id())
        vol_24h = int(int(ticker['volume_24h']) * 10 / 24 / 60 / float(ticker['last']))

        symbol = coin.name + "_usd"
        contract_type = "quarter"
        df = get_future_Nval(okFuture, symbol, contract_type, "15min", 200, 16)
        highest = list(df['highest'])[-1]

        lowest = list(df['lowest'])[-1]

        df = get_macd(okFuture, coin.name + "_usd", "quarter", "5min", 300)
        diff = list(df['diff'])
        dea = list(df['dea'])
        new_macd = 2 * (diff[-1] - dea[-1])

        if more == 0 and less == 0 and lessmore == 0 and moreless == 0 and lessless == 0:
            ret = json.loads(okFuture.future_position_4fix(coin.name+"_usd", "quarter", "1"))
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
            handle_deque(deque_3m, deal_entity, ts, ind_3m)
            handle_deque(deque_5m, deal_entity, ts, ind_5m)

            avg_3s_price = ind_3s.cal_avg_price()
            avg_10s_price = ind_10s.cal_avg_price()
            avg_min_price = ind_1min.cal_avg_price()
            avg_5m_price = ind_5m.cal_avg_price()
            price_10s_change = cal_rate(avg_3s_price, avg_10s_price)
            price_1m_change = cal_rate(avg_3s_price, avg_min_price)
            price_5m_change = cal_rate(avg_3s_price, avg_5m_price)

            if more == 1:
                if price_1m_change <= -0.2 or price_5m_change <= 0 or price_10s_change >= 0.5:
                    if sell_more_batch(coin.name, time_type, latest_price):
                        more = 0
                        thread.start_new_thread(ensure_sell_more, (coin.name, time_type,))

            elif less == 1:
                if price_1m_change >= 0.2 or price_5m_change >= 0 or price_10s_change <= -0.5:
                    if sell_less_batch(coin.name, time_type, latest_price):
                        less = 0
                        thread.start_new_thread(ensure_sell_less, (coin.name, time_type,))

            elif lessless == 1:
                if price_5m_change > 0 and new_macd > 0:
                    if sell_less_batch(coin.name, time_type, latest_price):
                        lessless = 0
                        thread.start_new_thread(ensure_sell_less, (coin.name, time_type,))

            elif lessmore == 1:
                if price_1m_change <= -0.12:
                    if sell_more_batch(coin.name, time_type, latest_price):
                        lessmore = 0
                        thread.start_new_thread(ensure_sell_more, (coin.name, time_type,))

            elif moreless == 1:
                if price_1m_change >= 0.12:
                    if sell_less_batch(coin.name, time_type, latest_price):
                        moreless = 0
                        thread.start_new_thread(ensure_sell_less, (coin.name, time_type,))

            else:
                if less_trend:
                    if ind_3m.vol > 10 * vol_24h and price_5m_change <= -0.6 and ind_1min.ask_vol > ind_1min.bid_vol and new_macd < 0:
                        if buyin_less(okFuture, coin.name, time_type, latest_price - 0.01):
                            lessless = 1
                            thread.start_new_thread(ensure_buyin_less, (okFuture, coin.name, time_type, latest_price,))
                            buy_price = latest_price
                            info = u'发出做空信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                            with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                                f.writelines(info + '\n')

                    elif ind_1min.vol > 5 * vol_24h and price_5m_change <= -0.5 and ind_1min.ask_vol > ind_1min.bid_vol:
                        if buyin_less(okFuture, coin.name, time_type, latest_price - 0.01):
                            less = 1
                            thread.start_new_thread(ensure_buyin_less, (okFuture, coin.name, time_type, latest_price,))
                            buy_price = latest_price
                            info = u'发出做空信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                            with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                                f.writelines(info + '\n')
                else:
                    if ind_3m.vol > 30 * vol_24h and price_5m_change < -0.5 and ind_1min.ask_vol > ind_1min.bid_vol:
                        if buyin_less(okFuture, coin.name, time_type, latest_price - 0.01):
                            lessless = 1
                            thread.start_new_thread(ensure_buyin_less, (okFuture, coin.name, time_type, latest_price,))
                            buy_price = latest_price
                            info = u'发出做空信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                            with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                                f.writelines(info + '\n')
                    elif avg_3s_price >= highest and 0.6 >= price_1m_change >= 0.2 and price_5m_change >= 0.3 and 0 < price_10s_change < 0.2:
                        if latest_price > avg_3s_price * 1.005:
                            continue
                        if (ind_1min.vol > 8 * vol_24h and ind_1min.bid_vol > 10 * ind_1min.ask_vol) \
                                or (ind_1min.vol > 5 * vol_24h and ind_1min.bid_vol > 20 * ind_1min.ask_vol) \
                                or (ind_1min.vol > 12 * vol_24h and ind_1min.bid_vol > 3 * ind_1min.ask_vol):
                            if buyin_more(okFuture, coin.name, time_type, latest_price+0.01):
                                more = 1
                                thread.start_new_thread(ensure_buyin_more, (okFuture, coin.name, time_type, latest_price,))
                                buy_price = latest_price
                                info = u'发出做多信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                                with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                                    f.writelines(info + '\n')

                    elif avg_3s_price <= lowest and -0.8 <= price_1m_change <= -0.2 and price_5m_change <= -0.3 and -0.2 < price_10s_change < 0:
                        if latest_price < avg_3s_price * 0.995:
                            continue
                        if (ind_1min.vol > 8 * vol_24h and ind_1min.ask_vol > 10 * ind_1min.bid_vol) \
                                or (ind_1min.vol > 5 * vol_24h and ind_1min.ask_vol > 20 * ind_1min.bid_vol) \
                                or (ind_1min.vol > 12 * vol_24h and ind_1min.ask_vol > 3 * ind_1min.ask_vol):
                            if buyin_less(okFuture, coin.name, time_type, latest_price-0.01):
                                less = 1
                                thread.start_new_thread(ensure_buyin_less, (okFuture, coin.name, time_type, latest_price,))
                                buy_price = latest_price
                                info = u'发出做空信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                                with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                                    f.writelines(info + '\n')

                    elif price_10s_change > 0 and price_1m_change > 0 and price_5m_change <= -0.5 \
                        and ind_1min.bid_vol > ind_1min.ask_vol and ind_3s.bid_vol > 10 * ind_3s.ask_vol \
                            and ind_10s.bid_vol > 10 * ind_10s.ask_vol and ind_10s.vol > 1000:
                        if buyin_more(okFuture, coin.name, time_type, latest_price + 0.01):
                            lessmore = 1
                            thread.start_new_thread(ensure_buyin_more, (okFuture, coin.name, time_type, latest_price,))
                            buy_price = latest_price
                            info = u'发出做多信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                            with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                                f.writelines(info + '\n')

                    elif price_10s_change < 0 and price_1m_change < 0 and price_5m_change >= 0.5 \
                            and ind_1min.ask_vol > ind_1min.bid_vol and ind_10s.ask_vol > 10 * ind_10s.bid_vol \
                            and ind_3s.ask_vol > 10 * ind_3s.bid_vol and ind_10s.vol > 1000:
                        if buyin_less(okFuture, coin.name, time_type, latest_price - 0.01):
                            moreless = 1
                            thread.start_new_thread(ensure_buyin_less, (okFuture, coin.name, time_type, latest_price,))
                            buy_price = latest_price
                            info = u'发出做空信号！！！买入价格：' + str(buy_price) + u', ' + now_time
                            with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                                f.writelines(info + '\n')

            price_info = deal_entity.type + u' now_price: %.4f, highest: %.4f, lowest: %.4f, 3s_price: %.4f, 10s_price: %.4f, 1m_price: %.4f, ' \
                                            u'5min_price: %.4f' \
                         % (latest_price, highest, lowest, avg_3s_price, avg_10s_price, avg_min_price, avg_5m_price)
            vol_info = u'cur_vol: %.3f, 3s vol: %.3f, 10s vol: %.3f, 1min vol: %.3f, ask_vol: %.3f, bid_vol: %.3f, ' \
                       u'3s_ask_vol: %.3f, 3s_bid_vol: %.3f, 24h_vol: %.3f, 3min vol: %.3f, 3min_ask_vol: %.3f, 3min_bid_vol: %.3f' \
                       % (deal_entity.amount, ind_3s.vol, ind_10s.vol, ind_1min.vol, ind_1min.ask_vol, ind_1min.bid_vol,
                          ind_3s.ask_vol, ind_3s.bid_vol, vol_24h, ind_3m.vol, ind_3m.ask_vol, ind_3m.bid_vol)
            rate_info = u'10s_rate: %.2f%%, 1min_rate: %.2f%%, 5min_rate: %.2f%%, 5min_macd: %.6f' \
                        % (price_10s_change, price_1m_change, price_5m_change, new_macd)
            write_info = price_info + u', ' + vol_info + u', ' + rate_info + u', ' + now_time + '\r\n'
            write_lines.append(write_info)
            if len(write_lines) >= 100:
                with codecs.open(file_deal, 'a+', 'UTF-8') as f:
                    f.writelines(write_lines)
                    write_lines = []

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
            cancel_uncompleted_order(okFuture, coin_name, time_type)
            time.sleep(1)
            jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))
            buy_available = jRet["holding"][0]["buy_available"]
            ret = okFuture.future_trade(coin_name + "_usd", time_type, '', buy_available, 3, 1, lever_rate)
            with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                f.writelines(ret + '\n')
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
    sleep_time = 3
    while sleep_time > 0:
        time.sleep(sleep_time)
        jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))
        if len(jRet["holding"]) > 0:
            cancel_uncompleted_order(okFuture, coin_name, time_type)
            time.sleep(1)
            jRet = json.loads(okFuture.future_position_4fix(coin_name + "_usd", time_type, "1"))
            sell_available = jRet["holding"][0]["sell_available"]
            ret = okFuture.future_trade(coin_name + "_usd", time_type, '', sell_available, 4, 1, lever_rate)
            with codecs.open(file_transaction, 'a+', 'utf-8') as f:
                f.writelines(ret + '\n')
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
    ws.send("{'event':'addChannel','channel':'ok_sub_futureusd_%s_trade_quarter'}" % coin.name)


if __name__ == '__main__':
    if len(sys.argv) > 2:
        coin_name = sys.argv[1]
        # 默认币种handle_deque
        coin = Coin(coin_name, "usdt")
        time_type = "quarter"
        file_transaction, file_deal = coin.gen_future_file_name()
        config_file = sys.argv[2]
        if config_file == 'config_mother':
            from config_mother import okFuture, futureAPI, spotAPI
        elif config_file == 'config_son1':
            from config_son1 import okFuture, futureAPI, spotAPI
        elif config_file == 'config_son3':
            from config_son3 import okFuture, futureAPI, spotAPI
        else:
            print('输入config_file有误，请输入config_mother or config_son1 or config_son3')
            sys.exit()
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
    else:
        print('缺少参数 coin_name, config_file')
        print('for example: python monitor_etc_future etc config_mother')