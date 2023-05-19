import json
from datetime import datetime
from typing import List, Dict

from vnpy_portfoliostrategy import StrategyTemplate, StrategyEngine, BacktestingEngine
from vnpy.trader.constant import Direction, Offset
from vnpy.trader.object import TickData, BarData, OrderData, TradeData
from vnpy.trader.utility import BarGenerator

from future_data.portfolio_global_config import vt_settings_with_short_code
from future_data.trade_data import TradeStatus, get_unclosed_trades, DbTradeData, update_db_trade_data, save_trade_data
from log.log_init import get_logger
from strategies.base_cta_strategy import GLOBAL_SETTINGS
from util.vt_symbol_util import split_vnpy_format


class BasePortfolioStrategy(StrategyTemplate):
    """投资组合策略模板"""

    author = "dongzhi"

    # 储存各合约的合约乘数，手续费，预估滑点等信息
    vt_settings = {}
    # 总资金
    capital = 1000000
    parameters = [
    ]
    variables = [
    ]

    def __init__(
            self,
            strategy_engine: StrategyEngine,
            strategy_name: str,
            vt_symbols: List[str],
            setting: dict
    ):
        """"""
        self.capital = 1000000
        # 框架初始化，读取配置文件
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        # 读取常用合约配置，此配置已移除月份编码，通过品种编码即可访问
        self.vt_settings = vt_settings_with_short_code
        # 是否回测环境
        self.back_testing = False
        if isinstance(strategy_engine, BacktestingEngine):
            self.back_testing = True
        logger_name = "backTesting" if self.back_testing else "main"
        self.logger = get_logger(logger_name)
        # 记录是否初始化完成(如加载历史数据)
        self.inited_internal = False
        # 业务相关数据
        self.bgs: Dict[str, BarGenerator] = {}
        self.last_tick_time: datetime = None
        self.last_trades = {}

        # 参考vnpy源码，需要为BarGenerator提供on_bar方法
        def on_bar(bar: BarData):
            """空实现，无需任何操作"""
            pass

        for vt_symbol in self.vt_symbols:
            self.bgs[vt_symbol] = BarGenerator(on_bar)
            self.last_trades[vt_symbol] = []
            if self.back_testing:
                self.capital = strategy_engine.capital

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.output("策略初始化")
        # print("策略初始化")
        if not self.back_testing:
            # for vt_symbol in self.vt_symbols:
            #     download_data_from_jq(vt_symbol.split('.')[0])
            self.load_bars(50)
        self.inited_internal = True
        print("初始化结束")

    def on_start(self):
        """
        Callback when strategy is started.
        """
        # print("策略启动")
        self.output("策略启动")

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.output("start save variables")
        self.sync_data()
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        # print("tick=%s,vt_symbol=%s" % (tick.datetime,tick.vt_symbol))
        new_minute = False
        if self.last_tick_time:
            if self.last_tick_time.minute < tick.datetime.minute \
                    or (self.last_tick_time.minute == 59 and tick.datetime.minute == 0):
                new_minute = True
                self.last_tick_time = tick.datetime
        else:
            self.last_tick_time = tick.datetime
        if new_minute:
            bars = {}
            for vt_symbol, bg in self.bgs.items():
                bars[vt_symbol] = bg.generate()
            self.on_bars(bars)

        bg: BarGenerator = self.bgs[tick.vt_symbol]
        bg.update_tick(tick)

    def on_bars(self, bars: Dict[str, BarData]):
        pass

    def update_order(self, order: OrderData) -> None:
        super().update_order(order)
        self.output("update_order success:--------------%s" % order)

    def update_trade(self, trade: TradeData) -> None:
        """
        Callback of new trade data update.
        """
        self.output("trade success:--------------%s" % trade)
        if trade.direction == Direction.LONG:
            self.pos[trade.vt_symbol] += trade.volume
        else:
            self.pos[trade.vt_symbol] -= trade.volume
        # 计算收益
        trade.closed_volume = 0
        self.calculate_revenue(trade)
        # 记录数据
        if not self.back_testing or GLOBAL_SETTINGS["BACK_TESTING_DATA_SAVE"]:
            # 生产使用时按本地时间存数据
            save_trade_data(self.strategy_name, self.capital, trade,
                            use_local_time=not self.back_testing)

    def calculate_revenue(self, trade: TradeData):
        # init data for trade
        trade.closed_volume = 0
        trade.status = TradeStatus.UN_CLOSED.value

        if trade.offset == Offset.NONE:
            return
        trades = self.last_trades[trade.vt_symbol]
        # load data from db if not back testing
        direction = Direction.SHORT if trade.direction == Direction.LONG else Direction.LONG
        if not self.back_testing or GLOBAL_SETTINGS["BACK_TESTING_DATA_SAVE"]:
            trades = get_unclosed_trades(self.strategy_name, trade.vt_symbol, direction.name)
        if trade.offset == Offset.OPEN:
            # open only need to save data into db or list
            trades.append(trade)
            return
        last_trades_of_direction = [v for v in trades if
                                    v.direction == direction or v.direction == direction.name]
        while len(last_trades_of_direction) > 0 and trade.closed_volume < trade.volume:
            last_trade = last_trades_of_direction[0]

            # volume can be deducted
            c_volume = min(last_trade.volume - last_trade.closed_volume, trade.volume - trade.closed_volume)
            last_trade.closed_volume += c_volume
            trade.closed_volume += c_volume
            if last_trade.volume <= last_trade.closed_volume:
                last_trade.status = TradeStatus.CLOSED.value
                last_trades_of_direction.remove(last_trade)
                trades.remove(last_trade)
            if isinstance(last_trade, DbTradeData):
                update_db_trade_data(last_trade)
            # 计算每张合约的损益
            # print("self.last_trade.tradeid %s" % self.last_trade.tradeid)
            # print("self.trade.tradeid %s" % trade.tradeid)
            direction = -1 if trade.direction == Direction.LONG else 1
            revenue_per_contract = direction * (trade.price - last_trade.price)
            self.output("%s , %s ,%s" % (last_trade.tradeid, trade.tradeid, revenue_per_contract))
            # 含手续费后的损益
            exchange, symbol, month = split_vnpy_format(trade.vt_symbol)
            revenue_per_contract_with_commission = revenue_per_contract - (
                    trade.price + last_trade.price) * self.vt_settings["rates"][symbol] * 2
            if self.back_testing:
                revenue_per_contract_with_commission -= self.vt_settings["slippages"][symbol] * 2
            revenue_per_volume = revenue_per_contract_with_commission * self.vt_settings["sizes"][symbol]
            volume = c_volume
            self.output(
                "last_order_id=%s,order_id=%s" % (last_trade.orderid, trade.orderid))
            self.output(
                "revenue_per_contract_with_commission=%s,volume=%s" % (
                    revenue_per_contract_with_commission, volume))
            total_revenue = revenue_per_volume * volume
            # print(
            #     'total_revenue=%s,trade.price=%s,last_trade.price=%s' % (
            #         total_revenue, trade.price, last_trade.price))
            msg = "datetime=%s,trade_vt_symbol=%s,self.capital=%s,revenue_percent=%s" % (
                trade.datetime, trade.vt_symbol, self.capital + total_revenue,
                round(total_revenue / self.capital * 100, 2))
            self.output(msg)
            self.output(self.pos)
            print(self.pos)
            print(msg)
            self.capital += total_revenue
            pass

    def output(self, msg: str, display=False):
        if self.inited_internal or display:
            self.logger.info("%s==== %s" % (self.strategy_name, msg))
