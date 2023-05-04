from datetime import datetime
from datetime import time
from time import sleep


from vnpy.trader.constant import Direction
from vnpy.trader.object import TickData, OrderData, BarData

from future_data.trade_data import get_last_trade

from strategies.base_cta_strategy import BaseCtaStrategy


class DualThrustStrategyDz(BaseCtaStrategy):
    """添加止盈与场景拦截的dt策略"""

    author = "Dongzhi"

    fixed_size = 1
    k1 = 0.4
    k2 = 0.7

    bars = None

    day_open = 0
    day_high = []
    day_low = []
    day_close = []
    days = 3

    day_range = 0
    long_entry = 0
    short_entry = 0
    stop_revenue_percent = 1.0
    exit_time = ""  # time(hour=22, minute=50)
    use_close_price = False

    long_entered = False
    short_entered = False
    scenario = 0  # 0 不操作 1 触发多头开仓  2 空头开仓 3 平多 4 平空

    parameters = ["k1", "k2", "days", "need_stop", "trailing_percent", "stop_revenue_percent", "bar_window",
                  "deposit_rate", "percent", 'capital', 'size', 'exit_time', 'use_close_price']
    variables = ['capital', "scenario", "intraTradeHigh", "intraTradeLow"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.bars = []
        self.day_high = []
        self.day_low = []
        self.day_close = []
        self.long_entered = True
        self.short_entered = True
        self.exit_time = time(hour=22, minute=50)
        if "exit_time" in setting:
            hour = int(setting["exit_time"].split(":")[0])
            minute = int(setting["exit_time"].split(":")[1])
            self.exit_time = time(hour=hour, minute=minute)

    def on_start(self):
        """
        当策略被启动时调用该函数。
        """
        self.long_entered = False
        self.short_entered = False
        self.output("on_start self.scenario inited")
        # if self.pos == 0:
        #     pass
        if not self.back_testing:
            # 从数据库加载数据，判断今天是否已经开过仓
            # 单独查询的原因为如果早盘就已经平仓，仅通过pos无法判断今天是否开过仓
            long_trade = get_last_trade(self.strategy_name, self.vt_symbol, Direction.LONG.name)
            if long_trade is not None and long_trade.datetime.date() == datetime.now().date():
                self.output("self.long_entered = True")
                self.long_entered = True
            short_trade = get_last_trade(self.strategy_name, self.vt_symbol, Direction.SHORT.name)
            if short_trade is not None and short_trade.datetime.date() == datetime.now().date():
                self.output("self.short_entered = True")
                self.short_entered = True
        self.scenario = 0
        self.trading = True
        self.output("on_start self.scenario: %s" % self.scenario)
        self.output("on_start self.long_entered: %s" % self.long_entered)
        self.output("on_start self.short_entered: %s" % self.short_entered)
        super().on_start()

    def exit(self, now: time, exit_time: time):
        # 判断日内平仓时间，一般为收盘前10分钟
        night_end = time(hour=3, minute=0)
        if exit_time <= night_end:
            if exit_time <= now <= night_end:
                return True
        return now >= exit_time

    def on_order(self, order: OrderData):
        """
        通过该函数收到委托状态更新推送。
        """
        self.output("on order %s" % order)
        # 委托状态更新则立刻更新标记，避免交易所服务端因其他原因导致撤单而本地无法感知
        self.scenario = 0
        pass

    def on_bar(self, bar: BarData):
        self.output("on_bar : %s" % str(bar))
        # 更新K线到时间序列容器中
        self.bg.update_bar(bar)
        # 日内收盘前平仓
        if self.exit(bar.datetime.time(), self.exit_time):
            self.cancel_all()
            if self.pos != 0:
                if not self.back_testing:
                    # 取消后等待服务器响应
                    sleep(2)
            if self.pos > 0:
                self.sell(bar.close_price - 20, abs(self.pos))
            elif self.pos < 0:
                self.cover(bar.close_price + 20, abs(self.pos))

        self.put_event()
        pass

    def on_bar_m(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        # self.cancel_all()

        # 记录两条数据用于判断是否为新的一天
        # 收到新的数据即视为当日开盘价，此写法不适用于包含凌晨0点-2点的品种
        self.bars.append(bar)
        if len(self.bars) <= 2:
            return
        else:
            self.bars.pop(0)
        last_bar = self.bars[-2]

        self.output("dualthrust last_bar : %s" % last_bar)
        self.output("dualthrust bar : %s" % bar)
        if last_bar.datetime.date() != bar.datetime.date() or len(self.day_high) == 0:
            # 笔者曾经在无法获取准确开盘价的时期也尝试过使用前日收盘价
            if self.use_close_price:
                self.day_open = self.day_close[-1] if len(self.day_close) > 0 else last_bar.close_price
            else:
                self.day_open = bar.open_price
            # data of N days
            if len(self.day_high) >= self.days:
                # 计算N天的波动范围，以及多空开仓点
                self.day_range = max(max(self.day_high) - min(self.day_close),
                                     max(self.day_close) - min(self.day_low))
                self.long_entry = self.day_open + self.k1 * self.day_range
                self.short_entry = self.day_open - self.k2 * self.day_range
                self.output("init dualthrust date : %s" % bar.datetime.date())
                self.output("init dualthrust self.day_open : %s" % self.day_open)
                self.output("init dualthrust self.day_high : %s" % self.day_high)
                self.output("init dualthrust self.day_low : %s" % self.day_low)
                self.output("init dualthrust self.day_close : %s" % self.day_close)
                self.output("init dualthrust self.day_range : %s" % self.day_range)
                self.output("init dualthrust self.long_entry : %s" % self.long_entry)
                self.output("init dualthrust self.short_entry : %s" % self.short_entry)

            # 初始化本日数据
            self.day_high.append(bar.high_price)
            self.day_low.append(bar.low_price)
            self.day_close.append(bar.close_price)
            # 移除多余数据
            if len(self.day_high) > self.days:
                self.day_high = self.day_high[1:]
                self.day_low = self.day_low[1:]
                self.day_close = self.day_close[1:]
            if self.back_testing:
                # 重置是否开仓标记
                self.long_entered = False
                self.short_entered = False
            # 重置场景标记
            self.scenario = 0
        else:
            # 当日数据记录最高最低价和收盘价
            self.day_high[-1] = max(self.day_high[-1], bar.high_price)
            self.day_low[-1] = min(self.day_low[-1], bar.low_price)
            self.day_close[-1] = bar.close_price

        self.output("self.day_open : %s" % self.day_open)
        self.output("self.day_range : %s" % self.day_range)
        self.output("self.long_entry : %s, long_entered: %s" % (self.long_entry, self.long_entered))
        self.output("self.short_entry : %s, short_entered: %s" % (self.short_entry, self.short_entered))

        if self.exit(bar.datetime.time(), self.exit_time):
            return
        if not self.day_range:
            return

        # 根据总资金计算开仓手数
        self.fixed_size = super().calculate_volume(bar.close_price)
        # print("%s , %s" % (self.fixed_size, self.capital))

        """根据行情产生的变化，计算当前需要操作的场景，将等待开仓、持仓中、止盈、止损等场景分为不同场景编码
           当行情未发生巨大变化时，可认为无需额外操作，避免频繁撤单。
           当场景发生变化，则触发实际下单行情，撤回未成交指令，重新下单。
           场景数量编码无实际意义，只需要确保计算场景的部分与处理交易的部分保持分支数量一致即可。
        """
        if not self.exit(bar.datetime.time(), self.exit_time):
            # 每30分钟清除一下场景缓存，避免并发问题导致场景变更时未成功下单
            if bar.datetime.minute % 30 == 0:
                self.scenario = 0
            # 计算场景，减少撤单次数
            scenario_this_time = 0
            if self.pos == 0:
                if bar.close_price >= self.day_open:
                    if not self.long_entered:
                        scenario_this_time = 1
                else:
                    if not self.short_entered:
                        scenario_this_time = 2
            elif self.pos > 0:
                revenue_stop_price = self.long_entry + self.stop_revenue_percent * self.day_range
                if bar.close_price > revenue_stop_price:
                    scenario_this_time = 7
                elif bar.close_price > self.long_entry:
                    scenario_this_time = 3
                elif bar.close_price <= self.short_entry:
                    scenario_this_time = 9
                else:
                    scenario_this_time = 4
            elif self.pos < 0:
                revenue_stop_price = self.short_entry - self.stop_revenue_percent * self.day_range
                if bar.close_price < revenue_stop_price:
                    scenario_this_time = 8
                elif bar.close_price < self.short_entry:
                    scenario_this_time = 5
                elif bar.close_price >= self.long_entry:
                    scenario_this_time = 10
                else:
                    scenario_this_time = 6
            # 场景未发生变化，直接返回
            # # 移动止损
            # 由于dt本身有止损点位，先计算dt的点位与移动止损的点位，然后选择更优的价格来下单
            need_stop_for_now, stop_price = super().stop_order(bar, do_stop=False)
            if need_stop_for_now:
                self.cancel_all()
                if self.pos > 0:
                    stop_price = max(self.short_entry, stop_price)
                    self.sell(stop_price, self.pos, stop=True)
                    self.output("stop order sell on longStop:%s, high:%s" % (stop_price, self.intraTradeHigh))
                if self.pos < 0:
                    stop_price = min(self.long_entry, stop_price)
                    self.cover(stop_price, -self.pos, stop=True)
                    self.output("stop order cover on shortStop:%s, low:%s" % (stop_price, self.intraTradeLow))
            self.output("same scenario : %s" % scenario_this_time)
            # # 场景变化触发stop单更新
            if self.scenario != scenario_this_time:
                # self.cancel_all()
                # # 移动止损
                # super().stop_order(bar)
                # self.output("cancel_all self.scenario : %s" % scenario_this_time)
                self.scenario = scenario_this_time
            else:
                self.put_event()
                return

            # 执行原版DT逻辑
            self.cancel_all()
            if self.pos == 0:
                if bar.close_price >= self.day_open:
                    if not self.long_entered:
                        self.output("dualThrust buy : %s" % self.long_entry)
                        self.buy(self.long_entry, self.fixed_size, stop=True)
                else:
                    if not self.short_entered:
                        self.output("dualThrust short : %s" % self.short_entry)
                        self.short(self.short_entry,
                                   self.fixed_size, stop=True)

            elif self.pos > 0:
                self.long_entered = True
                self.output("dualThrust sell and short : %s" % self.short_entry)
                revenue_stop_price = self.long_entry + self.stop_revenue_percent * self.day_range
                if bar.close_price > revenue_stop_price:
                    # self.sell(self.long_entry * (1 + self.stop_revenue_percent / 100), abs(self.pos))
                    self.output("sell revenue_stop_price %s" % revenue_stop_price)
                    self.sell(revenue_stop_price, abs(self.pos))
                else:
                    stop_price = stop_price if stop_price is not None else self.short_entry
                    if bar.close_price <= self.short_entry:
                        self.output("sell now %s" % bar.close_price)
                        self.sell(bar.close_price - 20, abs(self.pos))
                    else:
                        self.output("sell use stop %s" % stop_price)
                        self.sell(stop_price, abs(self.pos), stop=True)

                if not self.short_entered:
                    self.output("short use stop %s" % self.short_entry)
                    self.short(self.short_entry, self.fixed_size, stop=True)

            elif self.pos < 0:
                self.short_entered = True
                self.output("dualThrust cover and buy : %s" % self.long_entry)
                revenue_stop_price = self.short_entry - self.stop_revenue_percent * self.day_range
                if bar.close_price < revenue_stop_price:
                    # self.cover(self.short_entry * (1 - self.stop_revenue_percent / 100), abs(self.pos))
                    self.output("cover revenue_stop_price %s" % revenue_stop_price)
                    self.cover(revenue_stop_price, abs(self.pos))
                else:
                    stop_price = stop_price if stop_price is not None else self.long_entry
                    if bar.close_price >= self.long_entry:
                        self.output("cover now %s" % bar.close_price)
                        self.cover(bar.close_price + 20, abs(self.pos))
                    else:
                        self.output("cover use stop %s" % stop_price)
                        self.cover(stop_price, abs(self.pos), stop=True)

                if not self.long_entered:
                    self.output("buy use stop %s" % self.long_entry)
                    self.buy(self.long_entry, self.fixed_size, stop=True)
            # super().stop_order(bar)

        self.put_event()


