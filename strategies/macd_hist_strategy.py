from vnpy.trader.object import (
    BarData,
)
import scipy.special
from vnpy_ctastrategy import CtaTemplate

from util.day_bar_generator import DayBarGenerator


class MacdHistStrategy(CtaTemplate):
    # 策略作者
    author = "Dongzhi"
    # 日志
    logger = None

    # 定义参数
    bar_window = 1  # k线间隔，单位：分钟
    fast_window = 22  # 短期均线长度
    mid_window = 44  # 短期均线长度
    slow_window = 80  # 长期均线长度

    # 定义变量
    fast_ma0 = 0.0
    fast_ma1 = 0.0
    mid_ma0 = 0.0
    mid_ma1 = 0.0
    slow_ma0 = 0.0
    slow_ma1 = 0.0

    need_stop = 1  # 0/1是否需要止损
    trailing_percent = 5.0  # 百分比移动止损，如2%止损
    last_stop_order_id = None

    # 移动止损
    intraTradeHigh = 0  # 持仓期内最高点
    intraTradeLow = float('inf')  # 持仓期内最低点
    longStop = 0  # 多头止损价格
    shortStop = 0  # 空头止损价格

    # 添加参数和变量名到对应的列表
    parameters = ["need_stop", "trailing_percent", "bar_window", "fast_window", "mid_window", "slow_window",
                  "deposit_rate", "percent", 'capital', 'size']
    variables = ["fast_ma0", "fast_ma1", "slow_ma0", "slow_ma1", "capital"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.dbg = DayBarGenerator(max_length=self.slow_window + 1)
        self.need_stop_for_now = False
        self.stop_price = None

    def on_init(self):
        self.load_bar(10)

    def output(self, msg):
        # print(msg)
        pass

    def on_bar(self, bar: BarData):

        # self.write_log("on_bar_m")
        self.output("on_bar_m : %s" % str(bar))
        """
        通过该函数收到新的1分钟K线推送。
        """
        # 更新K线到时间序列容器中
        self.dbg.update_bar(bar)

        # 若缓存的K线数量尚不够计算技术指标，则直接返回
        if not self.dbg.is_inited(self.slow_window):
            # print("not inited")
            return
        # 计算快速均线
        fast_ma = self.dbg.sma(self.fast_window, array=True)
        self.fast_ma0 = fast_ma[-1]  # T时刻数值
        self.fast_ma1 = fast_ma[-2]  # T-1时刻数值
        # 计算中速均线
        mid_ma = self.dbg.sma(self.mid_window, array=True)
        self.mid_ma0 = mid_ma[-1]  # T时刻数值
        self.mid_ma1 = mid_ma[-2]  # T-1时刻数值
        # 计算慢速均线
        slow_ma = self.dbg.sma(self.slow_window, array=True)
        self.slow_ma0 = slow_ma[-1]
        self.slow_ma1 = slow_ma[-2]
        # print("self.fast_ma0 : %s" % self.fast_ma0)
        self.output("self.fast_ma1 : %s" % self.fast_ma1)
        self.output("self.mid_ma0 : %s" % self.mid_ma0)
        self.output("self.mid_ma1 : %s" % self.mid_ma1)
        self.output("self.slow_ma0 : %s" % self.slow_ma0)
        self.output("self.slow_ma1 : %s" % self.slow_ma1)
        # 计算macd
        macd_macd, macd_signal, macd_hist = self.dbg.macd(12, 26, 9, array=True)
        macd_fast_ma0 = macd_macd[-1]
        macd_fast_ma1 = macd_macd[-2]

        macd_slow_ma0 = macd_signal[-1]
        macd_slow_ma1 = macd_signal[-2]

        # 判断是否金叉
        cross_1 = (self.fast_ma0 > self.mid_ma0)
        # 判断是否死叉
        cross_2 = (self.mid_ma0 > self.slow_ma0)

        # 判断是否金叉
        macd_cross_over = (macd_fast_ma0 > macd_slow_ma0)

        volume = 20

        macd_hist_trend = []
        macd_hist_trend_before = []
        new_trend_len = 2
        old_trend_len = 3
        for i in range(new_trend_len):
            macd_hist_trend.append(macd_hist[-1 - i] - macd_hist[-2 - i])
        for i in range(old_trend_len):
            macd_hist_trend_before.append(macd_hist[-1 - new_trend_len - i] - macd_hist[-2 - new_trend_len - i])
        trend_up = len([v for v in macd_hist_trend if v > 0]) == len(macd_hist_trend)
        trend_down = len([v for v in macd_hist_trend if v < 0]) == len(macd_hist_trend)
        trend_before_up = len([v for v in macd_hist_trend_before if v > 0]) == len(macd_hist_trend_before)
        trend_before_down = len([v for v in macd_hist_trend_before if v < 0]) == len(macd_hist_trend_before)

        # print(volume)
        pos_changed = False
        target_pos = 0
        if not cross_2 and macd_hist[-1] < 0 and trend_before_down and trend_up:
            target_pos = 1
            pos_changed = True
        if cross_2 and macd_hist[-1] > 0 and trend_before_up and trend_down:
            target_pos = -1
            pos_changed = True

        # if pos_changed:
        #     current_time = bar.datetime.time().hour
        #     if current_time < 9:
        #         current_time = 9
        #     day_open, day_close = 9, 15
        #     expit_signal = scipy.special.expit(current_time - day_open)
        #     target_pos *= expit_signal

        if self.pos * target_pos < 0:
            target_pos = 0

        # self.stop_order(bar)

        target_volumn = int(volume * target_pos)
        if self.pos * target_pos > 0 and abs(self.pos) >= abs(target_volumn):
            return
        # 如果发生了金叉
        change_volumn = target_volumn - self.pos
        # print("%s,%s,%s" % (target_pos, change_volumn, self.pos))
        if change_volumn == 0:
            return
        if not pos_changed:
            return
        self.cancel_all()
        if self.pos >= 0 and change_volumn > 0:
            # 为了保证成交，在K线收盘价上加5发出限价单
            price = bar.close_price + 10
            vt_order_ids = self.buy(price, change_volumn)
            self.output("buy vt_order_ids : %s" % str(vt_order_ids))
            # 当前持有空头仓位，则先平空，再开多
        elif self.pos < 0 and change_volumn > 0:
            price = bar.close_price + 10
            vt_order_ids = self.cover(price, change_volumn)
            self.output("cover: %s" % str(vt_order_ids))
        elif self.pos > 0 and change_volumn < 0:
            price = bar.close_price - 10
            self.sell(price, -change_volumn)
        elif self.pos <= 0 and change_volumn < 0:
            price = bar.close_price - 10
            self.short(price, -change_volumn)

        self.put_event()

    def stop_order(self, bar: BarData, need_cancel_all=False, do_stop=True, tailing_ratio=1.0):
        self.need_stop_for_now = False
        first_after_start = self.stop_price is None
        self.stop_price = None
        if self.pos == 0:
            self.intraTradeHigh = 0
            self.intraTradeLow = float('inf')
        if self.need_stop and self.pos != 0:
            # 移动止损策略
            if self.pos > 0:
                self.intraTradeLow = bar.low_price
                if bar.high_price > self.intraTradeHigh or first_after_start:
                    # 撤销原有所有单
                    if need_cancel_all:
                        self.cancel_all()
                    elif self.last_stop_order_id is not None:
                        for o_id in self.last_stop_order_id:
                            self.cancel_order(o_id)
                    self.intraTradeHigh = max(self.intraTradeHigh, bar.high_price)
                    # 计算止损价位
                    self.longStop = self.intraTradeHigh * (1 - tailing_ratio * self.trailing_percent / 100)
                    if do_stop:
                        self.output("stop order sell on longStop:%s, high:%s" % (self.longStop, self.intraTradeHigh))
                        self.last_stop_order_id = self.sell(self.longStop, self.pos, stop=True)
                    self.need_stop_for_now = True
                    self.stop_price = self.longStop
            elif self.pos < 0:
                self.intraTradeHigh = bar.high_price
                if bar.low_price < self.intraTradeLow or first_after_start:
                    # 撤销原有所有单
                    if need_cancel_all:
                        self.cancel_all()
                    elif self.last_stop_order_id is not None:
                        for o_id in self.last_stop_order_id:
                            self.cancel_order(o_id)
                    self.intraTradeLow = min(self.intraTradeLow, bar.low_price)
                    # 计算止损价位
                    self.shortStop = self.intraTradeLow * (1 + tailing_ratio * self.trailing_percent / 100)
                    if do_stop:
                        self.output("stop order cover on shortStop:%s, low:%s" % (self.shortStop, self.intraTradeLow))
                        self.last_stop_order_id = self.cover(self.shortStop, -self.pos, stop=True)
                    self.need_stop_for_now = True
                    self.stop_price = self.shortStop
        return self.need_stop_for_now, self.stop_price
