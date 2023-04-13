from datetime import datetime

from vnpy.trader.object import (
    TickData,
    BarData,
    TradeData,
    OrderData,
)
from vnpy.trader.utility import BarGenerator, ArrayManager
from vnpy_ctastrategy import CtaTemplate, StopOrder
from vnpy_ctastrategy.backtesting import BacktestingEngine
from vnpy.trader.object import AccountData


class BaseCtaStrategy(CtaTemplate):
    """通用CTA模板"""

    # 策略作者
    author = "Dongzhi"
    # 日志
    logger = None

    # 定义参数
    bar_window = 1  # k线周期
    need_stop = 1  # 0/1是否需要止损
    trailing_percent = 5.0  # 百分比移动止损
    last_stop_order_id = None

    # 移动止损
    intraTradeHigh = 0  # 持仓期内最高点
    intraTradeLow = float('inf')  # 持仓期内最低点
    longStop = 0  # 多头止损价格
    shortStop = 0  # 空头止损价格

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        # 调用父类初始化方法，确保setting被正确注入
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        # 参数打印
        print("%s, %s : %s" % (datetime.now(),strategy_name, str(setting)))
        # K线合成器：从Tick合成分钟K线用
        # on_bar_m函数用于提供m分钟级别k线回调，默认推荐self.bar_window=1即可
        self.bg = BarGenerator(self.on_bar,
                               window=self.bar_window,
                               on_window_bar=self.on_bar_m)
        # 时间序列容器：计算技术指标用
        self.am = ArrayManager()
        self.need_stop_for_now = False
        self.stop_price = None
        # 回测时自动获取总资金
        self.back_testing = False
        if isinstance(cta_engine, BacktestingEngine):
            self.back_testing = True
        if self.back_testing:
            self.capital = cta_engine.capital

    def on_init(self):
        """
        当策略被初始化时调用该函数。
        """
        # 加载历史数据用于初始化回放
        self.load_bar(100, use_database=True)
        self.output("策略初始化")

    def on_start(self):
        """
        当策略被启动时调用该函数。
        """
        self.output("策略启动, capital: %s, need_stop:%s" % (self.capital, self.need_stop))
        # 通知图形界面更新（策略最新状态）
        # 不调用该函数则界面不会变化
        self.put_event()

    def on_stop(self):
        """
        当策略被停止时调用该函数。
        """
        self.write_log("策略停止")
        self.output("策略停止")
        self.put_event()

    def on_tick(self, tick: TickData):
        """
        通过该函数收到Tick推送。
        """
        self.bg.update_tick(tick)
        self.put_event()

    def on_bar(self, bar: BarData):
        self.output("on_bar : %s" % str(bar))
        self.output("pos : %s" % self.pos)
        # 更新K线到时间序列容器中
        self.bg.update_bar(bar)
        self.put_event()
        pass

    def stop_order(self, bar: BarData, need_cancel_all=False, do_stop=True, tailing_ratio=1.0):
        """
        :param bar: 当前分钟k线
        :param need_cancel_all: 是否在执行止损前调用cancel_all方法
        :param do_stop: 是否立刻执行止损，在部分场景中，止损价格可能与策略反手价格不一致，可将结果返回，交由策略自身择优选择止损点位
        :param tailing_ratio: 价格波动调整系数，用于策略自身根据需要动态调整止损百分比
        :return: 1.是否已到止损点位 2.止损执行价格
        """
        self.need_stop_for_now = False
        # 是否策略初次启动，用于立刻初始化止损价格
        first_after_start = self.stop_price is None
        self.stop_price = None
        # 持仓为0，重置行情最高点和最低点
        if self.pos == 0:
            self.intraTradeHigh = 0
            self.intraTradeLow = float('inf')
        if self.need_stop and self.pos != 0:
            # 移动止损策略
            if self.pos > 0:
                # 多单持仓时，动态记录最低价，便于反手时使用最新价格开始统计
                self.intraTradeLow = bar.low_price
                # 最高价突破，同步移动止损点位
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
                    # 挂条件单，确保止损价触发时尽快成交
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

    def on_bar_m(self, bar: BarData):
        """策略逻辑实现，子类重写这个方法即可 """
        pass

    def on_order(self, order: OrderData):
        """
        通过该函数收到委托状态更新推送。
        """
        self.output("on order %s" % order)
        # print(order)
        pass

    def on_trade(self, trade: TradeData):
        """
        通过该函数收到成交推送。
        """
        self.output("new trade success: %s" % trade)
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        通过该函数收到本地停止单推送。
        """
        self.put_event()
        pass

    def on_account(self, account: AccountData):
        self.output("account : %s" % str(account))
        self.put_event()
        pass

    def output(self, msg: str, display=False):
        # self.logger.info("%s==== %s" % (self.strategy_name, msg))
        # print(msg)
        pass
