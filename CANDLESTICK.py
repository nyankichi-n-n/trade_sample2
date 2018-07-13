# coding=utf-8

import pprint

"""
このモジュールでは なんちゃってローソク足を実装しています。
指定された期間のローソク足を戻します。
"""


class CandleStick:
    """
    なんちゃってローソク足のクラスです。
    """
    
    def __init__(self, period=12, cs_period=40):
        """
        ローソク足クラスの初期化処理
        :param period: ローソク足を作る間隔数
        :param cs_period: ローソク足の期間
        """
        self.__count = 0
        self.__period = period
        self.__cs_period = cs_period
        self.__price = []
        self.__cs = []
        for var in range(0, self.__period):
            self.__price.append(0)
        for var in range(0, self.__cs_period):
            self.__cs.append({'open': 0,
                              'high': 0,
                              'low': 0,
                              'close': 0,
                              'avg': 0})

    def get(self):
        """
        ローソク足テーブルを戻す
        :return: ローソク足テーブル
        """
        return self.__cs

    def add(self, price):
        """
        仮想通貨のカレントプライスを追加し、ローソク足情報ができたらTrueを戻す
        :param price: カレントプライス
        :return: １ローソク足が作れたらTrue
        """

        self.__price[self.__count] = price
        self.__count += 1
        if self.__count < self.__period:
            return False
        else:
            self.__count = 0
            cs_open = self.__price[0]
            cs_high = max(self.__price)
            cs_low = min(self.__price)
            cs_close = self.__price[-1]
            cs_avg = int(sum(self.__price) / len(self.__price))

            for var in range(0, self.__cs_period - 1):
                self.__cs[var]['open'] = self.__cs[var + 1]['open']
                self.__cs[var]['high'] = self.__cs[var + 1]['high']
                self.__cs[var]['low'] = self.__cs[var + 1]['low']
                self.__cs[var]['close'] = self.__cs[var + 1]['close']
                self.__cs[var]['avg'] = self.__cs[var + 1]['avg']

            self.__cs[-1]['open'] = cs_open
            self.__cs[-1]['high'] = cs_high
            self.__cs[-1]['low'] = cs_low
            self.__cs[-1]['close'] = cs_close
            self.__cs[-1]['avg'] = cs_avg

            return True
