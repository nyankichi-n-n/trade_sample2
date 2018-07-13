# coding=utf-8

import codecs
import datetime
from decimal import (Decimal)
import json
import time
import urllib.error

import ccxt
import slackweb

import CANDLESTICK
import logger.candlestick_logger
import logger.error_logger
import logger.trade_logger
import MACD
import SMA_BB

# 本プログラムは、マルチ売買申請には対応していない。必ず1申請での処理となる。
# 実売買はしないが、売買ルーチンやオーダーチェックのルーチンは含まれています。
# 単純なチャネルブレイクアウトでの売買方式です。

with codecs.open('config/key.json', 'r', 'utf-8') as f:
    API_data = json.load(f)

WEBHOOK_URL = API_data["slack_webhook_url"]
slack_flag = 'hooks.slack.com' in WEBHOOK_URL
slack = slackweb.Slack(WEBHOOK_URL)

API_KEY = API_data["zaif_key"]
API_SECRET = API_data["zaif_secret"]
COIN_NAME = 'BTC'
COIN_PAIR = 'BTC/JPY'
EXCHANGE = 'zaif:'

exchange = ccxt.zaif()
exchange.apiKey = API_KEY
exchange.secret = API_SECRET

trade_log = logger.trade_logger.TradeLogger('zaif', COIN_NAME)
error_log = logger.error_logger.ErrorLogger('error')
candlestick_log = logger.candlestick_logger.CandleStickLogger("cs", COIN_NAME)

# 市場価格の取得間隔
loop_count = 0
LOOP_TIME = 5  # 市場価格取得間隔の秒数

# 何分足のローソク足かの定数
CANDLE_STICK_PERIOD = int(1 * 60 / LOOP_TIME)  # 何分足

# チャネルブレイクアウトの間隔定数
CANDLE_TERM = 15  # ローソク足の保持数(レンジ幅を確認する間隔)
BUY_TERM = 10  # 買いを判断する間隔
SELL_TERM = 5  # 売りを判断する間隔
RANGE_THRESHOLD = 500  # レンジ幅の定数

# 移動平均線、ボリンジャーバンドの間隔数
PERIOD1 = 12  # 短期移動平均線 12
PERIOD2 = 26  # 長期移動平均線＆ボリンジャーバンドの間隔数 ※ LOOP_CNT26と同じにする 104

# MACDの間隔数
LOOP_CNT9 = 9  # MACD9のための定数(15秒間隔なので36)
LOOP_CNT12 = 12  # EMA12のための定数(15秒間隔なので48)
LOOP_CNT26 = 26  # EMA26のための定数(15秒間隔なので104)

# デットクロス売りに移行したかのフラグ
dead_cross_flag = False

# キャンセル処理への変数
CANCEL_LOOP_MAX = 12  # キャンセルするまでのループ回数　4x15=60秒
cancel_flag = False  # 約定してない売買申請がある場合にキャンセル処理を動かすフラグ
cancel_loop_count = 0  # キャンセルまでのカウント

# 売買後にホールドする回数の変数
trade_rising_flag = False  # 上昇傾向で保留したかのフラグ

# 売買取引量、板情報に表示されてる売買量(情報収集)
bid_amount = 0.0  # 買い取引量
ask_amount = 0.0  # 売り取引量
bid_depth_amount = 0.0  # 板買い
ask_depth_amount = 0.0  # 板売り

# アセット
funds_jpy = 0  # 注文余力日本円
funds_coin = 0.0  # 注文余力コイン
start_funds_jpy = 0  # プログラム開始時の日本円
asset_info = False

# 最後のトレード情報
last_trade_func = ''  # 取引機能
last_trade_order_id = 0  # 最後に取引したID
last_trade_size = 0.0  # 最後に取引したサイズ
last_trade_price = 0  # 最後に取引した価格
last_trade_price_pre = 0  # 一つ前の取引した価格(キャンセルした時用)
last_trade_type = 0  # 0:購入、1:利確1、2:利確2、3:損切り

# トレードログ用
message_flag = False
message_func = ''
message_trade = ''
message_size = 0
message_price = 0.0
date_time = datetime.datetime.now()  # print用表示タイム

# 現在の市場価格情報
current_price = 0  # 市場価格
current_bid_price = 0  # 買い気配
current_ask_price = 0  # 売り気配
current_price_pre = 0  # 前の市場価格
current_bid_price_pre = 0  # 前の買い気配
current_ask_price_pre = 0  # 前の売り気配
current_rising = False  # ローソク足で上昇傾向か？
current_buy = False  # ローソク足で買いシグナル

# プログラムの終了処理変数
END_FLAG = False  # プログラムの終了フラグ
end_datetime = datetime.datetime.now()  # 終了タイム
END_HOUR = 16  # 終了時
END_MINUTE = 30  # 終了分

#####################################
# テスト用                          #
user_coin_asset = 0.0  # 実売買しないのでテスト用コイン資産
user_jpy_asset = 20000.0  # 実売買しないのでテスト用日本円資産
#                                   #
#####################################


def order_limit_call(side, coin_amount, price):
    """
    仮想通貨指値注文
    繰り返しは5回までとしている。
    :param side: 'buy','sell'
    :param coin_amount: コイン数
    :param price: 価格
    :return: APIが正常応答したかのフラグ、オーダーID
    """
    global exchange, COIN_PAIR, error_log

    coin_float_amount = float(coin_amount)
    for _a in range(5):
        try:
            if side == 'buy':
                ccxt_result = exchange.create_limit_buy_order(COIN_PAIR, coin_float_amount, price)
            elif side == 'sell':
                ccxt_result = exchange.create_limit_sell_order(COIN_PAIR, coin_float_amount, price)
            else:
                return False, 0
        except ccxt.RequestTimeout:
            error_log.write()
            print('エラー: call ', side, ' order timeout')
            time.sleep(1)
        except ccxt.ExchangeNotAvailable:
            error_log.write()
            print('エラー: call ', side, ' order NotAvailable')
            time.sleep(1)
        except ccxt.ExchangeError:
            error_log.write()
            print('エラー: call ', side, ' order ExchangeError')
            time.sleep(1)
        else:
            return True, ccxt_result['id']

        # エラーでも申請が通っている場合があるのでチェック(タイムアウトしてた時に一度発生した)
        # 複数申請は無いプログラムでのチェック内容。
        check_flag, check_id, check_status = order_check()
        if check_flag and check_id != 0:
            return True, check_id
        for _b in range(5):
            try:
                ccxt_result = exchange.fetch_balance()
            except ccxt.RequestTimeout:
                error_log.write()
                print('エラー:balance Timeout')
                time.sleep(1)
            except ccxt.ExchangeNotAvailable:
                error_log.write()
                print('エラー:balance NotAvailable')
                time.sleep(1)
            except ccxt.ExchangeError:
                error_log.write()
                print('エラー:balance ExchangeError')
                time.sleep(1)
            else:
                if side == 'buy':
                    if ccxt_result['BTC']['total'] != 0:
                        return True, 0
                else:
                    if ccxt_result['BTC']['total'] == 0:
                        return True, 0
        else:
            print('order_limit_call balance リトライ5回失敗')
            return False, 0
    else:
        print('order_limit_call リトライ5回失敗')
        return False, 0


def order_check():
    """
    有効なオーダーがあるか確認
    :return: APIが正常応答したかのフラグ、オーダーID、オーダーステータス
    """
    global exchange, COIN_PAIR, error_log

    for _c in range(10):
        try:
            ccxt_result = exchange.fetch_open_orders(COIN_PAIR)
        except ccxt.RequestTimeout:
            error_log.write()
            print('エラー:cant open orders Timeout')
            time.sleep(1)
        except ccxt.ExchangeNotAvailable:
            error_log.write()
            print('エラー:cant open orders NotAvailable')
            time.sleep(1)
        except ccxt.ExchangeError:
            error_log.write()
            print('エラー:cant open orders ExchangeError')
            time.sleep(1)
        else:
            if len(ccxt_result) == 0:
                return True, 0, 0
            else:
                return True, ccxt_result[0]['id'], ccxt_result[0]['status']
    else:
        print('order_check リトライ10回失敗')
        return False, 0, 0


def slack_notify(message):
    """
    Slackへの通知
    :param message: 通知メッセージ
    """
    global slack_flag, slack, error_log

    if slack_flag:
        for _d in range(5):
            try:
                slack.notify(text=message)
            except urllib.error.HTTPError:
                error_log.write()
                print("エラー:slack call HTTPError")
            except urllib.error.URLError:
                error_log.write()
                print("エラー:slack call URLError")
            else:
                break
        else:
            print('slack call error')


def channel_break(price, candle_data):
    if candle_data[0]['open'] == 0:
        return {'side': None, 'price': 0}
    highest = max(i['high'] for i in candle_data[-1 * BUY_TERM:])
    if price > highest:
        return {'side': 'BUY', 'price': highest}
    lowest = min(i['low'] for i in candle_data[-1 * SELL_TERM:])
    if price < lowest:
        return {'side': 'SELL', 'price': lowest}
    return {'side': None, 'price': 0}


def is_range(candle_data, th):
    low = min([min(i['open'], i['close']) for i in candle_data])
    high = max([max(i['open'], i['close']) for i in candle_data])
    if (high - low) > th:
        return True
    else:
        return False


if __name__ == '__main__':

    sma_bb = SMA_BB.SimpleMovingAverageBollingerBand(PERIOD1, PERIOD2)
    macd = MACD.MovingAverageConvergenceDivergence(LOOP_CNT9, LOOP_CNT12, LOOP_CNT26)
    candle_stick = CANDLESTICK.CandleStick(CANDLE_STICK_PERIOD, CANDLE_TERM)

    sma_flag = True
    sma_avg1 = 0
    sma_avg2 = 0
    sma_sigma = 0
    sma_avg1_pre = 0
    sma_avg2_pre = 0
    sma_sigma_pre = 0
    macd_flag = True
    macd_macd = 0
    macd_signal = 0
    macd_macd_pre = 0
    macd_signal_pre = 0
    channel_break_result = {'side': None, 'price': 0}
    order_flag = True
    order_id = 0
    order_status = 0

    init_flag = False
    while not init_flag:
        try:
            last_trade_price = int(exchange.fetch_ticker(COIN_PAIR)['last'])
            # result = exchange.fetch_balance()
            # start_funds_jpy = result['total']['JPY']
            # if result['total'][COIN_NAME] != 0:
            #     start_funds_jpy += result['total'][COIN_NAME] * last_trade_price
            # print('start jpy:', start_funds_jpy)

            #####################################
            # テスト用                          #
            start_funds_jpy = user_jpy_asset
            #                                   #
            #####################################

        except (ccxt.RequestTimeout, ccxt.ExchangeNotAvailable, ccxt.ExchangeError):
            error_log.write()
            continue
        else:
            init_flag = True

    # 終了タイムを設定
    date_time = datetime.datetime.now()
    end_datetime = datetime.datetime(date_time.year, date_time.month, date_time.day, END_HOUR, END_MINUTE)
    END_FLAG = False
    if date_time > end_datetime:
        end_datetime += datetime.timedelta(days=1)
    print('END DATE TIME:', end_datetime)

    profit_count = 0
    loss_count = 0

    while True:
        message_flag = False
        message_func = ''
        message_trade = ''
        message_price = 0
        message_size = 0.0
        date_time = datetime.datetime.now()
        start_time = time.time()
        try:
            # result = exchange.fetch_balance()
            # funds_jpy = result['total']['JPY']
            # funds_coin = Decimal(result['total'][COIN_NAME]).quantize(Decimal('0.001'))
            #####################################
            # テスト用                          #
            funds_coin = user_coin_asset
            funds_jpy = user_jpy_asset
            #                                   #
            #####################################

            result = exchange.fetch_ticker(COIN_PAIR)
            current_price_pre = current_price
            current_bid_price_pre = current_bid_price
            current_ask_price_pre = current_ask_price
            current_price = int(result['last'])
            # current_price = (int(result['bid']) + int(result['ask'])) // 2
            current_bid_price = int(result['bid'])
            current_ask_price = int(result['ask'])

        except ccxt.RequestTimeout:
            error_log.write()
            print("エラー:Cant get data Timeout")
            time.sleep(1)
            continue

        except ccxt.ExchangeNotAvailable:
            error_log.write()
            print("エラー:Cant get data NotAvailable")
            time.sleep(1)
            continue

        except ccxt.ExchangeError:
            error_log.write()
            print("エラー:Cant get data Error")
            time.sleep(1)
            continue

        else:
            loop_count += 1
            candle_stick_data = candle_stick.get()
            channel_break_result = channel_break(current_price, candle_stick_data)

        if message_flag:
            print('■資産、ローソク足', loop_count)
            print(str(date_time))
            print(COIN_NAME + '資産:', str(funds_coin))
            print('jpy資産:', str(funds_jpy))
            print('始値:', candle_stick_data[-1]['open'], '高値:', candle_stick_data[-1]['high'],
                  '安値:', candle_stick_data[-1]['low'], '終値:', candle_stick_data[-1]['close'])
            print("最終取引価格:" + str(last_trade_price))
            message_func = EXCHANGE + '資産、ローソク足'
        else:
            print("■ 現在の情報です", loop_count)
            print(str(date_time))
            print("市場取引価格:" + str(current_price))
            print(COIN_NAME + "資産:" + str(funds_coin))
            print("jpy資産:" + str(funds_jpy))
            print("最終取引価格:" + str(last_trade_price))

        if asset_info or loop_count == 1:
            if funds_coin < 0.001 and last_trade_order_id == 0:
                message_text = EXCHANGE + '現在の資産: ' + str(date_time) + '\njpy資産:' \
                               + str(funds_jpy) + '\n' + COIN_NAME + '資産:' + str(funds_coin) \
                               + '\nProfit:' + str(profit_count) + ' Loss:' + str(loss_count) \
                               + '\nGain:' + str(funds_jpy - start_funds_jpy)
            else:
                message_text = EXCHANGE + '現在の資産: ' + str(date_time) + '\njpy資産:' \
                               + str(funds_jpy) + '\n' + COIN_NAME + '資産:' + str(funds_coin) \
                               + '\nProfit:' + str(profit_count) + ' Loss:' + str(loss_count)
            print(message_text)
            slack_notify(message_text)
            asset_info = False

        # コインを持っていて、チャネルブレイクアウト売り
        if funds_coin >= 0.001 and channel_break_result['side'] == 'SELL':

            # if last_trade_price < current_bid_price:

            amount = funds_coin
            # 売り
            # order_flag, order_id = order_limit_call('sell', amount, current_price)
            #####################################
            # テスト用                          #
            time.sleep(1)
            user_coin_asset -= float(amount)
            user_jpy_asset += (current_price * float(amount))
            order_flag = True
            order_id = 0
            #                                   #
            #####################################

            if order_flag:
                message_flag = True
                last_trade_func = 'ask'
                last_trade_size = amount
                last_trade_price_pre = last_trade_price
                last_trade_price = current_price
                last_trade_order_id = order_id
                asset_info = True
                dead_cross_flag = True
                if last_trade_price_pre < last_trade_price:
                    profit_count += 1
                    last_trade_type = 2
                else:
                    loss_count += 1
                    last_trade_type = 3

                message_func += 'チャネルブレイクアウト売り'
                if order_id == 0:
                    message_func += '、約定'
                    trade_rising_flag = False
                else:
                    cancel_flag = True
                    cancel_loop_count = 0
                message_trade = 'ask'
                message_price = current_price
                message_size = amount
                message_text = message_func + ': ' + str(date_time) + '\nPrice:'
                message_text += str(current_price) + '\nSize:' + str(amount)
                print(message_text)
                slack_notify(message_text)

        # コインを最小単位持っていない場合でチャネルブレイクアウト買い
        elif funds_coin < 0.001 and last_trade_order_id == 0 \
                and channel_break_result['side'] == 'BUY'\
                and is_range(candle_stick_data, RANGE_THRESHOLD) \
                and sma_avg1 > sma_avg1_pre:
            amount = Decimal(funds_jpy * 0.9 / current_price).quantize(Decimal('0.001'))

            # 買い
            # order_flag, order_id = order_limit_call('buy', amount, current_price)
            #####################################
            # テスト用                          #
            time.sleep(1)
            user_coin_asset += float(amount)
            user_jpy_asset -= (current_price * float(amount))
            order_flag = True
            order_id = 0
            #                                   #
            #####################################

            if order_flag:
                message_flag = True
                last_trade_func = 'bid'
                last_trade_size = amount
                last_trade_price_pre = last_trade_price
                last_trade_price = current_price
                last_trade_order_id = order_id
                last_trade_type = 0
                dead_cross_flag = False
                asset_info = True

                message_func += '購入'
                if order_id == 0:
                    message_func += '、約定'
                    trade_rising_flag = False
                else:
                    cancel_flag = True
                    cancel_loop_count = 0
                message_trade = 'bid'
                message_price = current_price
                message_size = amount

                message_text = message_func + ': ' + str(date_time)
                message_text += '\nPrice:' + str(current_price) + '\nSize:' + str(amount)
                print(message_text)
                slack_notify(message_text)

        if cancel_flag and cancel_loop_count > CANCEL_LOOP_MAX:
            order_flag, order_id, order_status = order_check()
            if order_flag:
                if order_id == 0:
                    message_func += '、約定'
                    message_text = message_func
                    print(message_text)
                    slack_notify(message_text)
                    asset_info = True
                    last_trade_order_id = 0
                    cancel_flag = False
                    trade_rising_flag = False
                else:
                    try:
                        print(exchange.cancel_order(order_id, COIN_PAIR))
                    except (ccxt.RequestTimeout, ccxt.ExchangeNotAvailable, ccxt.ExchangeError):
                        error_log.write()
                        print("エラー:cant trade[info/cancel]")
                    else:
                        message_flag = True
                        last_trade_price = last_trade_price_pre
                        message_func += '、キャンセル'
                        message_text = EXCHANGE + '■ キャンセルしました'
                        print(message_text)
                        slack_notify(message_text)
                        asset_info = True
                        if last_trade_type == 1 or last_trade_type == 2:
                            profit_count -= 1
                        elif last_trade_type == 3:
                            loss_count -= 1
                        last_trade_type = 0
                        last_trade_order_id = 0
                        cancel_flag = False
                        trade_rising_flag = False

        sma_flag = False
        macd_flag = False
        cs_flag = candle_stick.add(current_price)
        if cs_flag:
            candle_stick_data = candle_stick.get()
            sma_flag, sma_avg1, sma_avg2, sma_sigma, sma_avg1_pre, sma_avg2_pre, sma_sigma_pre \
                = sma_bb.add(candle_stick_data[-1]['avg'])
            macd_flag, macd_macd, macd_signal, macd_macd_pre, macd_signal_pre \
                = macd.add(candle_stick_data[-1]['avg'])
            if sma_flag:
                message_flag = True

        if message_flag:
            trade_log.write(
                func=message_func,
                coin_asset=funds_coin,
                jpy_asset=funds_jpy,
                market_price=current_price,
                market_bid_price=current_bid_price,
                market_ask_price=current_ask_price,
                order_id=last_trade_order_id,
                trade=message_trade,
                last_trade_price=last_trade_price,
                price=message_price,
                size=message_size,
                mean_line1=sma_avg1,
                mean_line2=sma_avg2,
                bid_amount=bid_amount,
                ask_amount=ask_amount,
                bid_depth_amount=bid_depth_amount,
                ask_depth_amount=ask_depth_amount,
                sigma2=sma_sigma,
                macd=macd_macd,
                signal=macd_signal)

        if cs_flag:
            candlestick_log.write(
                coin_asset=funds_coin,
                jpy_asset=funds_jpy,
                last_trade_price=last_trade_price,
                market_open=candle_stick_data[-1]['open'],
                market_max=candle_stick_data[-1]['high'],
                market_min=candle_stick_data[-1]['low'],
                market_close=candle_stick_data[-1]['close'],
                market_avg=candle_stick_data[-1]['avg'],
                msg='')

        cancel_loop_count += 1

        if funds_coin < 0.001 and END_FLAG and last_trade_order_id == 0:
            message_text = EXCHANGE + 'プログラム終了\n' + str(date_time) + '\njpy資産:'
            message_text += str(funds_jpy) + '\n' + COIN_NAME + '資産:' + str(funds_coin)
            message_text += '\nProfit:' + str(profit_count) + ' Loss:' + str(loss_count)
            message_text += '\nGain:' + str(funds_jpy - start_funds_jpy)
            print(message_text)
            slack_notify(message_text)
            exit()

        if date_time > end_datetime:
            END_FLAG = True

        end_time = time.time()
        elpsed_time = end_time - start_time
        if elpsed_time > LOOP_TIME:
            elpsed_time %= LOOP_TIME
            print('ake time over', str(LOOP_TIME), 'sec')

        time.sleep(LOOP_TIME - elpsed_time)
