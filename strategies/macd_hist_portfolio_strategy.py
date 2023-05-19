from typing import Dict, List

import scipy.special
from vnpy.trader.constant import Direction, Offset
from vnpy.trader.object import BarData
from vnpy_portfoliostrategy import StrategyEngine

from strategies.base_portfolio_strategy import BasePortfolioStrategy
from util.day_bar_generator import DayBarGenerator
from util.vt_symbol_util import split_vnpy_format


class MacdHistPortfolioStrategy(BasePortfolioStrategy):
    """"""

    author = "dongzhi"

    fast_window = 40  # 短期均线长度
    mid_window = 80  # 中期均线长度

    percent = 5

    parameters = ["fast_window", "mid_window", "percent", "need_stop", "trailing_percent",
                  'capital']
    variables = [
        'capital', 'vt_used_capital', "intraTradeHigh", "intraTradeLow"
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
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)

        for vt_symbol in self.vt_symbols:
            exchange, symbol, month = split_vnpy_format(vt_symbol)
            self.day_bgs[symbol] = DayBarGenerator(200)

    def on_bars(self, bars: Dict[str, BarData]):
        for vt_symbol in bars:
            bar = bars[vt_symbol]
            self.process_single_bar(bar)

    def process_single_bar(self, bar: BarData):
        vt_symbol = bar.vt_symbol
        exchange, symbol, month = split_vnpy_format(vt_symbol)

        dbg = self.day_bgs[symbol]
        # 更新k线到日线里
        self.day_bgs[symbol].update_bar(bar)
        # 若缓存的K线数量尚不够计算技术指标，则直接返回
        if not dbg.is_inited(self.mid_window):
            # print("not inited")
            return

        pos = self.get_pos(vt_symbol)
        # 计算快速均线
        fast_ma = dbg.sma(self.fast_window, array=True)
        fast_ma0 = fast_ma[-1]  # T时刻数值
        fast_ma1 = fast_ma[-2]  # T-1时刻数值
        # 计算中速均线
        mid_ma = dbg.sma(self.mid_window, array=True)
        mid_ma0 = mid_ma[-1]  # T时刻数值
        mid_ma1 = mid_ma[-2]  # T-1时刻数值

        # 计算macd
        macd_macd, macd_signal, macd_hist = dbg.macd(12, 26, 9, array=True)

        # 判断是否短期均线高于中期均线，即上升趋势
        cross_1 = (fast_ma0 > mid_ma0)

        # 目前尚未进行资金管理，使用固定手数开仓
        # volume = 20
        # 动态计算开仓手数
        volume = self.calculate_volume(symbol, bar.close_price)

        # 使用两个数组记录柱状线，长度可配置，便于判断两个数组的斜率是否一致
        macd_hist_trend = []
        macd_hist_trend_before = []
        new_trend_len = 2
        old_trend_len = 3
        # 将对应柱状线放入前后两个列表中
        for i in range(new_trend_len):
            macd_hist_trend.append(macd_hist[-1 - i] - macd_hist[-2 - i])
        for i in range(old_trend_len):
            macd_hist_trend_before.append(macd_hist[-1 - new_trend_len - i] - macd_hist[-2 - new_trend_len - i])
        # 分别记录转折点前后斜率是否上升/下降
        trend_up = len([v for v in macd_hist_trend if v > 0]) == len(macd_hist_trend)
        trend_down = len([v for v in macd_hist_trend if v < 0]) == len(macd_hist_trend)
        trend_before_up = len([v for v in macd_hist_trend_before if v > 0]) == len(macd_hist_trend_before)
        trend_before_down = len([v for v in macd_hist_trend_before if v < 0]) == len(macd_hist_trend_before)

        # 记录逻辑仓位，target_pos=-1/0/1分别代表开空/平仓/开多
        pos_changed = False
        target_pos = 0
        # 最后一根柱状线<0，且斜率先降后升，开多
        if not cross_1 and macd_hist[-1] < 0 and trend_before_down and trend_up:
            target_pos = 1
            pos_changed = True
        # 最后一根柱状线>0，且斜率先升后降，开空
        if cross_1 and macd_hist[-1] > 0 and trend_before_up and trend_down:
            target_pos = -1
            pos_changed = True

        # 如果现有仓位与目标仓位相反，先单独平仓，等待下一分钟再执行开仓
        # 避免同时进行两笔交易可能导致的回调异常
        if pos * target_pos < 0:
            target_pos = 0

        # 计算最终目标仓位
        target_volumn = int(volume * target_pos)
        # 异常数据过滤，如目标仓位方向一致，但新仓位较低，则不做任何操作
        # 当引入手数计算以后，可能会出现手数随其他因素波动情况，此时需要避免频繁操作
        if pos * target_pos > 0 and abs(pos) >= abs(target_volumn):
            return
        # 仓位发生变化，计算差额
        change_volumn = target_volumn - pos
        if change_volumn == 0:
            return
        # 逻辑仓位未变化直接忽略，减少运算与操作次数
        if not pos_changed:
            return
        # 取消所有未成交的指令
        self.cancel_all()
        # 多单持仓，且目标仓位增加，开多
        if pos >= 0 and change_volumn > 0:
            # 为了保证成交，在K线收盘价上加10发出限价单
            price = bar.close_price + 10
            vt_order_ids = self.buy(vt_symbol, price, change_volumn)
            self.output("buy vt_order_ids : %s" % str(vt_order_ids))
        # 当前持有空头仓位，则先平空
        elif pos < 0 and change_volumn > 0:
            price = bar.close_price + 10
            vt_order_ids = self.cover(vt_symbol, price, change_volumn)
            self.output("cover: %s" % str(vt_order_ids))
        # 多单持仓，仓位减小，平多
        elif pos > 0 and change_volumn < 0:
            price = bar.close_price - 10
            self.sell(vt_symbol, price, -change_volumn)
        # 空单持仓，仓位数值减少，即空单增加，开空
        elif pos <= 0 and change_volumn < 0:
            price = bar.close_price - 10
            self.short(vt_symbol, price, -change_volumn)

        # vnpy内置方法，用于触发客户端UI组件更新，可写可不写
        self.put_event()

    def calculate_volume(self, symbol, current_price):
        volume = 1
        # 计算每手保证金
        cost_per_order = self.vt_settings["sizes"][symbol] \
                         * current_price * self.vt_settings["deposit_rates"][symbol] / 100
        volume = round(self.capital * self.percent / 100 / cost_per_order)
        if volume <= 0:
            volume = 0
        # 防止超出总可用资本
        if volume * cost_per_order > self.capital:
            volume = volume - 1
        self.output("self.capital: %s , volume: %s" % (self.capital, volume))
        return volume