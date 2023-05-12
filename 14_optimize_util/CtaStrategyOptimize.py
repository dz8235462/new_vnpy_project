import math
import time

import pandas as pd

from vnpy.trader.constant import Interval
from vnpy.trader.optimize import OptimizationSetting
from vnpy_ctastrategy.backtesting import BacktestingEngine

from strategies.dual_thrust_strategy_dz import DualThrustStrategyDz

original_capital = 1000000


def main():
    default_setting = {'trailing_percent': 3}
    min_step = 0.05
    start = pd.to_datetime("20180901",
                           format='%Y%m%d %H:%M:%S.%f').tz_localize("Asia/Shanghai")
    end = pd.to_datetime("20190801",
                         format='%Y%m%d %H:%M:%S.%f').tz_localize("Asia/Shanghai")
    # 创建引擎,设置回测模式
    engine = BacktestingEngine()
    # 配置引擎参数
    engine.set_parameters(vt_symbol="rb8888.SHFE",
                          start=start,
                          end=end,
                          interval=Interval.MINUTE,
                          slippage=1,  #
                          rate=0.25 / 10000,
                          size=10,
                          pricetick=1,
                          capital=original_capital)

    """爬山暴力破解优化算法
    通过设置原始参数范围{x: x1-x2 , y: y1-y2}
    假设数据表现接近平滑曲线，将步长设置为 (x2-x1)/5 可将单个参数的模拟次数降低到6次
    即n个参数需要的模拟次数为6^n
    取表现最优的一组参数，按照 (x0-step,x0+step)区间继续拆分，直到步长小于设定的最低精度
    """
    # default_setting["exit_time"] = "14:50"
    # default_setting["stop_revenue_percent"] = 1.5
    # default_setting["bar_window"] = 1
    # default_setting["need_stop"] = 1
    # default_setting["percent"] = 30
    engine.add_strategy(DualThrustStrategyDz, default_setting)
    param_ranges = [
        # {"name": "bar_window", "start": 1, "end": 10, "step": 1},
        {"name": "days", "start": 3, "end": 5, "step": 1},
        # {"name": "stop_revenue_percent", "start": 0.5, "end": 2, "step": 0.01},
        {"name": "k1", "start": 0.2, "end": 0.7, "step": min_step},
        {"name": "k2", "start": 0.4, "end": 1, "step": min_step}]

    best_param = run_optimize(param_ranges, engine)


def run_optimize(param_ranges, engine: BacktestingEngine, target: str = "end_balance"):
    step_constant = 5
    round_cnt = 0
    start_time = time.time()
    best_param = {}
    # statistics = {}
    # 循环执行直到超出一定次数或精度符合要求
    while True:
        optimization_setting = OptimizationSetting()
        # sharpe_ratio end_balance
        optimization_setting.set_target(target)
        # 添加参数到回测引擎
        for param in param_ranges:
            if "scale" not in param:
                # 控制参数精度
                param["precision"], param["scale"] = precision_and_scale(param["step"])
            param["current_step"] = round((param["end"] - param["start"]) / step_constant, param["scale"])
            if param["current_step"] < param["step"]:
                param["current_step"] = param["step"]  # math.pow(10, -param["scale"])
            optimization_setting.add_parameter(name=param["name"], start=param["start"], end=param["end"] + 0.01,
                                               step=param["current_step"])
            pass
        print("param_ranges : %s" % str(param_ranges))
        result_list = engine.run_optimization(optimization_setting)
        best_param_tmp, target_value, statistics = result_list[0]
        best_param = eval(best_param_tmp)
        for key in engine.default_setting:
            if key not in best_param:
                best_param[key] = engine.default_setting[key]
        round_cnt += 1
        win_count = len(
            [target_value for best_param, target_value, statistics in result_list if
             statistics["end_balance"] >= original_capital])
        print("win/lose around the point param : %s/%s" % (win_count, len(result_list) - win_count))
        print("best param for %s (%s) now : %s, sharpe_ratio : %s, target_value : %s" % (
            str(engine.vt_symbol), str(engine.strategy.strategy_name), str(best_param), str(statistics["sharpe_ratio"]),
            str(target_value)))
        need_new_run = False
        for param in param_ranges:
            if param["current_step"] <= param["step"]:
                continue
            param["end"] = min(float(best_param[param["name"]]) + param["current_step"], param["end"])
            param["start"] = max(float(best_param[param["name"]]) - param["current_step"], param["start"])
            need_new_run = True
            pass
        if not need_new_run:
            break
        # 如3次仍无法发现盈利参数，直接结束
        if win_count == 0 and round_cnt >= 3:
            print("no win point is found, stop searching!!!!!!!!!!!!!!!!!!!!")
            break
        if round_cnt >= 8:
            break
    print("total round : %s" % str(round_cnt))
    print("time cost : %s" % str(time.time() - start_time))
    print("statistics : %s" % str(statistics))
    print("end_balance : %s" % str(statistics["end_balance"]))
    print("sharpe_ratio : %s" % str(statistics["sharpe_ratio"]))
    print("annual_return : %s" % str(statistics["annual_return"]))
    print("max_ddpercent : %s" % str(statistics["max_ddpercent"]))
    return best_param


def precision_and_scale(x):
    max_digits = 14
    int_part = int(abs(x))
    magnitude = 1 if int_part == 0 else int(math.log10(int_part)) + 1
    if magnitude >= max_digits:
        return magnitude, 0
    frac_part = abs(x) - int_part
    multiplier = 10 ** (max_digits - magnitude)
    frac_digits = multiplier + int(multiplier * frac_part + 0.5)
    while frac_digits % 10 == 0:
        frac_digits /= 10
    scale = int(math.log10(frac_digits))
    return magnitude + scale, scale


if __name__ == '__main__':
    main()
