from datetime import timedelta, datetime

import pandas as pd
from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager

DAY = "DAY"
HOUR = "HOUR"
MINUTE = "MINUTE"


class DayBarGenerator:
    # k线数组最大长度，超出长度后丢弃过期数据
    max_length = 60

    def __init__(self, max_length: int = 60, bar_length=1, length_unit=DAY):
        """初始化，设置用于计算的k线数量最大数量及k线长度和单位"""
        self.max_length = max_length
        self.bars: BarData = []
        self.am = ArrayManager(max_length)
        self.current_bar: BarData = None
        # 支持N分钟k线、小时线、日线
        self.bar_length = bar_length
        self.length_unit = length_unit
        # 缓存相关，由于日K线的统计数据在当天基本不变，故通过缓存提高回测速度
        self.cache = {}
        self.donchian_data = {}
        self.atr_data = {}
        self.boll_data = {}
        self.ma_data = {}
        self.wma_data = {}

    def is_same_bar(self, datetime1, datetime2):
        """判断是否属于同一根k线"""
        if self.length_unit == DAY:
            if datetime1.day != datetime2.day:
                return False
        if self.length_unit == HOUR:
            # if datetime1 + timedelta(hours=self.bar_length) < datetime2:
            if datetime1.hour != datetime2.hour:
                return False
        if self.length_unit == MINUTE:
            if datetime1 + timedelta(minutes=self.bar_length) < datetime2:
                return False
        return True

    def is_inited(self, length: int):
        """设置最小值，确保数据量低于length时不产生交易信号"""
        return len(self.bars) >= length

    def reset_cache(self):
        """k线更新时重置缓存"""
        self.cache = {}
        self.donchian_data = {}
        self.atr_data = {}
        self.boll_data = {}
        self.ma_data = {}
        self.wma_data = {}

    def update_bar(self, bar: BarData, init_function=None):
        """将新的k线更新到数据中"""
        if bar is None:
            return
        if self.current_bar is None:
            self.current_bar = bar
            return
        # 新bar不属于上一根k线，则将旧数据归档，新数据作为当前k线开始汇总
        if not self.is_same_bar(self.current_bar.datetime, bar.datetime):
            if init_function:
                init_function(self.current_bar)
            self.bars.append(self.current_bar)
            self.am.update_bar(self.current_bar)
            # 达到上限移除过期数据
            if len(self.bars) > self.max_length:
                self.bars.pop(0)
            self.current_bar = bar
            # 重置缓存
            self.reset_cache()
            return
        self.current_bar.high_price = max(self.current_bar.high_price, bar.high_price)
        self.current_bar.low_price = min(self.current_bar.low_price, bar.low_price)
        self.current_bar.volume += bar.volume
        if bar.datetime >= self.current_bar.datetime:
            self.current_bar.close_price = bar.close_price

    def get_last(self):
        """获取最后一根k线，主要用于获取最新收盘价等信息"""
        length = len(self.bars)
        if length < 1:
            return None
        return self.bars[length - 1]

    def donchian(self, window: int):
        """唐奇安通道"""
        if window is None or len(self.bars) < window:
            return None, None
        key = 'key_%s' % window
        if key in self.donchian_data:
            up, down = self.donchian_data[key]
            return up, down
        up, down = self.am.donchian(window)
        self.donchian_data[key] = up, down
        return up, down

    def atr(self, window: int):
        """真实波动率"""
        key = 'key_%s' % window
        if key in self.atr_data:
            atr_value = self.atr_data[key]
            return atr_value
        atr_value = self.am.atr(window)
        self.atr_data[key] = atr_value
        return atr_value

    def sma(self, window: int, array: bool = False):
        """简单移动平均"""
        key = 'key_%s' % window
        if not array:
            if key in self.ma_data:
                ma_value = self.ma_data[key]
                return ma_value
        ma_value = self.am.sma(window, array=array)
        if array:
            self.ma_data[key] = ma_value[-1]
        else:
            self.ma_data[key] = ma_value
        return ma_value

    def wma(self, window: int, array: bool = False):
        """加权移动平均"""
        key = 'key_%s' % window
        if not array:
            if key in self.wma_data:
                ma_value = self.wma_data[key]
                return ma_value
        ma_value = self.am.wma(window, array=array)
        if array:
            self.wma_data[key] = ma_value[-1]
        else:
            self.wma_data[key] = ma_value
        return ma_value

    def macd(self, fast_period: int,
             slow_period: int,
             signal_period: int,
             array: bool = False):
        """MACD"""
        macd_cache = "macd_cache"
        if not macd_cache in self.cache:
            self.cache[macd_cache] = {}
        key = 'key_%s_%s_%s' % (fast_period, slow_period, signal_period)
        if not array:
            if key in self.cache[macd_cache]:
                value = self.cache[macd_cache][key]
                return value
        macd, signal, hist = self.am.macd(fast_period, slow_period, signal_period, array=array)
        if array:
            self.cache[macd_cache][key] = macd[-1], signal[-1], hist[-1]
        else:
            self.cache[macd_cache][key] = macd, signal, hist
        return macd, signal, hist


if __name__ == '__main__':
    # 测试方法
    start = pd.to_datetime("20100101",
                           format='%Y%m%d %H:%M:%S.%f').tz_localize("Asia/Shanghai")
    print(start + timedelta(days=10))
    dbg = DayBarGenerator(1, length_unit=DAY)
    price = 1000.0
    for i in range(0, 1000):
        time = datetime.now()
        time = time + timedelta(hours=i)
        bar = BarData(
            symbol='rb9999',
            exchange=Exchange.SHFE,
            datetime=time,
            gateway_name='CTP',
            open_price=price + i,
            high_price=price + i + 1,
            low_price=price + i - 2,
            close_price=price + i - 1
        )
        dbg.update_bar(bar)
        # print(bar)

        print(len(dbg.bars))
        print(dbg.macd(12, 26, 9, array=True))
    print(dbg.bars)
