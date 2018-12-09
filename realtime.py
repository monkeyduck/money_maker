#!/usr/bin/python
# -*- coding: UTF-8 -*-

import websocket
try:
    import thread
except ImportError:
    import _thread as thread
import zlib


def inflate(data):
    decompress = zlib.decompressobj(
            -zlib.MAX_WBITS  # see above
    )
    inflated = decompress.decompress(data)
    inflated += decompress.flush()
    return inflated


def connect():
    ws = websocket.WebSocket()
    ws_address = "wss://real.okex.com"
    ws_port = 10441
    ws.connect(ws_address, http_proxy_host="websocket", http_proxy_port=ws_port)


def on_message(ws, message):
    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    print(message)


def on_error(ws, error):
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    print("websocket connected...")
    ws.send("{'event':'addChannel','channel':'ok_sub_futureusd_etc_trade_quarter'}")


if __name__ == "__main__":
    ws = websocket.WebSocketApp("wss://real.okex.com:10440/websocket/okexapi?compress=true",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    while True:
        ws.run_forever(ping_interval=10, ping_timeout=8)
