from vnpy.trader.object import (
    BarData,
)

from strategies.base_cta_strategy import BaseCtaStrategy
from util.day_bar_generator import DayBarGenerator


class MacdHistStrategy(BaseCtaStrategy):
    # 策略作者
    author = "Dongzhi"
    # 日志
    logger = None

    # 定义参数
    bar_window = 1  # k线间隔，单位：分钟
    fast_window = 40  # 短期均线长度
    mid_window = 80  # 中期均线长度

    # 定义变量
    fast_ma0 = 0.0
    fast_ma1 = 0.0
    mid_ma0 = 0.0
    mid_ma1 = 0.0

    # 添加参数和变量名到对应的列表
    parameters = ["capital", "size", "rate", "slippage", "deposit_rate", "percent", "need_stop", "trailing_percent", "bar_window",
                  "fast_window", "mid_window"]
    variables = ["intraTradeHigh", "intraTradeLow", "capital"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.dbg = DayBarGenerator(max_length=100)

    def on_bar_m(self, bar: BarData):

        self.output("on_bar_m : %s" % str(bar))
        """
        通过该函数处理策略逻辑，MACD柱状线
        """
        # 更新K线到时间序列容器中
        self.dbg.update_bar(bar)

        # 若缓存的K线数量尚不够计算技术指标，则直接返回
        # 这里30主要是为了计算MACD的26日均线，大于26即可。
        if not self.dbg.is_inited(self.mid_window):
            # print("not inited")
            return

        # 移动止损
        self.stop_order(bar)

        # 计算快速均线
        fast_ma = self.dbg.sma(self.fast_window, array=True)
        self.fast_ma0 = fast_ma[-1]  # T时刻数值
        self.fast_ma1 = fast_ma[-2]  # T-1时刻数值
        # 计算中速均线
        mid_ma = self.dbg.sma(self.mid_window, array=True)
        self.mid_ma0 = mid_ma[-1]  # T时刻数值
        self.mid_ma1 = mid_ma[-2]  # T-1时刻数值

        # 计算macd
        macd_macd, macd_signal, macd_hist = self.dbg.macd(12, 26, 9, array=True)

        # 判断是否短期均线高于中期均线，即上升趋势
        cross_1 = (self.fast_ma0 > self.mid_ma0)

        # 目前尚未进行资金管理，使用固定手数开仓
        # volume = 20
        # 动态计算开仓手数
        volume = self.calculate_volume(bar.close_price)

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
        if self.pos * target_pos < 0:
            target_pos = 0


        # 计算最终目标仓位
        target_volumn = int(volume * target_pos)
        # 异常数据过滤，如目标仓位方向一致，但新仓位较低，则不做任何操作
        # 当引入手数计算以后，可能会出现手数随其他因素波动情况，此时需要避免频繁操作
        if self.pos * target_pos > 0 and abs(self.pos) >= abs(target_volumn):
            return
        # 仓位发生变化，计算差额
        change_volumn = target_volumn - self.pos
        if change_volumn == 0:
            return
        # 逻辑仓位未变化直接忽略，减少运算与操作次数
        if not pos_changed:
            return
        # 取消所有未成交的指令
        self.cancel_all()
        # 多单持仓，且目标仓位增加，开多
        if self.pos >= 0 and change_volumn > 0:
            # 为了保证成交，在K线收盘价上加10发出限价单
            price = bar.close_price + 10
            vt_order_ids = self.buy(price, change_volumn)
            self.output("buy vt_order_ids : %s" % str(vt_order_ids))
        # 当前持有空头仓位，则先平空
        elif self.pos < 0 and change_volumn > 0:
            price = bar.close_price + 10
            vt_order_ids = self.cover(price, change_volumn)
            self.output("cover: %s" % str(vt_order_ids))
        # 多单持仓，仓位减小，平多
        elif self.pos > 0 and change_volumn < 0:
            price = bar.close_price - 10
            self.sell(price, -change_volumn)
        # 空单持仓，仓位数值减少，即空单增加，开空
        elif self.pos <= 0 and change_volumn < 0:
            price = bar.close_price - 10
            self.short(price, -change_volumn)

        # vnpy内置方法，用于触发客户端UI组件更新，可写可不写
        self.put_event()

