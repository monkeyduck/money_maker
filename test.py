# !/usr/bin/python
# -*- coding: UTF-8 -*-

try:
    import thread
except ImportError:
    import _thread as thread
from trade import  buyin_less_batch, buyin_more_batch, json, ensure_buyin_less, \
    ensure_buyin_more, okFuture, okSpot
import time
from run import sell_less_batch, sell_more_batch

import smtplib
from email.mime.text import MIMEText
from email.header import Header


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
        smtpObj = smtplib.SMTP()
        smtpObj.connect(mail_host, 25)  # 25 为 SMTP 端口号
        smtpObj.login(mail_user, mail_pass)
        smtpObj.sendmail(sender, receivers, msg.as_string())
        print("邮件发送成功")
    except smtplib.SMTPException as e:
        print("Error: 无法发送邮件:", e)


def get_hold_info():
    global flag
    i = 5
    while i > 0:
        ret = okFuture.future_userinfo_4fix()
        time.sleep(0.5)
        print(ret)
        i -= 1
    flag = 1


def query_24h_vol():
    avg_vol = float(okSpot.ticker("etc_usdt")['ticker']['vol']) / 24 / 60
    print('1min avg_vol: %.3f' % avg_vol)


def exe_finished():
    global finished
    finished = True


def sell():
    time.sleep(10)
    exe_finished()
    print("Finished thread")


if __name__ == '__main__':
    coin_name = "etc"
    time_type = "quarter"
    thread.start_new_thread(sell_less_batch, (coin_name, time_type, 10,))
    while True:
        print("start to sell")
        time.sleep(1)