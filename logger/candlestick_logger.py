# coding=utf-8
"""
ローソク足ロガー

"""

import datetime
import codecs
import csv


class CandleStickLogger:
    """
    ローソク足ロガー
    """
    
    def __init__(self, file_path, coin_name='mona'):
        """
        Content:
          コンストラクタ
        Param:
          1. file_path:    ファイルパス
          2. coin_name:    コイン名
        """
        now = datetime.datetime.now()
        self.__file_path = file_path + now.strftime("%Y%m%d-%H%M%S") + ".csv"
        self.__message_title = True
        self.write(coin_asset=coin_name + '資産',
                   jpy_asset='JPY資産',
                   last_trade_price='最終トレード価格',
                   market_open='始値',
                   market_max='高値',
                   market_min='安値',
                   market_close='終値',
                   market_avg='平均',
                   msg='備考')
        self.__message_title = False
    
    def write(self,
              coin_asset=0,
              jpy_asset=0,
              last_trade_price=0,
              market_open=0,
              market_max=0,
              market_min=0,
              market_close=0,
              market_avg=0,
              msg=''):
        """
        Content:
          書き込みメソッド
        Param:
          1. coin_asset: コイン資産
          2. jpy_asset: JPY資産
          3. last_trade_price: 最終トレード価格
          4. market_open: 始値
          5. market_max: 高値
          6. market_min; 安値
          7. market_close: 終値
          8. market_avg: 平均
          9. msg: 備考
        """
        # ログファイル内容作成
        csvlist = []
        if self.__message_title:
            csvlist.append("日付")
            csvlist.append("日時")
        else:
            now = datetime.datetime.now()
            csvlist.append(now.strftime("%Y/%m/%d"))
            csvlist.append(now.strftime("%H:%M:%S"))
        csvlist.append(coin_asset)
        csvlist.append(jpy_asset)
        if last_trade_price == 0:
            csvlist.append('')
        else:
            csvlist.append(last_trade_price)
        if market_open == 0:
            csvlist.append('')
        else:
            csvlist.append(market_open)
        if market_max == 0:
            csvlist.append('')
        else:
            csvlist.append(market_max)
        if market_min == 0:
            csvlist.append('')
        else:
            csvlist.append(market_min)
        if market_close == 0:
            csvlist.append('')
        else:
            csvlist.append(market_close)
        if market_avg == 0:
            csvlist.append('')
        else:
            csvlist.append(market_avg)
        csvlist.append(msg)
        
        # ログファイルに書き込む
        with codecs.open(self.__file_path, "a", "utf-8-sig") as f:
            writer = csv.writer(f, lineterminator='\n')
            writer.writerow(csvlist)
        
        # 初期化
        coin_asset = 0
        jpy_asset = 0
        last_trade_price=0
        market_open = 0
        market_max = 0
        market_min = 0
        market_close = 0
        market_avg = 0
        msg = ''
