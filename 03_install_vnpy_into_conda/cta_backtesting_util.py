import numpy as np
import pandas as pd
from vnpy_ctastrategy.backtesting import BacktestingEngine
from vnpy.trader.constant import Interval, Offset, Direction
from vnpy_ctastrategy.strategies.double_ma_strategy import DoubleMaStrategy


def main():
    start = pd.to_datetime("20200101",
                           format='%Y%m%d %H:%M:%S.%f').tz_localize("Asia/Shanghai")

    end = pd.to_datetime("20230101",
                         format='%Y%m%d %H:%M:%S.%f').tz_localize("Asia/Shanghai")
    # 创建引擎,设置回测模式
    engine = BacktestingEngine()
    engine.log_output = True
    # 配置引擎参数
    original_capital = 100000
    engine.set_parameters(vt_symbol="rb9999.SHFE",
                          start=start,
                          end=end,
                          interval=Interval.MINUTE,
                          slippage=1,  #
                          rate=1.01 / 10000,
                          size=10,
                          pricetick=1,
                          capital=original_capital)
    engine.add_strategy(DoubleMaStrategy, {
        'fast_window': 30.0, 'slow_window': 80
    })
    engine.load_data()
    engine.run_backtesting()
    df1 = engine.calculate_result()
    engine.calculate_statistics()
    # 计算单次开仓平仓收益百分比
    trades = engine.get_all_trades()
    engine.show_chart()
    engine.clear_data()


if __name__ == '__main__':
    main()
