import copy
import json
from time import sleep
from datetime import datetime, time
from datetime import timedelta
from typing import List, Dict, Tuple

from vnpy_portfoliostrategy import StrategyEngine
from vnpy.trader.constant import Direction, Offset
from vnpy.trader.object import BarData


from strategies.base_portfolio_strategy import BasePortfolioStrategy
from util.day_bar_generator import DayBarGenerator
from util.vt_symbol_util import split_vnpy_format, concat_vnpy_format


class MainContractPortfolioStrategy(BasePortfolioStrategy):
    """"""

    author = "dongzhi"

    history_contract_default_code = "9999"

    # 记录每个合约占用的保证金，防止开仓金额不足
    vt_used_capital = {}
    # 最大资金使用率
    max_use_percent = 80

    # 移动止损相关
    need_stop = True
    trailing_percent = 5

    parameters = ["need_stop", "trailing_percent",
                  'capital']
    variables = [
        'capital', 'vt_used_capital',
    ]

    def __init__(
            self,
            strategy_engine: StrategyEngine,
            strategy_name: str,
            vt_symbols: List[str],
            setting: dict
    ):
        """"""
        # 生成日线的工具
        # 日线记录,key为品种编号，不含月份，格式为{ 'rb':bg, 'FG':bg }
        # 便于历史数据读取主力合约，下单使用当前合约
        # 即便于换月和计算长期趋势数据
        self.day_bgs = {}
        # 记录每个合约占用的保证金，防止开仓金额不足
        self.vt_used_capital = {}
        # 记录止损价格
        self.vt_stop_price = {}
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)

        for vt_symbol in self.vt_symbols:
            exchange, symbol, month = split_vnpy_format(vt_symbol)
            self.day_bgs[symbol] = DayBarGenerator(200)
            if symbol not in self.vt_used_capital:
                self.vt_used_capital[symbol] = 0
        # 记录已换月的旧合约编码，便于自动换月,格式{old:new}
        self.outdated_contracts = {}
        self.init_outdated_contract()
        # 记录止损价
        self.stop_price = {}
        self.intraTradeHigh = {}
        self.intraTradeLow = {}
        self.need_cancel_all = True

    def init_outdated_contract(self):
        symbol_month_map = {}
        symbol_exchange_map = {}
        for vt_symbol in self.vt_symbols:
            exchange, symbol, month = split_vnpy_format(vt_symbol)
            print("init_outdated_contract, exchange, symbol, month =%s , %s , %s , vt_symbol = %s" % (
              exchange, symbol, month, vt_symbol))
            if month == MainContractPortfolioStrategy.history_contract_default_code:
                continue
            if symbol not in symbol_month_map:
                symbol_month_map[symbol] = set()
            new_month = int(month)
            symbol_month_map[symbol].add(new_month)
            symbol_exchange_map[symbol] = exchange
        for symbol in symbol_month_map:
            month_set = symbol_month_map[symbol]
            newest_month = max(month_set)
            month_set.remove(newest_month)
            for old_month in month_set:
                self.outdated_contracts[concat_vnpy_format(symbol_exchange_map[symbol], symbol, old_month)] = \
                    concat_vnpy_format(exchange, symbol, newest_month)
            print("init_outdated_contract, outdated_contracts = %s" % self.outdated_contracts)

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        try:
            self.output("策略初始化")
            if not self.back_testing:
                # 将合约转换为主力连续，方便计算长期趋势等数据
                symbols = set()
                for vt_symbol in self.vt_symbols:
                    exchange, symbol, month = split_vnpy_format(vt_symbol)
                    symbols.add(vt_symbol)
                    # 添加主力连续
                    symbols.add(concat_vnpy_format(exchange, symbol,
                                                   MainContractPortfolioStrategy.history_contract_default_code))
                # 调用定制后的load_bars
                self.load_bars(100, inparam_vt_symbols=symbols)
            self.inited_internal = True
        except Exception as e:
            self.logger.error(e, stack_info=True, exc_info=True)
            pass

    def on_bars(self, bars: Dict[str, BarData]):
        # 拷贝，避免直接修改bars对象
        # 否则会对vnpy内部使用产生影响
        bars = copy.deepcopy(bars)
        self.output(bars)
        self.need_cancel_all = True
        self.output("init self.need_cancel_all=%s" % self.need_cancel_all)
        for vt_symbol in self.outdated_contracts:

            exchange, symbol, month = split_vnpy_format(vt_symbol)
            if vt_symbol not in bars:
                continue
            bar = bars[vt_symbol]
            # 过滤旧合约数据
            bars[vt_symbol] = None
            if bar is None:
                continue
            pos = self.get_pos(vt_symbol)
            # 重置误差数据
            if symbol not in self.vt_used_capital:
                self.vt_used_capital[symbol] = 0
            # 换月
            main_contract_vt_symbol = self.outdated_contracts[vt_symbol]
            if self.trading and pos != 0 and self.bgs[main_contract_vt_symbol].last_tick \
                    and self.bgs[main_contract_vt_symbol].last_tick.last_price > 0:
                self.output("start change to main contract")
                # 当前处理换月，且忽略掉主力合约,避免主力为更新pos前重复操作
                bars.pop(main_contract_vt_symbol)
                # 平仓
                self.take_order_of_size(vt_symbol, abs(pos), bar.close_price,
                                        Direction.LONG if pos < 0 else Direction.SHORT, Offset.CLOSE)
                self.vt_used_capital[symbol] = 0
                self.output("take_order_of_size, %s" % vt_symbol)
                # 开仓
                # get last price of main_contract
                main_contract_price = self.bgs[main_contract_vt_symbol].last_tick.last_price
                self.take_order_of_size(main_contract_vt_symbol, abs(pos), main_contract_price,
                                        Direction.LONG if pos > 0 else Direction.SHORT, Offset.OPEN)
                self.output("take_order_of_size, %s" % main_contract_vt_symbol)
        # 当前合约与9999同时加载，仅处理当前合约
        # 此对象仅储存非9999合约编码
        current_vt_symbol = set()
        for vt_symbol in bars:
            bar = bars[vt_symbol]
            if bar is None:
                continue
            exchange, symbol, month = split_vnpy_format(vt_symbol)
            if month != MainContractPortfolioStrategy.history_contract_default_code:
                current_vt_symbol.add(symbol)
            pass
        self.output("after change month: %s" % bars)
        now = datetime.now()
        for vt_symbol in bars:
            bar = bars[vt_symbol]
            if bar is None:
                continue
            # 过滤启动时收到的实时k线
            if not self.trading \
                    and bar.datetime.date() == now.date() \
                    and bar.datetime.time() >= (now - timedelta(minutes=1)).time():
                self.output("realtime bars on starting process, skipped. bar=%s" % bar)
                continue
            exchange, symbol, month = split_vnpy_format(vt_symbol)
            # 加载时如果当前合约已经有数据，则忽略主力合约
            if month == MainContractPortfolioStrategy.history_contract_default_code \
                    and symbol in current_vt_symbol:
                continue
            # 更新k线到日线里
            self.day_bgs[symbol].update_bar(bar)
            if symbol not in self.vt_used_capital:
                self.vt_used_capital[symbol] = 0
            try:
                # 子类策略实现
                self.process_main_contract_bar(bar)
            except Exception as e:
                self.logger.error(e, stack_info=True, exc_info=True)
                raise e

        pass

    def process_main_contract_bar(self, bar: BarData):
        """此方法用于给子类重写，类似原来重写on_bar方法
        当前策略对于回测基本不会产生影响，故仅能通过实盘来验证。
        """
        pass

    def _get_deposit(self, symbol: str, price: float, size: float):
        used_deposit = size * price * self.vt_settings["sizes"][symbol] * self.vt_settings["deposit_rates"][
            symbol] / 100
        return used_deposit

    def stop_order(self, bar: BarData, need_cancel_all=False, do_stop=True, tailing_ratio=1.0,
                   use_atr=False, atr=None,
                   atr_multiplier=1) \
            -> Tuple[bool, float]:
        """
        移动止损
        """
        vt_symbol = bar.vt_symbol
        # exchange, symbol, month = split_vnpy_format(vt_symbol)

        actually_stop = False
        first_after_start = vt_symbol not in self.stop_price or self.stop_price[vt_symbol] is None
        self.stop_price[vt_symbol] = None

        pos = self.get_pos(vt_symbol)
        if pos == 0 or vt_symbol not in self.intraTradeHigh \
                or vt_symbol not in self.intraTradeLow:
            self.intraTradeHigh[vt_symbol] = 0
            self.intraTradeLow[vt_symbol] = float('inf')
        if self.need_stop and pos != 0:
            # 移动止损策略
            if pos > 0:
                self.intraTradeLow[vt_symbol] = bar.low_price
                self.output(
                    "old self.intraTradeHigh[%s]=%s, bar.high_price=%s" % (
                        vt_symbol, self.intraTradeHigh[vt_symbol], bar.high_price))
                if bar.high_price > self.intraTradeHigh[vt_symbol] or first_after_start:
                    self.intraTradeHigh[vt_symbol] = max(self.intraTradeHigh[vt_symbol], bar.high_price)
                    self.output(
                        "new self.intraTradeHigh[%s]=%s" % (vt_symbol, self.intraTradeHigh[vt_symbol]))
                # 计算止损价位
                if use_atr:
                    long_stop = self.intraTradeHigh[vt_symbol] - atr * atr_multiplier
                else:
                    long_stop = self.intraTradeHigh[vt_symbol] * (1 - tailing_ratio * self.trailing_percent / 100)
                if do_stop and bar.close_price < long_stop:
                    self.output(
                        "stop order sell on long_stop:%s, high:%s" % (long_stop, self.intraTradeHigh[vt_symbol]))
                    self.take_order_of_size(vt_symbol, abs(pos), long_stop, Direction.SHORT, Offset.CLOSE)
                    actually_stop = True
                self.stop_price[vt_symbol] = long_stop
            elif pos < 0:
                self.intraTradeHigh[vt_symbol] = bar.high_price
                self.output(
                    "old self.intraTradeLow[%s]=%s, bar.low_price=%s" % (vt_symbol, self.intraTradeLow[vt_symbol],
                                                                         bar.low_price))
                if bar.low_price < self.intraTradeLow[vt_symbol] or first_after_start:
                    self.intraTradeLow[vt_symbol] = min(self.intraTradeLow[vt_symbol], bar.low_price)
                    self.output(
                        "new self.intraTradeLow[%s]=%s" % (vt_symbol, self.intraTradeLow[vt_symbol]))
                # 计算止损价位
                if use_atr:
                    short_stop = self.intraTradeLow[vt_symbol] + atr * atr_multiplier
                else:
                    short_stop = self.intraTradeLow[vt_symbol] * (1 + tailing_ratio * self.trailing_percent / 100)
                if do_stop and bar.close_price > short_stop:
                    self.output(
                        "stop order cover on short_stop:%s, low:%s" % (short_stop, self.intraTradeLow[vt_symbol]))
                    self.take_order_of_size(vt_symbol, abs(pos), short_stop, Direction.LONG, Offset.CLOSE)
                    actually_stop = True
                self.stop_price[vt_symbol] = short_stop
        return actually_stop, self.stop_price[vt_symbol]

    def take_order_of_size(self, vt_symbol: str, change_size: int, price: float, direction: Direction,
                           offset: Offset, ask_bid_diff=20):
        """按照实际手数进行开仓"""
        if change_size < 1:
            return
        if not self.inited_internal or not self.trading:
            return
        if self.need_cancel_all:
            self.cancel_all()
            self.need_cancel_all = False
            self.output("change self.need_cancel_all=%s" % self.need_cancel_all)
        if not self.back_testing:
            sleep(0.5)
        exchange, symbol, month = split_vnpy_format(vt_symbol)
        pos = self.get_pos(vt_symbol)
        used_deposit = self._get_deposit(symbol, price, change_size)
        # 开仓
        if offset == Offset.OPEN:

            used_capital = 0
            for contract in self.vt_used_capital:
                used_capital += self.vt_used_capital[contract]
            used_capital_info = "capital=%s,used=%s,percent=%s" % (
                self.capital, used_capital, round(used_capital / self.capital * 100, 2))
            # print(used_capital_info)
            self.output(used_capital_info)
            # 计算资金是否足够开仓
            if used_capital + used_deposit > self.capital * MainContractPortfolioStrategy.max_use_percent / 100:
                self.output("not enough capital, %s , used= %s" % (used_capital, used_deposit))
                return

            self.vt_used_capital[symbol] += used_deposit
            # 下单
            if direction == Direction.LONG:
                ids = self.buy(vt_symbol, price + ask_bid_diff, change_size)
                # print("ids=%s" % ids)
                self.output("buy vt_symbol=%s, price=%s, size=%s, current_pos=%s, inited_internal=%s" % (
                    vt_symbol, price, change_size, pos, self.inited_internal))
            else:
                ids = self.short(vt_symbol, price - ask_bid_diff, change_size)
                # print("ids=%s" % ids)
                self.output("short vt_symbol=%s, price=%s, size=%s, current_pos=%s, inited_internal=%s" % (
                    vt_symbol, price, change_size, pos, self.inited_internal))
            pass
        else:
            """平仓"""
            self.vt_used_capital[symbol] -= used_deposit
            if self.vt_used_capital[symbol] < 0:
                self.vt_used_capital[symbol] = 0
            if abs(pos) == abs(change_size):
                self.vt_used_capital[symbol] = 0
            if pos == 0:
                return
            # 平仓
            if pos < 0:
                self.cover(vt_symbol, price + ask_bid_diff, change_size)
                self.output("cover vt_symbol=%s, price=%s, size=%s" % (vt_symbol, price, change_size))
            else:
                self.sell(vt_symbol, price - ask_bid_diff, change_size)
                self.output("sell vt_symbol=%s, price=%s, size=%s" % (vt_symbol, price, change_size))
            pass

    def calculate_volume_use_atr(self, symbol, current_price, atr=None,
                                 atr_multiplier=1, money_at_risk_rate=1.0):
        volume = 1
        # 计算每手保证金
        cost_per_order = self.vt_settings["sizes"][symbol] * current_price * self.vt_settings["deposit_rates"][
            symbol] / 100
        money_at_risk_per_contract = self.vt_settings["sizes"][symbol] * atr * atr_multiplier
        volume = round(self.capital * money_at_risk_rate / 100 / money_at_risk_per_contract)
        if volume <= 0:
            volume = 1
        # 防止超出总可用资本
        if volume * cost_per_order > self.capital:
            volume = 0
        self.output("self.capital: %s , volume: %s" % (self.capital, volume))
        return volume
