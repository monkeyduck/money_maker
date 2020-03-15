# !/usr/bin/python
# -*-coding:UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from utils import timestamp2string, cal_rate, inflate, send_email, write_info_into_file
from entity import Coin, Indicator, DealEntity, INSTRUMENT_ID_LINKER
import time
import sys

swap_size = 1


def do_more_and_less_same_time():
    ticker = swapAPI.get_specific_ticker(swap_instrument_id)
    # 买一价
    best_ask_price = float(ticker['best_ask'])
    # 卖一价
    best_bid_price = float(ticker['best_bid'])
    # take_order(self, instrument_id, size, type, order_type, price, client_oid, match_price):
    size = swap_size
    swap_more_order_result = swapAPI.take_order(swap_instrument_id, size, 1, 0, best_ask_price, None, None)
    swap_less_order_result = swapAPI.take_order(swap_instrument_id, size, 2, 0, best_bid_price, None, None)
    time.sleep(0.5)
    if swap_more_order_result and swap_more_order_result['result'] \
            and swap_less_order_result and swap_less_order_result['result']:
        swap_more_order_id = swap_more_order_result['order_id']
        swap_less_order_id = swap_less_order_result['order_id']
        write_info_into_file('合约做多下单成功，订单id: ' + str(swap_more_order_id), file_transaction)
        write_info_into_file('合约做空下单成功，订单id: ' + str(swap_less_order_id), file_transaction)
        return swap_more_order_id, swap_less_order_id
    return False, False


def stop_swap_more(size):
    swap_price_latest = float(swapAPI.get_specific_ticker(swap_instrument_id)['best_bid'])
    swap_order_result = swapAPI.take_order(swap_instrument_id, size, 3, 0, swap_price_latest, None, None)
    time.sleep(0.5)
    if swap_order_result and swap_order_result['result'] == 'true':
        swap_order_id = swap_order_result['order_id']
        write_info_into_file('做多卖出order_id: ' + str(swap_order_id), file_transaction)
        a = swapAPI.get_order_info('EOS-USD-SWAP', swap_order_id)
        if a['state'] == '2':
            thread.start_new_thread(send_email, ('做多卖出成交', ))
            return True
        elif a['state'] == '-1':
            return False
        else:
            swapAPI.revoke_order(swap_order_id, swap_instrument_id)
            return False
    return False


def stop_swap_less(size):
    swap_price_latest = float(swapAPI.get_specific_ticker(swap_instrument_id)['best_ask'])
    swap_order_result = swapAPI.take_order(swap_instrument_id, size, 4, 0, swap_price_latest, None, None)
    time.sleep(0.5)
    if swap_order_result and swap_order_result['result'] == 'true':
        swap_order_id = swap_order_result['order_id']
        write_info_into_file('做空卖出order_id: ' + str(swap_order_id), file_transaction)
        order_info = swapAPI.get_order_info('EOS-USD-SWAP', swap_order_id)
        if order_info['state'] == '2':
            thread.start_new_thread(send_email, ('做空卖出成交',))
            return True
        elif order_info['state'] == '-1':
            return False
        else:
            swapAPI.revoke_order(swap_order_id, swap_instrument_id)
            return False
    return False


if __name__ == '__main__':
    if len(sys.argv) > 2:
        less = 0
        more = 0
        max_profit_rate = 0
        swap_less_price = 0
        swap_less_time = 0
        swap_more_price = 0
        swap_more_time = 0

        coin_name = sys.argv[1]
        # 默认币种handle_deque
        coin = Coin(coin_name, "usdt")
        instrument_id = coin.get_instrument_id()
        future_instrument_id = coin.get_future_instrument_id()
        swap_instrument_id = coin.name.upper() + '-USD-SWAP'
        print('swap_instrument_id: ' + swap_instrument_id)
        file_transaction, file_deal = coin.gen_file_name()
        config_file = sys.argv[2]
        if config_file == 'config_mother':
            from config_mother import leverAPI, futureAPI, swapAPI
        else:
            print('输入config_file有误，请输入config_mother or config_son1 or config_son3')
            sys.exit()
        while True:
            time.sleep(0.1)
            ts = time.time()
            now_time = timestamp2string(ts)
            if less == 0 and more == 0:
                more_id, less_id = do_more_and_less_same_time()
                if more_id and less_id:
                    swap_order_info = swapAPI.get_order_info(swap_instrument_id, more_id)
                    write_info_into_file('做多 order info: ' + str(swap_order_info), file_transaction)
                    if swap_order_info['state'] == '2':
                        more = 1
                        swap_more_time = int(ts)
                        swap_more_price = float(swap_order_info['price_avg'])
                        write_info_into_file('做多订单成交，成交信息：' + str(swap_order_info), file_transaction)
                        thread.start_new_thread(send_email, ('合约做多, 价格：' + str(swap_more_price),))
                        break
                    elif swap_order_info['state'] == '-1':
                        pass
                    else:
                        swapAPI.revoke_order(more_id, swap_instrument_id)

                    swap_order_info = swapAPI.get_order_info(swap_instrument_id, less_id)
                    if swap_order_info['state'] == '2':
                        less = 1
                        swap_less_time = int(ts)
                        swap_less_price = float(swap_order_info['price_avg'])
                        write_info_into_file('做空订单成交，成交信息：' + str(swap_order_info), file_transaction)
                        thread.start_new_thread(send_email, ('合约做空，价格：' + str(swap_less_price),))
                        break
                    elif swap_order_info['state'] == '-1':
                        pass
                    else:
                        swapAPI.revoke_order(less_id, swap_instrument_id)

                    while True:
                        if more == 1 and less == 1:
                            write_info_into_file('多空订单均成交！做多价：' + str(swap_more_price) + ',做空价：' + str(swap_less_price), file_transaction)
                            break
                        elif more == 0 and less == 0:
                            break
                        elif more == 0 and less == 1:
                            swap_price_latest = float(swapAPI.get_specific_ticker(swap_instrument_id)['best_ask'])
                            # take_order(self, instrument_id, size, type, order_type, price, client_oid, match_price):
                            size = swap_size
                            swap_order_result = swapAPI.take_order(swap_instrument_id, size, 1, 0, swap_price_latest,
                                                                   None, None)
                            time.sleep(0.5)
                            if swap_order_result and swap_order_result['result']:
                                swap_order_id = swap_order_result['order_id']
                                swap_order_info = swapAPI.get_order_info(swap_instrument_id, swap_order_id)
                                if swap_order_info['state'] == '2':
                                    more = 1
                                    swap_more_time = int(ts)
                                    swap_more_price = float(swap_order_info['price_avg'])
                                    thread.start_new_thread(send_email, ('合约做多, 价格：' + str(swap_more_price),))
                                    break
                                elif swap_order_info['state'] == '-1':
                                    continue
                                else:
                                    swapAPI.revoke_order(swap_order_id, swap_instrument_id)

                        else:
                            swap_price_latest = float(swapAPI.get_specific_ticker(swap_instrument_id)['best_bid'])
                            # take_order(self, instrument_id, size, type, order_type, price, client_oid, match_price):
                            size = swap_size
                            write_info_into_file('ready to swap less, size :' + str(size), file_transaction)
                            swap_order_result = swapAPI.take_order(swap_instrument_id, size, 2, 0, swap_price_latest,
                                                                   None, None)
                            time.sleep(0.5)
                            if swap_order_result and swap_order_result['result']:
                                swap_order_id = swap_order_result['order_id']
                                swap_order_info = swapAPI.get_order_info(swap_instrument_id, swap_order_id)
                                if swap_order_info['state'] == '2':
                                    less = 1
                                    swap_less_time = int(ts)
                                    swap_less_price = float(swap_order_info['price_avg'])
                                    thread.start_new_thread(send_email, ('合约做空，价格：' + str(swap_less_price),))
                                    break
                                elif swap_order_info['state'] == '-1':
                                    continue
                                else:
                                    swapAPI.revoke_order(swap_order_id, swap_instrument_id)
            elif less == 0 and more == 1:
                position_info = swapAPI.get_specific_position(swap_instrument_id)
                for pos in position_info['holding']:
                    if pos['side'] == 'long':
                        margin = float(pos['margin'])
                        profit = float(pos['unrealized_pnl'])
                        available = int(pos['avail_position'])
                        profit_rate = round(profit / margin * 100, 2)
                        max_profit_rate = max(max_profit_rate, profit_rate)
                        if profit_rate < max_profit_rate - 10:
                            if stop_swap_more(available):
                                more = 0

            elif less == 1 and more == 0:
                position_info = swapAPI.get_specific_position(swap_instrument_id)
                for pos in position_info['holding']:
                    if pos['side'] == 'short':
                        margin = float(pos['margin'])
                        profit = float(pos['unrealized_pnl'])
                        available = int(pos['avail_position'])
                        profit_rate = round(profit / margin * 100, 2)
                        max_profit_rate = max(max_profit_rate, profit_rate)
                        if profit_rate < max_profit_rate - 10:
                            if stop_swap_less(available):
                                less = 0

            elif less == 1 and more == 1:
                more_profit_rate = 0
                less_profit_rate = 0
                available = swap_size
                position_info = swapAPI.get_specific_position(swap_instrument_id)
                for pos in position_info['holding']:
                    if pos['side'] == 'long':
                        margin = float(pos['margin'])
                        profit = float(pos['unrealized_pnl'])
                        available = int(pos['avail_position'])
                        more_profit_rate = profit / margin * 100
                        print('做多收益%.4f个%s,收益率：%.2f%%' % (profit, coin_name.upper(), more_profit_rate))
                    if pos['side'] == 'short':
                        margin = float(pos['margin'])
                        profit = float(pos['unrealized_pnl'])
                        available = int(pos['avail_position'])
                        less_profit_rate = profit / margin * 100
                        print('做空收益%.4f个%s,收益率：%.2f%%' % (profit, coin_name.upper(), less_profit_rate))
                if more_profit_rate < -20:
                    if stop_swap_more(available):
                        max_profit_rate = less_profit_rate
                        more = 0
                if less_profit_rate < -20:
                    if stop_swap_less(available):
                        max_profit_rate = more_profit_rate
                        less = 0
    else:
        print('缺少参数 coin_name, config_file')
        print('for example: python monitor_spot etc config_mother')


