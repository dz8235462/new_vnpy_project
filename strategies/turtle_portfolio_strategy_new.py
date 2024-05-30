from typing import List

from vnpy.trader.constant import Direction, Offset
from vnpy.trader.object import BarData
from vnpy_portfoliostrategy import StrategyEngine

from strategies.main_contract_portfolio_strategy import MainContractPortfolioStrategy
from util.vt_symbol_util import split_vnpy_format

TRADING = 0
GAIN = 1
LOSS = 2


class TurtlePortfolioStrategy(MainContractPortfolioStrategy):
    """"""

    author = "dongzhi"

    unit_one_contract = 4
    unit_same_market = 6
    unit_same_direction_diff_market = 10
    unit_same_direction = 12

    s1_window = 20
    s2_window = 55
    exit_window = 10
    atr_window = 20
    moving_stop_size = 1

    # 记录相关市场的合约 {v1:[v1,v2,v3]}
    vt_relations = {}
    # 记录每个合约占用的保证金，防止开仓金额不足
    vt_used_capital = {}
    # 记录每个合约当前的单位，正负表示,仅需要单向
    vt_used_unit = {}
    # 记录最后一次平仓日期，便于平仓当前避免同方向再次开仓
    vt_last_close_time = {}
    # 最大资金使用率
    max_use_percent = 80

    percent_at_risk = 0.007

    vt_settings_json = "{}"
    parameters = [
        "s1_window", "s2_window", "exit_window", "moving_stop_size", "capital"
    ]
    variables = [
        'capital', 'vt_used_unit', 'vt_used_capital', 'vt_stop_price', 'vt_last_trade_status', 'vt_donchian_1',
        'vt_donchian_2', 'vt_atr', 'use_new_donchian', 'vt_last_close_time'
    ]

    def __init__(
            self,
            strategy_engine: StrategyEngine,
            strategy_name: str,
            vt_symbols: List[str],
            setting: dict
    ):
        """"""
        self.no_data = {}
        self.s1_window = 25
        self.s2_window = 55
        self.exit_window = 10
        self.atr_window = 20
        self.moving_stop_size = 1
        self.percent_at_risk = TurtlePortfolioStrategy.percent_at_risk
        # 生成日线的工具
        # 记录相关市场的合约 {v1:[v1,v2,v3]}
        self.vt_relations = {}
        # 记录每个合约占用的保证金，防止开仓金额不足
        self.vt_used_capital = {}
        # 记录每个合约当前的单位，正负表示,仅需要单向
        self.vt_used_unit = {}
        # 记录止损价格
        self.vt_stop_price = {}
        self.use_new_donchian = {}
        self.vt_atr = {}
        self.vt_donchian_1 = {}
        self.vt_donchian_2 = {}
        self.vt_last_trade_status = {}
        self.vt_last_close_time = {}
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        for vt_symbol in self.vt_symbols:
            exchange, symbol, month = split_vnpy_format(vt_symbol)
            if symbol not in self.vt_used_unit:
                self.vt_used_unit[symbol] = 0
                self.vt_used_capital[symbol] = 0
        for r_array in self.vt_settings["vt_relation_arrays"]:
            for symbol in r_array:
                self.vt_relations[symbol] = r_array

    def process_main_contract_bar(self, bar: BarData):
        vt_symbol = bar.vt_symbol
        exchange, symbol, month = split_vnpy_format(vt_symbol)
        self.day_bgs[symbol].update_bar(bar)

        if symbol not in self.vt_used_unit:
            self.vt_used_unit[symbol] = 0
            self.vt_used_capital[symbol] = 0

        unit = self.vt_used_unit[symbol]
        pos = self.get_pos(vt_symbol)

        # if self.inited and unit != 0 and abs(pos) == 0:
        #     self.vt_used_unit[vt_symbol] = 0
        #     self.vt_used_capital[vt_symbol] = 0
        # if bar.datetime.month==12 and bar.datetime.hour==9 and symbol=="ag":
        #    print(1)
        # 防止新增合约无保证金数据
        if unit != 0 and self.vt_used_capital[symbol] == 0:
            deposit = self.get_deposit(symbol, bar.close_price, abs(pos))
            self.output("update deposit of %s, amount=%s" % (vt_symbol, deposit))
            self.vt_used_capital[symbol] = deposit

        # # 防止平仓未成交
        # if unit == 0 and pos != 0:
        #     self.take_order(vt_symbol, 1, bar.close_price, direction=Direction.SHORT if pos > 0 else Direction.LONG,
        #                     offset=Offset.CLOSE)
        # # 系统1
        atr = self.day_bgs[symbol].atr(self.atr_window)
        # 止损退出
        if unit > 0:
            if symbol not in self.vt_stop_price:
                self.vt_stop_price[symbol] = 0
            if self.vt_stop_price[symbol] < bar.close_price - self.moving_stop_size * atr:
                self.vt_stop_price[symbol] = bar.close_price - self.moving_stop_size * atr
            if bar.close_price < self.vt_stop_price[symbol]:
                self.take_order(vt_symbol, 1, bar.close_price, direction=Direction.SHORT, offset=Offset.CLOSE)
                self.vt_last_trade_status[symbol] = LOSS
                self.vt_last_close_time["%s_%s" % (symbol, Direction.SHORT)] = bar.datetime.date().__str__()
        if unit < 0:
            if symbol not in self.vt_stop_price:
                self.vt_stop_price[symbol] = float('inf')
            if self.vt_stop_price[symbol] > bar.close_price + self.moving_stop_size * atr:
                self.vt_stop_price[symbol] = bar.close_price + self.moving_stop_size * atr
            if bar.close_price > self.vt_stop_price[symbol]:
                self.take_order(vt_symbol, 1, bar.close_price, direction=Direction.LONG, offset=Offset.CLOSE)
                self.vt_last_trade_status[symbol] = LOSS
                self.vt_last_close_time["%s_%s" % (symbol, Direction.LONG)] = bar.datetime.date().__str__()
        # 正常退出
        e_up, e_down = self.day_bgs[symbol].donchian(self.exit_window)
        # if symbol == "ag":
        #    print("vt_symbol=%s,unit=%s,pos=%s,used_deposit=%s,e_up=%s,e_down=%s,time=%s" % (
        #        vt_symbol, unit, self.get_pos(vt_symbol), self.vt_used_capital[symbol], e_up, e_down,bar.datetime))
        self.output("vt_symbol=%s,unit=%s,pos=%s,used_deposit=%s,e_up=%s,e_down=%s" % (
            vt_symbol, unit, self.get_pos(vt_symbol), self.vt_used_capital[symbol], e_up, e_down))
        if e_up is not None:
            if unit > 0 and bar.close_price < e_down:
                self.take_order(vt_symbol, 1, bar.close_price, direction=Direction.SHORT, offset=Offset.CLOSE)
                self.vt_last_trade_status[symbol] = LOSS  # todo
                self.vt_last_close_time["%s_%s" % (symbol, Direction.SHORT)] = bar.datetime.date().__str__()
            elif unit < 0 and bar.close_price > e_up:
                self.take_order(vt_symbol, 1, bar.close_price, direction=Direction.LONG, offset=Offset.CLOSE)
                self.vt_last_trade_status[symbol] = LOSS  # todo
                self.vt_last_close_time["%s_%s" % (symbol, Direction.LONG)] = bar.datetime.date().__str__()

        s1_up, s1_down = self.day_bgs[symbol].donchian(self.s1_window)
        if symbol in self.use_new_donchian and self.use_new_donchian[symbol]:
            self.clear_donchian_cache(symbol)
            self.vt_donchian_1[symbol] = s1_up, s1_down
            self.vt_atr[symbol] = atr
            self.use_new_donchian[symbol] = False
            self.output("use_new_donchian symbol=%s" % (symbol))
            self.sync_data()
        if symbol in self.vt_donchian_1 and self.vt_donchian_1[symbol] is not None:
            s1_up, s1_down = self.vt_donchian_1[symbol]
        if symbol in self.vt_atr and self.vt_atr[symbol] is not None:
            atr = self.vt_atr[symbol]
        self.output("vt_symbol=%s,atr=%s,s1_up=%s,s1_down=%s,current=%s,capital=%s" % (
            vt_symbol, atr, s1_up, s1_down, bar.close_price, self.capital))
        if s1_up is not None:
            changed_unit = 0
            long_close_today = False
            if "%s_%s" % (symbol, Direction.LONG) in self.vt_last_close_time:
                long_close_today = self.vt_last_close_time[
                                       "%s_%s" % (symbol, Direction.LONG)] == bar.datetime.date().__str__()
                # print('long_close_today %s , %s , %s' % (
                #     self.vt_last_close_time["%s_%s" % (symbol, Direction.LONG)].date(), datetime.now().date(),
                #     long_close_today))
            short_close_today = False
            if "%s_%s" % (symbol, Direction.SHORT) in self.vt_last_close_time:
                short_close_today = self.vt_last_close_time[
                                        "%s_%s" % (symbol, Direction.SHORT)] == bar.datetime.date().__str__()
                # print('short_close_today %s , %s , %s' % (
                #     self.vt_last_close_time["%s_%s" % (symbol, Direction.SHORT)].date(), datetime.now().date(),
                #     short_close_today))
            for i in range(TurtlePortfolioStrategy.unit_one_contract):
                self.output(
                    "vt_symbol=%s,bar.close_price=%s,s1_up + i/2*atr=%s,self.vt_used_unit[symbol] < i + 1=%s" % (
                        vt_symbol, bar.close_price, s1_up + i / 2 * atr, self.vt_used_unit[symbol] < i + 1))
                if bar.close_price > s1_up + i / 2 * atr and self.vt_used_unit[symbol] < i + 1:
                    # 记录突破,判断上次突破是否盈利
                    # 如果亏损，按系统1开仓
                    if symbol not in self.vt_last_trade_status or self.vt_last_trade_status[symbol] != GAIN:
                        changed_unit += 1
                    self.vt_last_trade_status[symbol] = TRADING
                self.output(
                    "vt_symbol=%s,bar.close_price=%s,s1_down - i/2*atr=%s,self.vt_used_unit[symbol] > -i - 1=%s" % (
                        vt_symbol, bar.close_price, s1_down - i / 2 * atr, self.vt_used_unit[symbol] > -i - 1))
                if bar.close_price < s1_down - i / 2 * atr and self.vt_used_unit[symbol] > -i - 1:
                    if symbol not in self.vt_last_trade_status or self.vt_last_trade_status[symbol] != GAIN:
                        changed_unit -= 1
                    self.vt_last_trade_status[symbol] = TRADING
            # 如价格差距过大，说明已错过开仓点，直接忽略
            if changed_unit > 0 and bar.close_price > s1_up + (
                    TurtlePortfolioStrategy.unit_one_contract - 0.8) / 2 * atr:
                changed_unit = 0
                if unit == 0:
                    self.clear_donchian_cache(symbol)
            if changed_unit < 0 and bar.close_price < s1_down - (
                    TurtlePortfolioStrategy.unit_one_contract - 0.8) / 2 * atr:
                changed_unit = 0
                if unit == 0:
                    self.clear_donchian_cache(symbol)
            if changed_unit > 0 and not short_close_today:
                if unit == 0:
                    self.vt_donchian_1[symbol] = s1_up, s1_down
                    self.vt_atr[symbol] = atr
                self.take_order(vt_symbol, changed_unit, bar.close_price, direction=Direction.LONG, offset=Offset.OPEN)
                self.vt_stop_price[symbol] = bar.close_price - self.moving_stop_size * atr
            elif changed_unit < 0 and not long_close_today:
                if unit == 0:
                    self.vt_donchian_1[symbol] = s1_up, s1_down
                    self.vt_atr[symbol] = atr
                self.take_order(vt_symbol, -changed_unit, bar.close_price, direction=Direction.SHORT,
                                offset=Offset.OPEN)
                self.vt_stop_price[symbol] = bar.close_price + self.moving_stop_size * atr
        # if vt_symbol[0:2] == 'IF':
        #     return
        # s2_up, s2_down = self.day_bgs[vt_symbol].donchian(self.s2_window)
        # if vt_symbol in self.vt_donchian_2 and self.vt_donchian_2[vt_symbol] is not None:
        #     s2_up, s2_down = self.vt_donchian_2[vt_symbol]
        # self.output("vt_symbol=%s,atr=%s,s2_up=%s,s2_down=%s" % (vt_symbol, atr, s2_up, s2_down))
        # if s2_up is not None:
        #     for i in range(TurtlePortfolioStrategy.unit_one_contract):
        #         if bar.close_price > s2_up + i / 2 * atr and self.vt_used_unit[vt_symbol] < i + 1:
        #             # 记录突破,判断上次突破是否盈利
        #             self.take_order(vt_symbol, 1, bar.close_price, direction=Direction.LONG, offset=Offset.OPEN)
        #             self.vt_donchian_2[vt_symbol] = s2_up, s2_down
        #             self.vt_stop_price[vt_symbol] = bar.close_price - self.moving_stop_size * atr
        #         if bar.close_price < s2_down - i / 2 * atr and self.vt_used_unit[vt_symbol] > -i - 1:
        #             self.take_order(vt_symbol, 1, bar.close_price, direction=Direction.SHORT, offset=Offset.OPEN)
        #             self.vt_donchian_2[vt_symbol] = s2_up, s2_down
        #             self.vt_stop_price[vt_symbol] = bar.close_price + self.moving_stop_size * atr

        # 清空模拟数据
        self.output("self.need_cancel_all=%s" % self.need_cancel_all)
        if self.trading and self.need_cancel_all:
            self.check_pos(vt_symbol, bar.close_price)
        pass

    def size_of_atr(self, symbol: str, window: int):
        atr = self.day_bgs[symbol].atr(window)
        if symbol in self.vt_atr and self.vt_atr[symbol] is not None:
            atr = self.vt_atr[symbol]
        vt_size = self.vt_settings["sizes"][symbol]
        if atr <= 0 or vt_size <= 0:
            return 0
        # print("symbol=%s,size=%s,atr=%s" % (vt_symbol, vt_size, atr))
        volume = min(self.capital, 5000000) * self.percent_at_risk / atr / vt_size
        return volume

    def get_deposit(self, symbol: str, price: float, size: float):

        used_deposit = size * price * self.vt_settings["sizes"][symbol] * self.vt_settings["deposit_rates"][
            symbol] / 100
        return abs(used_deposit)

    def take_order(self, vt_symbol: str, unit: int, price: float, direction: Direction, offset: Offset):

        exchange, symbol, month = split_vnpy_format(vt_symbol)
        pos = self.get_pos(vt_symbol)
        # 开仓
        if offset == Offset.OPEN:
            coefficient = (1 if direction == Direction.LONG else -1)
            # 判断是否需要继续开仓
            # 单合约上限
            if abs(self.vt_used_unit[symbol]) >= TurtlePortfolioStrategy.unit_one_contract:
                self.output("abs(self.vt_used_unit[symbol]) >= TurtlePortfolioStrategy.unit_one_contract")
                return
            # 相关市场上限
            contracts_related = self.vt_relations[symbol]
            related_unit = 0
            for contract in contracts_related:
                if contract not in self.vt_used_unit:
                    continue
                unit_of_contract = self.vt_used_unit[contract] * (1 if direction == Direction.LONG else -1)
                related_unit += unit_of_contract if unit_of_contract > 0 and self.vt_used_capital[contract] > 0 else 0
            if related_unit >= TurtlePortfolioStrategy.unit_same_market:
                self.output("related_unit >= TurtlePortfolioStrategy.unit_same_market")
                return
            # 全市场上限
            total_unit = 0
            for contract in self.vt_used_unit:
                if contract not in self.vt_used_unit:
                    continue
                unit_of_contract = self.vt_used_unit[contract] * (1 if direction == Direction.LONG else -1)
                total_unit += unit_of_contract if unit_of_contract > 0 and self.vt_used_capital[contract] > 0 else 0
            if total_unit >= TurtlePortfolioStrategy.unit_same_direction:
                self.output("total_unit >= TurtlePortfolioStrategy.unit_same_direction")
                return
            # 判断资金是否足够
            # 更新单位与占用资金
            self.vt_used_unit[symbol] += coefficient * unit
            unit_size = self.size_of_atr(symbol, self.atr_window)
            change_size = self.get_change_pos(vt_symbol, self.vt_used_unit[symbol], unit_size)
            used_deposit = self.get_deposit(symbol, price, change_size)
            if pos == 0:
                self.vt_used_capital[symbol] = 0
            used_capital = 0
            for contract in self.vt_used_capital:
                used_capital += self.vt_used_capital[contract]
            # if symbol == "ag":
            #    print("capital=%s,used=%s,percent=%s" % (
            #        self.capital, used_capital, round(used_capital / self.capital * 100, 2)))
            self.output("capital=%s,used=%s,percent=%s" % (
                self.capital, used_capital, round(used_capital / self.capital * 100, 2)))
            if used_capital + used_deposit > self.capital * TurtlePortfolioStrategy.max_use_percent / 100:
                # print("capital is used beyond limit, used_capital=%s,used_deposit=%s,capital=%s" % (
                #     used_capital, used_deposit, self.capital))
                self.vt_used_unit[symbol] -= coefficient * unit
                self.output(
                    "used_capital + used_deposit > self.capital * TurtlePortfolioStrategy.max_use_percent / 100")
                return

            self.vt_used_capital[symbol] += used_deposit
            if change_size < 1:
                self.output(
                    "change_size < 1")
                return
            # 取消未成交
            if self.need_cancel_all:
                self.cancel_all()
                self.need_cancel_all = False
                self.output("take_order self.need_cancel_all=%s" % self.need_cancel_all)
            # 下单
            if direction == Direction.LONG:
                self.buy(vt_symbol, price + 20, change_size)
                self.output("buy vt_symbol=%s, price=%s, size=%s, current_pos=%s, inited_internal=%s" % (
                    vt_symbol, price, change_size, pos, self.inited_internal))
            else:
                self.short(vt_symbol, price - 20, change_size)
                self.output("short vt_symbol=%s, price=%s, size=%s, current_pos=%s, inited_internal=%s" % (
                    vt_symbol, price, change_size, pos, self.inited_internal))
            pass
        else:

            unit = self.vt_used_unit[symbol]
            self.vt_used_unit[symbol] = 0
            self.vt_used_capital[symbol] = 0
            self.clear_donchian_cache(symbol)

            if pos == 0:
                return
            # 取消未成交
            if self.need_cancel_all:
                self.cancel_all()
                self.need_cancel_all = False
                self.output("take_order self.need_cancel_all=%s" % self.need_cancel_all)
            # 平仓
            if pos < 0:
                self.cover(vt_symbol, price + 20, abs(pos))
                self.output("cover vt_symbol=%s, price=%s, unit=%s, size=%s" % (vt_symbol, price, unit, abs(pos)))
            else:
                self.sell(vt_symbol, price - 20, abs(pos))
                self.output("sell vt_symbol=%s, price=%s, unit=%s, size=%s" % (vt_symbol, price, unit, abs(pos)))
            pass

    def clear_donchian_cache(self, symbol):
        self.vt_donchian_1[symbol] = None
        self.vt_atr[symbol] = None
        self.vt_donchian_2[symbol] = None

    def check_pos(self, vt_symbol, price):
        # 待移除，避免因仓位总数限制导致部分品种平仓后重新开仓相关品种
        exchange, symbol, month = split_vnpy_format(vt_symbol)
        unit = self.vt_used_unit[symbol]
        if unit == 0:
            self.vt_atr[symbol] = None
        pos = self.get_pos(vt_symbol)
        unit_size = self.size_of_atr(symbol, self.atr_window)
        gap = int(unit_size * unit - pos)
        target_pos = self.get_change_pos(vt_symbol, self.vt_used_unit[symbol], unit_size) + abs(pos)
        target_pos = target_pos * (1 if unit > 0 else -1)
        gap = int(target_pos - pos)
        self.output("check_pos,vt_symbol=%s,unit=%s,unit_size=%s,pos=%s,target_pos=%s,gap=%s" % (
            vt_symbol, unit, unit_size, pos, target_pos, gap
        ))
        # if abs(gap) >= 0.8 * unit_size and abs(gap) >= 1 or unit == 0:
        #     if gap > 0:
        #         if unit > 0:
        #             self.buy(vt_symbol, price + 20, abs(gap))
        #             self.output("check_pos buy vt_symbol=%s, price=%s, size=%s, current_pos=%s, inited_internal=%s" % (
        #                 vt_symbol, price, abs(gap), pos, self.inited_internal))
        #         if unit <= 0:
        #             self.cover(vt_symbol, price + 20, abs(gap))
        #             self.output(
        #                 "check_pos cover vt_symbol=%s, price=%s, size=%s, current_pos=%s, inited_internal=%s" % (
        #                     vt_symbol, price, abs(gap), pos, self.inited_internal))
        #     if gap < 0:
        #         if unit < 0:
        #             self.short(vt_symbol, price - 20, abs(gap))
        #             self.output(
        #                 "check_pos short vt_symbol=%s, price=%s, size=%s, current_pos=%s, inited_internal=%s" % (
        #                     vt_symbol, price, abs(gap), pos, self.inited_internal))
        #         if unit >= 0:
        #             self.sell(vt_symbol, price - 20, abs(gap))
        #             self.output(
        #                 "check_pos sell vt_symbol=%s, price=%s, size=%s, current_pos=%s, inited_internal=%s" % (
        #                     vt_symbol, price, abs(gap), pos, self.inited_internal))
        pass

    def get_change_pos(self, vt_symbol, target_unit, unit_size):
        origin_size = unit_size * abs(target_unit)
        if origin_size < 1 and target_unit != 0:
            origin_size = int(
                unit_size + (TurtlePortfolioStrategy.unit_one_contract - 1) / TurtlePortfolioStrategy.unit_one_contract)
        change_size = int(origin_size - abs(self.get_pos(vt_symbol)))
        return change_size
