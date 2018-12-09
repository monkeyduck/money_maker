# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import inflate
from config_avg import spotAPI
from trade_spot_v3 import spot_buy, spot_sell
import json

import traceback
import websocket

# 默认币种handle_deque
instrument_id = "etc_usdt"
buy_price = 10000
amount = 0.1
buy_times = 0
old_order_id = None


def on_message(ws, message):
    global buy_price, buy_times
    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    if 'pong' in message or 'addChannel' in message:
        return
    jmessage = json.loads(message)

    for each_message in jmessage:
        data = each_message['data']
        asks = data['asks'][::-1]
        bids = data['bids']
        ask_price = float(asks[0][0])
        bid_price = float(bids[0][0])
        if bid_price > buy_price:
            spotAPI.revoke_order(instrument_id, old_order_id)
        #下单
        if ask_price >= bid_price * 1.0008:
            new_order_id = spot_buy(spotAPI, instrument_id, amount, bid_price + 0.0001)
            if new_order_id:
                old_order_id = new_order_id
                buy_price = bid_price + 0.0001
                buy_times += 1

                bid_info = 'bids price: %.4f, buy_price: %.4f, buy_times: %d' % (bid_price, buy_price, buy_times)
                print(bid_info)


def on_error(ws, error):
    traceback.print_exc()
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    print("websocket connected...")
    ws.send("{'event':'addChannel','channel':'ok_sub_spot_etc_usdt_depth_5'}")


if __name__ == '__main__':
    # ws = websocket.WebSocketApp("wss://real.okex.com:10442/ws/v3?compress=true",
    ws = websocket.WebSocketApp("wss://real.okex.com:10440/websocket/okexapi?compress=true",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    while True:
        ws.run_forever(ping_interval=20, ping_timeout=10)
