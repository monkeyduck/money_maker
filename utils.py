#!/usr/bin/python
# -*- coding: UTF-8 -*-

import smtplib
import zlib
from email.mime.text import MIMEText
from email.header import Header
import hmac
import base64
import datetime
import consts as c
import time
import codecs


def sign(message, secretKey):
    mac = hmac.new(bytes(secretKey, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    d = mac.digest()
    return base64.b64encode(d)


def pre_hash(timestamp, method, request_path, body):
    return str(timestamp) + str.upper(method) + request_path + body


def get_header(api_key, sign, timestamp, passphrase):
    header = dict()
    header[c.CONTENT_TYPE] = c.APPLICATION_JSON
    header[c.OK_ACCESS_KEY] = api_key
    header[c.OK_ACCESS_SIGN] = sign
    header[c.OK_ACCESS_TIMESTAMP] = str(timestamp)
    header[c.OK_ACCESS_PASSPHRASE] = passphrase

    return header


def parse_params_to_str(params):
    url = '?'
    for key, value in params.items():
        url = url + str(key) + '=' + str(value) + '&'

    return url[0:-1]


def get_timestamp():
    now = datetime.datetime.now()
    t = now.isoformat()
    return t + "Z"


def signature(timestamp, method, request_path, body, secret_key):
    if str(body) == '{}' or str(body) == 'None':
        body = ''
    message = str(timestamp) + str.upper(method) + request_path + str(body)
    mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    d = mac.digest()
    return base64.b64encode(d)


def inflate(data):
    decompress = zlib.decompressobj(
            -zlib.MAX_WBITS  # see above
    )
    inflated = decompress.decompress(data)
    inflated += decompress.flush()
    return inflated


def string2timestamp(stime):
    # 格式化时间
    if '.' in stime:
        format_time = stime.split('.')[0]
    else:
        format_time = stime
    # 时间
    try:
        ts = time.strptime(format_time, "%Y-%m-%dT%H:%M:%S")
        return int(time.mktime(ts))
    except Exception as e:
        print(repr(e))
        print(stime)


def timestamp2string(ts):
    try:
        time_stamp = int(ts)
        if len(str(time_stamp)) > 10:
            ts = float(time_stamp) / 1000
        else:
            ts = time_stamp
        d = datetime.datetime.fromtimestamp(ts)
        str1 = d.strftime("%Y-%m-%d %H:%M:%S")
        return str1
    except Exception as e:
        return ts


def write_info_into_file(info, file_name):
    print(info)
    with codecs.open(file_name, 'a+', 'utf-8') as f:
        f.writelines(timestamp2string(time.time()) + ' ' + info + '\n')


def cal_rate(cur_price, last_price):
    if last_price != 0:
        return round((cur_price - last_price) / last_price, 5) * 100
    else:
        return 0


def cal_weighted(prices, weights):
    if len(prices) != len(weights):
        return 0
    w = 0
    for i in range(len(prices)):
        w += prices[i] * weights[i]
    return w


def get_timestamp():
    now = datetime.datetime.now()
    t = now.isoformat("T", "milliseconds")
    return t + "Z"


def send_email(message):
    # 第三方 SMTP 服务
    mail_host = "smtp.163.com"  # 设置服务器
    mail_user = "lilinchuan2"  # 用户名
    mail_pass = "l1992l0202c2112"  # 口令

    sender = 'lilinchuan2@163.com'
    receivers = ['475900302@qq.com']  # 接收邮件，可设置为你的QQ邮箱或者其他邮箱

    msg = MIMEText(message, 'plain', 'utf-8')
    msg['From'] = Header("MoneyMaker <%s>" % sender)
    msg['To'] = Header("管理员 <%s>" % receivers[0])
    msg['Subject'] = Header("币圈操作提示", 'utf-8')

    try:
        # smtplib.SMTP_SSL
        smtpObj = smtplib.SMTP_SSL(mail_host, 465)
        smtpObj.login(mail_user, mail_pass)
        smtpObj.sendmail(sender, receivers, msg.as_string())
        print("邮件发送成功")
    except smtplib.SMTPException as e:
        print("Error: 无法发送邮件:", e)


def calc_stf(deal_entity, last_price, last_last_price):
    if last_last_price != last_price != 0:
        price = deal_entity.price
        vol = deal_entity.amount
        if price == last_price:
            return vol * (price - last_last_price)
        else:
            return vol * (price - last_price)
    return 0


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


if __name__ == '__main__':
    print(string2timestamp(get_timestamp()))