# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from realtime import websocket,deque,codecs,traceback,cal_rate
from time_utils import timestamp2string
from trade import buyin_less, buyin_more, json, ensure_buyin_less, \
    ensure_buyin_more,okFuture, cancel_uncompleted_order, gen_orders_data, send_email
from entity import Coin, Indicator, DealEntity
import time

# 默认币种
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


def on_message(ws, message):
    if 'pong' in message or 'addChannel' in message:
        return
    print(message)


def on_error(ws, error):
    traceback.print_exc()
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    def run(*args):
        ws.send("{'event':'addChannel','channel':'ok_sub_futureusd_etc_kline_quarter_1min'}")
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
        # print("write left lines into file...")
        # with codecs.open(file_deal, 'a+', 'UTF-8') as f:
        #     f.writelines(write_lines)
        #     write_lines = []