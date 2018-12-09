import time
import traceback
import copy
try:
    import thread
except ImportError:
    import _thread as thread

class SpotMaker:
    # 价格趋势系数
    def price_trend_factor(self, trades, buy1_price, sell1_price, buy2_price, sell2_price, buy3_price, sell3_price, vol_list, index_type=None, symmetric=True):
        prices = trades["price"].values.tolist()
        latest_trades = prices[-6:]
        mid_price = (buy1_price+sell1_price)/2*0.7 + (buy2_price+sell2_price)/2*0.2 + (buy3_price+sell3_price)/2*0.1
        latest_trades.append(mid_price)
        is_bull_trend = False
        is_bear_trend = False
        last_price_too_far_from_latest = False
        has_large_vol_trade = False

        if latest_trades[-1] > max(latest_trades[:-1]) + latest_trades[-1]*0.00005 or (latest_trades[-1] > max(latest_trades[:-2]) + latest_trades[-1]*0.00005 and latest_trades[-1] > latest_trades[-2]):
            is_bull_trend = True
        elif latest_trades[-1] < min(latest_trades[:-1]) - latest_trades[-1]*0.00005 or (latest_trades[-1] < min(latest_trades[:-2]) - latest_trades[-1]*0.00005 and latest_trades[-1] < latest_trades[-2]):
            is_bear_trend = True

        if abs(latest_trades[-1] - latest_trades[-2]*0.7 - latest_trades[-3]*0.2 - latest_trades[-4]*0.1) > latest_trades[-1]*0.002:
            last_price_too_far_from_latest = True

        if max(vol_list) > 20:
            has_large_vol_trade = True

        if is_bull_trend or is_bear_trend or last_price_too_far_from_latest or has_large_vol_trade:
            return 0

        if index_type == "rsi":
            prices = trades["price"]
            index = indicators.rsi_value(prices, len(prices)-1)
        else:
            index = self.buy_trades_ratio(trades)
        # 价格趋势严重，暂停交易
        if index <= 20 or index >= 80:
            return 0

        # 对称下单时，factor用来调整下单总数
        if symmetric:
            factor = 1 - abs(index-50)/50
        # 非对称下单时，factor用来调整买入订单的数量
        else:
            factor = index / 50
        return factor

    def trade_thread(self):
        while True:
            try:
                if self.timeInterval > 0:
                    self.timeLog("Trade - 等待 %d 秒进入下一个循环..." % self.timeInterval)
                    time.sleep(self.timeInterval)

                # 检查order_info_list里面还有没有pending的order，然后cancel他们
                order_id_list = []
                for odr in self.order_info_list:
                    order_id_list.append(odr["order_id"])
                self.huobi_cancel_pending_orders(order_id_list=order_id_list)
                self.order_info_list = []

                account = self.get_huobi_account_info()

                buy1_price = self.get_huobi_buy_n_price()
                sell1_price = self.get_huobi_sell_n_price()
                buy2_price = self.get_huobi_buy_n_price(n=2)
                sell2_price = self.get_huobi_sell_n_price(n=2)
                buy3_price = self.get_huobi_buy_n_price(n=3)
                sell3_price = self.get_huobi_sell_n_price(n=3)

                buy1_vol = self.get_huobi_buy_n_vol()
                sell1_vol = self.get_huobi_sell_n_vol()
                buy2_vol = self.get_huobi_buy_n_vol(n=2)
                sell2_vol = self.get_huobi_sell_n_vol(n=2)
                buy3_vol = self.get_huobi_buy_n_vol(n=3)
                sell3_vol = self.get_huobi_sell_n_vol(n=3)
                buy4_vol = self.get_huobi_buy_n_vol(n=4)
                sell4_vol = self.get_huobi_sell_n_vol(n=4)
                buy5_vol = self.get_huobi_buy_n_vol(n=5)
                sell5_vol = self.get_huobi_sell_n_vol(n=5)

                vol_list = [buy1_vol, buy2_vol, buy3_vol, buy4_vol, buy5_vol, sell1_vol, sell2_vol, sell3_vol,
                            sell4_vol, sell5_vol]

                latest_trades_info = self.get_latest_market_trades()

                # 账户或者行情信息没有取到
                if not all([account, buy1_price, sell1_price]):
                    continue

                self.heart_beat_time.value = time.time()

                global init_account_info
                if init_account_info is None:
                    init_account_info = account

                global account_info_for_r_process
                account_info_for_r_process = copy.deepcopy(self.account_info)

                min_price_spread = self.arbitrage_min_spread(self.get_huobi_buy_n_price(), self.min_spread_rate)
                # 计算下单数量
                total_qty = min(self.total_qty_per_transaction, account.btc, account.cash / buy1_price)
                trend_factor = self.price_trend_factor(latest_trades_info, buy1_price, sell1_price, buy2_price,
                                                       sell2_price, buy3_price, sell3_price, vol_list,
                                                       symmetric=self.is_symmetric)
                if self.is_symmetric:
                    total_qty *= trend_factor
                    buy_ratio = 1
                    sell_ratio = 1
                else:
                    buy_ratio = trend_factor
                    sell_ratio = 2 - trend_factor
                order_data_list = self.orders_price_and_qty_from_min_spread(buy1_price, sell1_price, total_qty,
                                                                            self.price_step, self.qty_step,
                                                                            self.min_qty_per_order,
                                                                            self.max_qty_per_order,
                                                                            min_price_spread, buy_ratio=buy_ratio,
                                                                            sell_ratio=sell_ratio)
                self.spot_batch_limit_orders(self.market_type, order_data_list,
                                             time_interval_between_threads=self.time_interval_between_threads)
                current_spread = self.bid_ask_spread(self.exchange)
                self.save_transactions(signal_spread=current_spread, signal_side="market_maker")
                self.latest_trade_time = time.time()
            except Exception:
                self.timeLog(traceback.format_exc())
                continue


    #其中，做市算法下单模块的代码如下：

    # 从最小价差向外挂单
    def orders_price_and_qty_from_min_spread(self, buy1_price, sell1_price, total_qty, price_step, qty_step,
                                             min_qty_per_order, max_qty_per_order, min_price_spread, buy_ratio=1,
                                             sell_ratio=1):
        orders_list = []
        remaining_qty = total_qty
        avg_price = (buy1_price + sell1_price) / 2

        if buy_ratio > 1:  # price is going down
            avg_price += 0.2
        elif sell_ratio > 1:  # price is going up
            avg_price -= 0.2

        buy_order_price = avg_price - min_price_spread / 2
        sell_order_price = avg_price + min_price_spread / 2
        order_qty = min(min_qty_per_order, remaining_qty)
        while remaining_qty >= min_qty_per_order and buy_order_price > buy1_price and sell_order_price < sell1_price:
            # buy_order_qty = max(order_qty * buy_ratio, self.min_order_qty)
            # sell_order_qty = max(order_qty * sell_ratio, self.min_order_qty)
            buy_order_qty = max(order_qty, self.min_order_qty)
            sell_order_qty = max(order_qty, self.min_order_qty)
            orders_list.append({"price": buy_order_price, "amount": buy_order_qty, "type": "buy"})
            orders_list.append({"price": sell_order_price, "amount": sell_order_qty, "type": "sell"})
            remaining_qty -= buy_order_qty
            buy_order_price -= price_step
            sell_order_price += price_step
            order_qty = min(buy_order_qty + qty_step, max_qty_per_order)
            order_qty = min(remaining_qty, order_qty)
        return orders_list

    def go(self):
        self.timeLog("日志启动于 %s" % self.getStartRunningTime().strftime(self.TimeFormatForLog))
        self.timeLog("开始cancel pending orders")
        self.huobi_cancel_pending_orders()
        self.timeLog("完成cancel pending orders")

        thread_pool = []
        thread_pool.append(Thread(target=self.trade_thread, args=()))
        if self.need_rebalance:
            spot_rebalance = SpotRebalance(self.heart_beat_time, self.coinMarketType, depth_data=self.depth_data,
                                           transaction_info=self.order_info_queue)
            thread_pool.append(Thread(target=spot_rebalance.go, args=()))
        for thread in thread_pool:
            thread.setDaemon(True)
            thread.start()
        for thread in thread_pool:
            thread.join()


class SpotRebalance:
    def __init__(self, heart_beat_time, coinMarketType, depth_data, transaction_info):
        pass

    def go(self):
        while True:
            try:
                if self.timeInterval > 0:
                    self.timeLog("R-balance - 等待 %d 秒进入下一个循环..." % self.timeInterval)
                    time.sleep(self.timeInterval)

                # 检查order_info_list里面还有没有pending的order，然后cancel他们
                order_id_list = []
                for odr in self.order_info_list:
                    order_id_list.append(odr["order_id"])
                self.huobi_cancel_pending_orders(order_id_list=order_id_list)
                self.order_info_list = []

                global init_account_info
                account_info = self.get_huobi_account_info_1(max_delay=self.account_info_max_delay)
                buy_1_price = self.get_huobi_buy_n_price()
                sell_1_price = self.get_huobi_sell_n_price()

                if not all([account_info, init_account_info, buy_1_price, sell_1_price]):
                    continue

                self.heart_beat_time.value = time.time()

                qty_delta = account_info.btc_total - init_account_info.btc_total
                cash_delta = account_info.cash_total - init_account_info.cash_total

                # 需要卖出
                if qty_delta >= self.min_order_qty:
                    trade_type = helper.SPOT_TRADE_TYPE_SELL
                    order_qty = qty_delta
                    if cash_delta <= 0:
                        holding_avg_price = abs(cash_delta / qty_delta)
                    else:
                        holding_avg_price = None
                    init_price = sell_1_price
                    if holding_avg_price is None:
                        worst_price = buy_1_price
                    else:
                        worst_price = max(buy_1_price, holding_avg_price * (1 + self.mim_spread_rate))
                        # worst_price = buy_1_price
                # 需要买入
                elif qty_delta <= -self.min_order_qty:
                    trade_type = helper.SPOT_TRADE_TYPE_BUY
                    order_qty = -qty_delta
                    if cash_delta > 0:
                        holding_avg_price = abs(cash_delta / qty_delta)
                    # 钱与币都减少，卖出的均价为负
                    else:
                        holding_avg_price = None
                    init_price = buy_1_price
                    if holding_avg_price is None:
                        worst_price = sell_1_price
                    else:
                        worst_price = min(sell_1_price, holding_avg_price * (1 - self.mim_spread_rate))
                        # worst_price = sell_1_price
                # 无需操作
                else:
                    continue

                # 下单限价单
                res = self.spot_order_to_target_qty(self.market_type, self.coin_type, trade_type, order_qty, init_price,
                                                    price_step=self.price_step, worst_price=worst_price,
                                                    max_qty_per_order=self.qty_per_order, max_time=self.max_time)
                if res is None:
                    total_executed_qty = 0
                else:
                    total_executed_qty, deal_avg_price = res

                remaining_qty = order_qty - total_executed_qty

                # 若设置了参数MARKET_ORDER_WHEN_QTY_DIFF_TOO_LARGE 为True，则可能需要市价单补单
                if remaining_qty >= self.min_order_qty and self.use_market_order:
                    current_diff_ratio = remaining_qty / init_account_info.btc_total
                    if self.max_qty_per_market_order is not None:
                        order_qty = min(remaining_qty, self.max_qty_per_market_order)
                    else:
                        order_qty = remaining_qty
                    order_id = None
                    # 市价卖出
                    if trade_type == helper.SPOT_TRADE_TYPE_SELL and current_diff_ratio > self.max_positive_diff_ratio:
                        order_id = self.spot_order(self.market_type, self.coin_type, trade_type,
                                                   helper.ORDER_TYPE_MARKET_ORDER, quantity=order_qty)
                    # 市价买入
                    elif trade_type == helper.SPOT_TRADE_TYPE_BUY and current_diff_ratio > self.max_negative_diff_ratio:
                        cash_amount = sell_1_price * order_qty
                        order_id = self.spot_order(self.market_type, self.coin_type, trade_type,
                                                   helper.ORDER_TYPE_MARKET_ORDER, cash_amount=cash_amount)
                    if order_id is not None:
                        self.spot_order_wait_and_cancel(self.market_type, self.coin_type, order_id)

                self.save_transactions(signal_side="rebalance")
                self.latest_trade_time = time.time()
            except Exception:
                self.timeLog(traceback.format_exc())
                continue


    def spot_order_to_target_qty(self, marketType, coinType, trade_type, target_qty, init_order_price, price_step=None,
                                 worst_price=None, max_qty_per_order=None, max_time=None):
        """
        交易目标数量的标的，不停的下单、撤单、补单（补单时将价格向不利方向小幅移动），直至全部成交或价格达到某一条件或超过一定时间退出
        :param marketType: 1: huobi, 2: okcoin
        :param coinType: 1: btc, 2: ltc
        :param trade_type: helper.SPOT_TRADE_TYPE_BUY or helper.SPOT_TRADE_TYPE_SELL
        :param target_qty: 成交的目标数量
        :param init_order_price: 最初的下单价格
        :param price_step: 每次补单的价格变动，默认 0.5元
        :param worst_price: 最不利的价格
        :param max_qty_per_order: 每次下单的最大数量， 默认0.005个
        :param max_time: 最大执行时间， 默认 60秒
        :return:
        """
        if price_step is None:
            price_step = 0.5
        if max_qty_per_order is None:
            max_qty_per_order = 0.005
        if max_time is None:
            max_time = 60
        if marketType == helper.HUOBI_MARKET_TYPE:
            min_order_qty = helper.HUOBI_BTC_MIN_ORDER_QTY
        elif marketType == helper.OKCOIN_MARKET_TYPE:
            min_order_qty = helper.OKCOIN_BTC_MIN_ORDER_QTY
        else:
            return None
        if trade_type == helper.SPOT_TRADE_TYPE_SELL:
            price_step *= -1
        total_executed_qty = 0
        total_deal_cash_amount = 0
        remaining_qty = target_qty - total_executed_qty
        start_time = time.time()
        end_time = start_time + max_time
        order_price = init_order_price
        if trade_type == helper.SPOT_TRADE_TYPE_BUY:
            if worst_price is None:
                worst_price = init_order_price * 1.1
            order_price = min(order_price, worst_price)
        else:
            if worst_price is None:
                worst_price = init_order_price * 0.9
            order_price = max(order_price, worst_price)

        while True:
            order_qty = min(remaining_qty, max_qty_per_order)
            if order_qty < min_order_qty:
                break
            order_id = self.spot_order(marketType, coinType, trade_type, helper.ORDER_TYPE_LIMIT_ORDER,
                                       price=order_price,
                                       quantity=order_qty)
            if order_id is None:
                continue
            self.spot_order_wait_and_cancel(marketType, coinType, order_id)
            res = self.spot_order_info_detail(marketType, coinType, order_id)
            if res is None:
                continue
            else:
                executed_qty = res[1]
                avg_price = res[2]
            total_executed_qty += executed_qty
            total_deal_cash_amount += executed_qty * avg_price
            remaining_qty = target_qty - total_executed_qty
            order_price += price_step
            if remaining_qty < min_order_qty:
                self.timeLog("剩余未成交数量(%.4f)小于交易所最小下单数量(%.4f)" % (remaining_qty, min_order_qty))
                break
            if time.time() > end_time:
                self.timeLog("超过了最大执行时间，停止继续下单")
                break
            if trade_type == helper.SPOT_TRADE_TYPE_BUY:
                if order_price > worst_price:
                    self.timeLog("当前买入下单价格(%.2f元)大于最差价格(%.2f元)" % (order_price, worst_price))
                    break
            else:
                if order_price < worst_price:
                    self.timeLog("当前卖出下单价格(%.2f元)小于最差价格(%.2f元)" % (order_price, worst_price))
                    break
        if total_executed_qty > 0:
            deal_avg_price = total_deal_cash_amount / total_executed_qty
        else:
            deal_avg_price = 0
        return total_executed_qty, deal_avg_price


