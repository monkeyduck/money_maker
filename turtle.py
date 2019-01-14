#!/usr/bin/python
# -*- coding: UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
import time
from config_strict import futureAPI, okFuture
from strategy import get_future_Nval
from trade_v3 import buyin_more, buyin_less, sell_more_batch, sell_less_batch, ensure_buyin_more, ensure_buyin_less, ensure_sell_less ,ensure_sell_more
from entity import Position
from utils import timestamp2string
import traceback
import sys


positions=[]    #记录仓位
position_unit = 1
WAIT_DEAL = 2   #等待成交时间（秒）
N = 0   #价格波动
highest = 0
lowest = 10000
time_gap = "15min"


class Turtle:
    def __init__(self, coin_name, instrument_id):
        self.coin_name = coin_name
        self.instrument_id = instrument_id
        self.order_queue = []
        self.volume_24 = 0

    def calc_unit(self):
        global pre_time, highest, lowest, position_unit, N
        # 计算n, 头寸
        
        account = futureAPI.get_coin_account(self.coin_name)

        manage_assets = float(account['total_avail_balance'])
        
        ticker = futureAPI.get_specific_ticker(self.instrument_id)
        
        last = float(ticker['last'])

        self.volume_24 = int(int(ticker['volume_24h']) * 10 / last)

        symbol = self.coin_name + "_usd"
        contract_type = "quarter"
        df = get_future_Nval(okFuture, symbol, contract_type, time_gap, 200)
        N = list(df['N'])[-1]

        position_unit = min(manage_assets * 0.01 / N, manage_assets / last * 0.95)

        highest = list(df['highest'])[-1]

        lowest = list(df['lowest'])[-1]
        print("价格波动N=%.4f, unit=%.4f" % (N, position_unit))

    def get_recent_vol(self, recent_minutes):
        k_line = futureAPI.get_kline(self.instrument_id, 60)
        vol = 0
        for i in range(recent_minutes):
            vol += int(k_line[i][5])
        return vol

    def build_position(self, ticker):
        global positions, highest, lowest
        try:
            last = float(ticker['last'])
            amount = int(position_unit * 2 * last)
            # 建仓
            if len(positions) == 0 and last >= highest:
                ret = futureAPI.take_order('', self.instrument_id, 1, last, amount, 1, 20)
                if ret and ret['result']:
                    new_order_id = ret['order_id']
                    print('建多仓：挂单开多，order_id: %s' % new_order_id)
                    time.sleep(WAIT_DEAL)
                    info = futureAPI.get_order_info(new_order_id, self.instrument_id)
                    print('建仓订单信息: %s' % info)
                    status = info['status']
                    if status == '2':
                        deal_price = float(info['price_avg'])
                        filled_qty = int(info['filled_qty'])
                        coin_amount = float(filled_qty * 10 / deal_price)
                        stop_loss = deal_price - 0.5 * N
                        position = Position(price=deal_price, amount=coin_amount, stop_loss=stop_loss, time=timestamp2string(time.time()),
                                            side='more')
                        positions.append(position)
                    else:
                        futureAPI.revoke_order(self.instrument_id, new_order_id)

            if len(positions) == 0 and last <= lowest:
                ret = futureAPI.take_order('', self.instrument_id, 2, last, amount, 1, 20)
                if ret and ret['result']:
                    new_order_id = ret['order_id']
                    print('建空仓：挂单开空，order_id: %s' % new_order_id)
                    time.sleep(WAIT_DEAL)
                    info = futureAPI.get_order_info(new_order_id, self.instrument_id)
                    print('订单信息: %s' % info)
                    status = info['status']
                    if status == '2':
                        deal_price = float(info['price_avg'])
                        filled_qty = int(info['filled_qty'])
                        coin_amount = float(filled_qty * 10 / deal_price)
                        stop_loss = deal_price + 0.5 * N
                        position = Position(price=deal_price, amount=coin_amount, stop_loss=stop_loss, time=timestamp2string(time.time()),
                                            side='less')
                        positions.append(position)
                    else:
                        futureAPI.revoke_order(self.instrument_id, new_order_id)

            highest = max(highest, last)
            lowest = min(lowest, last)

        except Exception as e:
            print('建仓出错, %s' % repr(e))
            traceback.print_exc()

    def add_position(self, ticker):
        global positions, N
        try:
            # 加仓&止损
            if len(positions) > 0:
                last = float(ticker['last'])
                print('当前仓位: %d, 仓位信息：' % len(positions))
                for i in range(len(positions)):
                    cur = positions[i]
                    if cur.side == 'more':
                        profit = (last - cur.price) / cur.price * 100
                    else:
                        profit = (cur.price - last) / cur.price * 100
                    print('第%d个仓位: 委托价: %.3f, 数量: %.2f, 方向: %s, 止损价: %.3f, 买入时间: %s, 当前盈利: %.2f%%'
                          % (i+1, cur.price, cur.amount, cur.side, cur.stop_loss, cur.time, profit))
                prev_position = positions[-1]
                last_buy_price = prev_position.price
                side = prev_position.side
                amount = int(position_unit * 2 * last)
                last_stop_loss_price = prev_position.stop_loss

                if side == 'more':
                    if last-last_buy_price >= 0.5 * N:
                        ret = futureAPI.take_order('', self.instrument_id, 1, last, amount, 1, 20)
                        if ret and ret['result']:
                            new_order_id = ret['order_id']
                            print('多仓加仓，order_id: %s' % new_order_id)
                            time.sleep(WAIT_DEAL)
                            info = futureAPI.get_order_info(new_order_id, self.instrument_id)
                            print('订单信息: %s' % info)
                            status = info['status']
                            if status == '2':
                                deal_price = float(info['price_avg'])
                                filled_qty = int(info['filled_qty'])
                                coin_amount = float(filled_qty * 10 / deal_price)
                                stop_loss = deal_price - 0.5 * N
                                position = Position(price=deal_price, amount=coin_amount, stop_loss=stop_loss, time=timestamp2string(time.time()),
                                                    side='more')
                                positions.append(position)
                            else:
                                futureAPI.revoke_order(self.instrument_id, new_order_id)

                    elif last <= last_stop_loss_price or last <= lowest:
                        sell_more_batch(futureAPI, self.instrument_id, last)
                        thread.start_new_thread(ensure_sell_more, (futureAPI, self.coin_name, self.instrument_id, last, last_buy_price,))
                        positions = []
                if side == 'less':
                    if last < last_buy_price - 0.5 * N:
                        ret = futureAPI.take_order('', self.instrument_id, 2, last, amount, 1, 20)
                        if ret and ret['result']:
                            new_order_id = ret['order_id']
                            print('空仓加仓，order_id: %s' % new_order_id)
                            time.sleep(WAIT_DEAL)
                            info = futureAPI.get_order_info(new_order_id, self.instrument_id)
                            print('订单信息: %s' % info)
                            status = info['status']
                            if status == '2':
                                deal_price = float(info['price_avg'])
                                filled_qty = int(info['filled_qty'])
                                coin_amount = float(filled_qty * 10 / deal_price)
                                stop_loss = deal_price + 0.5 * N
                                position = Position(price=deal_price, amount=coin_amount, stop_loss=stop_loss, time=timestamp2string(time.time()),
                                                    side='less')
                                positions.append(position)
                            else:
                                futureAPI.revoke_order(self.instrument_id, new_order_id)

                    elif last >= last_stop_loss_price or last >= highest:
                        sell_less_batch(futureAPI, self.instrument_id, last)
                        thread.start_new_thread(ensure_sell_less, (futureAPI, self.coin_name, self.instrument_id, last, last_buy_price,))
                        positions = []
        except Exception as e:
            print('加仓出错：%s' % repr(e))
            traceback.print_exc()

    def process_pending_orders(self):
        print('当前订单队列共有%d个订单' % len(self.order_queue))
        del_list = []
        for i in range(len(self.order_queue)):
            old_order_id = self.order_queue[i]
            try:
                old_order_info = futureAPI.get_order_info(old_order_id, self.instrument_id)
                print('第%d个订单信息为：%s' % (i+1, old_order_info))
                status = old_order_info['status']
                type = int(old_order_info['type'])
                last = float(old_order_info['price'])
    
                # 已撤单
                if status == '-1':
                    del_list.append(old_order_id)
    
                # 全部成交
                elif status == '2':
                    del_list.append(old_order_id)
    
                # 部分成交或等待成交
                else:
                    futureAPI.revoke_order(self.instrument_id, old_order_id)
                    amount = int(old_order_info['size'])
                    filled_amt = int(old_order_info['filled_qty'])
                    unfilled = amount - filled_amt
                    if unfilled >= 1:
                        if type == 1:
                            buyID = buyin_more(futureAPI, self.coin_name, self.instrument_id, False, unfilled)
                        elif type == 2:
                            buyID = buyin_less(futureAPI, self.coin_name, self.instrument_id, False, unfilled)
                        else:
                            continue
                        if buyID:
                            self.order_queue.append(buyID)
                    else:
                        del_list.append(old_order_id)
            except Exception as e:
                print(repr(e))
                traceback.print_exc()
                del_list.append(old_order_id)
                continue

        # 删除已成交和已撤销订单
        for to_del_id in del_list:
            self.order_queue.remove(to_del_id)


if __name__ == '__main__':
    if len(sys.argv) > 2:
        coin_name = sys.argv[1]
        print(coin_name.upper())
        time_gap = sys.argv[2]
        time_type = coin_name.upper() + "-USD-190329"
        turtle = Turtle(coin_name, "ETC-USD-190329")
        prev_calc_time = 0
        while True:
            try:
                now_time = int(time.time())
                if now_time - prev_calc_time > 600:
                    prev_calc_time = now_time
                    turtle.calc_unit()
                ticker = futureAPI.get_specific_ticker(turtle.instrument_id)
                last = float(ticker['last'])
                recent_vol = turtle.get_recent_vol(2)
                print('最新: %.3f, 最高: %.3f， 最低: %.3f, 成交量: %d, 时间: %s' % (last,
                highest, lowest, recent_vol, timestamp2string(time.time())))
                vol_24h = int(int(ticker['volume_24h']) / 24 / 60)
                if recent_vol > 6 * vol_24h:
                    turtle.build_position(ticker)
                turtle.add_position(ticker)
                # turtle.process_pending_orders()
                time.sleep(1)
            except Exception as e:
                print(repr(e))
                traceback.print_exc()
                continue
    else:
        print('缺少参数')
        print('for example: python turtle.py `eos` `5min`')
