from client_v3 import Client
from consts import *


class LeverageAPI(Client):

    def __init__(self, api_key, api_seceret_key, passphrase, use_server_time=False):
        Client.__init__(self, api_key, api_seceret_key, passphrase, use_server_time)

    # query spot account info
    def get_account_info(self):
        return self._request_without_params(GET, LEVER_ACCOUNT)

    # query specific coin account info
    def get_coin_account_info(self, symbol):
        return self._request_without_params(GET, LEVER_COIN_ACCOUNT + str(symbol))

    # 借币
    def borrow_coin(self, instrument_id, currency, amount):
        params = {'instrument_id': instrument_id, 'currency': currency, 'amount': amount}
        return self._request_with_params(POST, LEVER_BORROW_RECORD, params)

    # 还币
    def repay_coin(self, instrument_id, currency, amount):
        params = {'instrument_id': instrument_id, 'currency': currency, 'amount': amount}
        return self._request_with_params(POST, LEVER_REPAYMENT_COIN, params)

    def query_lever_available(self, instrument_id):
        return self._request_without_params(GET, LEVER_SPECIFIC_CONFIG + instrument_id.upper() + '/availability')

    # query ledger record not paging
    def get_ledger_record(self, symbol, limit=1):
        params = {}
        if limit:
            params['limit'] = limit
        return self._request_with_params(GET, LEVER_LEDGER_RECORD + str(symbol) + '/ledger', params)

    # query ledger record with paging
    def get_ledger_record_paging(self, symbol, before, after, limit):
       params = {'from': before, 'to': after, 'limit': limit}
       return self._request_with_params(GET, LEVER_LEDGER_RECORD + str(symbol) + '/ledger', params, cursor=True)

    # take order
    def take_order(self, otype, side, instrument_id, size, margin_trading=1, client_oid='', price='', funds='', order_type='0',):
        params = {'type': otype, 'side': side, 'instrument_id': instrument_id, 'size': size, 'client_oid': client_oid,
                  'price': price, 'funds': funds, 'margin_trading': margin_trading, 'order_type': order_type}
        return self._request_with_params(POST, LEVER_ORDER, params)

    # revoke order
    def revoke_order(self, instrument_id, order_id):
        params = {'instrument_id': instrument_id}
        return self._request_with_params(POST, LEVER_REVOKE_ORDER + str(order_id), params)

    # revoke orders
    def revoke_orders(self, instrument_id, order_ids):
        params = {'instrument_id': instrument_id, 'order_ids': order_ids}
        return self._request_with_params(POST, LEVER_REVOKE_ORDERS, params)

    # revoke order handling exceptions
    def revoke_order_exception(self, instrument_id, order_id):
        try:
            self.revoke_order(instrument_id, order_id)
        except Exception as e:
            print(repr(e))

    # query orders list
    #def get_orders_list(self, status, instrument_id, before, after, limit):
    #    params = {'status': status, 'instrument_id': instrument_id, 'before': before, 'after': after, 'limit': limit}
    #    return self._request_with_params(GET, LEVER_ORDERS_LIST, params, cursor=True)

    # query orders list v3
    def get_orders_list(self, status, instrument_id, froms='', to='', limit='100'):
        params = {'status': status, 'instrument_id': instrument_id, 'limit': limit}
        if froms:
            params['from'] = froms
        if to:
            params['to'] = to
        if instrument_id:
            params['instrument_id'] = instrument_id
        return self._request_with_params(GET, LEVER_ORDER_LIST, params, cursor=True)

    # query order info
    def get_order_info(self, oid, instrument_id):
        params = {'instrument_id': instrument_id}
        return self._request_with_params(GET, LEVER_ORDER_INFO + str(oid), params)

    # query fills
    #def get_fills(self, order_id, instrument_id, before, after, limit):
    #    params = {'order_id': order_id, 'instrument_id': instrument_id, 'before': before, 'after': after, 'limit': limit}
    #    return self._request_with_params(GET, LEVER_FILLS, params, cursor=True)

    def get_fills(self, order_id, instrument_id, froms, to, limit='100'):
        params = {'order_id': order_id, 'instrument_id': instrument_id, 'from': froms, 'to': to, 'limit': limit}
        return self._request_with_params(GET, LEVER_FILLS, params, cursor=True)

    def lever_sell_market(self, instrument_id, amount):
        try:
            if amount > 0:
                ret = self.take_order('market', 'sell', instrument_id, amount, margin_trading=2, )
                if ret and ret['result']:
                    return ret["order_id"]
            return False
        except Exception as e:
            print(repr(e))
            return False

    # 全部成交或立即取消
    def lever_buy_FOK(self, instrument_id, amount, price):
        try:
            ret = self.take_order('limit', 'buy', instrument_id, amount, margin_trading=2, price=price, order_type='2')
            if ret and ret['result']:
                return ret['order_id']
            return False
        except Exception as e:
            print(repr(e))
            return False


    # 全部成交或立即取消
    def lever_sell_FOK(self, instrument_id, amount, price):
        try:
            ret = self.take_order('limit', 'sell', instrument_id, amount, margin_trading=2, price=price,
                                  order_type='2')
            if ret and ret['result']:
                return ret['order_id']
            return False
        except Exception as e:
            print(repr(e))
        return False

