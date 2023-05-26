from datetime import timedelta
from json import JSONEncoder

import pandas as pd

from vnpy.trader.constant import Interval
from vnpy_portfoliostrategy import BacktestingEngine

from future_data.portfolio_global_config import vt_settings_with_short_code, global_vt_settings
from strategies.base_cta_strategy import GLOBAL_SETTINGS
from strategies.macd_hist_portfolio_strategy import MacdHistPortfolioStrategy
from strategies.turtle_portfolio_strategy import TurtlePortfolioStrategy

ORDER_PREFIX = "order_"
OPEN = "open"
CLOSE = "close"
WIN = "win"
LOSE = "lose"


def get_portfolio_daily_pnl():
    GLOBAL_SETTINGS["BACK_TESTING_DATA_SAVE"] = False

    load_days = 8
    start = pd.to_datetime("20100101",
                           format='%Y%m%d %H:%M:%S.%f').tz_localize("Asia/Shanghai")
    end = start + timedelta(days=load_days)
    total_end = pd.to_datetime("20120101",
                               format='%Y%m%d %H:%M:%S.%f').tz_localize("Asia/Shanghai")
    # 创建引擎,设置回测模式
    engine = BacktestingEngine()
    engine.log_output = True
    # 配置引擎参数
    original_capital = 100000
    # 'rb8888', 'ag8888', 'IF8888', 'm8888', 'TA8888', 'i8888', 'y8888', 'au8888', 'FG8888', 'sc8888',
    # 'al8888', 'jm8888', 'lh8888'
    vt_settings = vt_settings_with_short_code
    vt_symbols = [
                  "rb8888.SHFE","TA8888.CZCE",
                  "ag8888.SHFE",  "TA8888.CZCE", "au8888.SHFE", "MA8888.CZCE",
                  "jm8888.DCE",  "m8888.DCE",
                  "al8888.SHFE",
                  # "i8888.DCE",
                  # "jm8888.DCE", "ag8888.SHFE", "al8888.SHFE",
                  # "m8888.DCE","IF8888.CFFEX", #"sc8888.INE",
                  # "TA8888.CZCE",  "MA8888.CZCE", "IF8888.CFFEX",
                  ]
    vt_symbols = [v for v in set().union(vt_symbols)]
    vt_settings_json = JSONEncoder().encode(vt_settings)
    print(vt_settings_json)

    engine.set_parameters(
        vt_symbols=vt_symbols,
        interval=Interval.MINUTE,
        start=start,
        end=end,
        rates=global_vt_settings["rates"],
        slippages=global_vt_settings["slippages"],
        sizes=global_vt_settings["sizes"],
        priceticks=global_vt_settings["priceticks"],
        capital=original_capital,
    )
    # 注意add_strategy会重置strategy对象，只能调用一次
    engine.add_strategy(TurtlePortfolioStrategy,
                        {})

    while start < total_end:
        engine.load_data()
        engine.run_backtesting()
        start = end

        end = start + timedelta(days=load_days)
        if end > total_end:
            end = total_end
        engine.set_parameters(
            vt_symbols=vt_symbols,
            interval=Interval.MINUTE,
            start=start,
            end=end,
            rates=global_vt_settings["rates"],
            slippages=global_vt_settings["slippages"],
            sizes=global_vt_settings["sizes"],
            priceticks=global_vt_settings["priceticks"],
            capital=original_capital,
        )

    daily_df = engine.calculate_result()
    engine.calculate_statistics()
    # engine.show_chart()
    return daily_df["net_pnl"]


if __name__ == '__main__':
    get_portfolio_daily_pnl()
