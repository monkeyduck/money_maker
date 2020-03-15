# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate, write_info_into_file
from entity import Coin, Indicator, DealEntity, INSTRUMENT_ID_LINKER
import time
import json
import traceback
from collections import deque
import websocket
import codecs
import sys

spot_latest_price = 0
swap_latest_price = 0


def on_message(ws, message):
    global spot_latest_price, swap_latest_price
    ts = time.time()
    now_time = timestamp2string(ts)

    message = bytes.decode(inflate(message), 'utf-8')  # data decompress
    json_message = json.loads(message)
    for json_data in json_message['data']:
        ins_id = json_data['instrument_id']
        if ins_id == instrument_id:
            spot_latest_price = float(json_data['last'])
        elif ins_id == swap_instrument_id:
            swap_latest_price = float(json_data['last'])
        write_info_into_file('spot price = ' + str(spot_latest_price) + ', swap price = ' + str(swap_latest_price), file_deal)
        diff = round(swap_latest_price - spot_latest_price, 4)
        diff_rate = round(diff / (spot_latest_price + 0.001) * 100, 3)
        write_info_into_file('diff = ' + str(diff) + ', rate = ' + str(diff_rate) + '%', file_deal)
        # latest_price = float(json_data['price'])
        # deal_entity = DealEntity(json_data['trade_id'], latest_price, round(float(json_data['size']), 3), ts,
        #                          json_data['side'])


def on_error(ws, error):
    traceback.write_info_exc()
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    print("websocket connected...")
    ws.send("{\"op\": \"subscribe\", \"args\": [\"spot/ticker:%s-USDT\"]}" % (coin.name.upper()))
    ws.send("{\"op\": \"subscribe\", \"args\": [\"swap/ticker:%s-USD-SWAP\"]}" % (coin.name.upper()))


if __name__ == '__main__':
    if len(sys.argv) > 2:
        coin_name = sys.argv[1]
        # 默认币种handle_deque
        coin = Coin(coin_name, "usdt")
        instrument_id = coin_name.upper() + INSTRUMENT_ID_LINKER + 'USDT'
        future_instrument_id = coin.get_future_instrument_id()
        swap_instrument_id = instrument_id.split(INSTRUMENT_ID_LINKER)[0].upper() + '-USD-SWAP'
        print('swap_instrument_id: ' + swap_instrument_id)
        file_transaction, file_deal = coin.gen_file_name()
        config_file = sys.argv[2]
        if config_file == 'config_mother':
            from config_mother import leverAPI, futureAPI, swapAPI
        # elif config_file == 'config_son1':
        #     from config_son1 import spotAPI, okFuture, futureAPI
        # elif config_file == 'config_son3':
        #     from config_son3 import spotAPI, okFuture, futureAPI
        else:
            print('输入config_file有误，请输入config_mother or config_son1 or config_son3')
            sys.exit()
        while True:
            ws = websocket.WebSocketApp("wss://real.OKEx.com:8443/ws/v3?compress=true",
                                        on_message=on_message,
                                        on_error=on_error,
                                        on_close=on_close)
            ws.on_open = on_open
            ws.run_forever(ping_interval=15, ping_timeout=10)

    else:
        print('缺少参数 coin_name, config_file')
        print('for example: python monitor_spot etc config_mother')