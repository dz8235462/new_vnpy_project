from datetime import timedelta
from json import JSONEncoder

import pandas as pd

from vnpy.trader.constant import Interval
from vnpy_portfoliostrategy import BacktestingEngine

from future_data.portfolio_global_config import vt_settings_with_short_code, global_vt_settings
from strategies.base_cta_strategy import GLOBAL_SETTINGS
from strategies.macd_hist_portfolio_strategy import MacdHistPortfolioStrategy

ORDER_PREFIX = "order_"
OPEN = "open"
CLOSE = "close"
WIN = "win"
LOSE = "lose"


def get_portfolio_daily_pnl():
    GLOBAL_SETTINGS["BACK_TESTING_DATA_SAVE"] = False
    start = pd.to_datetime("20100101",
                           format='%Y%m%d %H:%M:%S.%f').tz_localize("Asia/Shanghai")
    end = pd.to_datetime("20200101",
                               format='%Y%m%d %H:%M:%S.%f').tz_localize("Asia/Shanghai")

    # 创建引擎,设置回测模式
    engine = BacktestingEngine()
    engine.log_output = True
    # 配置引擎参数
    original_capital = 1000000
    vt_settings = vt_settings_with_short_code
    vt_symbols = [
                  "rb8888.SHFE","m8888.DCE","MA8888.CZCE","TA8888.CZCE","ag8888.SHFE",
                  # "TA8888.CZCE",
                  # "ag8888.SHFE",  "TA8888.CZCE", "au8888.SHFE", "MA8888.CZCE",
                  # "jm8888.DCE",  "m8888.DCE",
                  # "al8888.SHFE",
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
        # "i8888.DCE", "ag8888.SHFE", "IF8888.CFFEX",
        # "au8888.SHFE", "m8888.DCE", "y8888.DCE",
        # "TA8888.CZCE", "sc8888.INE", "al8888.SHFE",
        interval=Interval.MINUTE,
        start=start,
        end=end,
        rates=global_vt_settings["rates"],
        slippages=global_vt_settings["slippages"],
        sizes=global_vt_settings["sizes"],
        priceticks=global_vt_settings["priceticks"],
        capital=original_capital,
    )

    engine.add_strategy(MacdHistPortfolioStrategy,
                        {"mid_window": 40, "slow_window": 80 ,"percent": 1})
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    engine.calculate_statistics()
    engine.show_chart()
    return daily_df["net_pnl"]


if __name__ == '__main__':
    get_portfolio_daily_pnl()
