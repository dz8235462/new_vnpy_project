import multiprocessing
import sys
from datetime import datetime, time
from logging import INFO
from time import sleep

# import pandas as pd
from vnpy_ctastrategy import CtaStrategyApp
from vnpy_ctastrategy.base import EVENT_CTA_LOG
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.setting import SETTINGS
from vnpy_ctp import CtpGateway

from future_data.auto_change_month_task import get_change_month_for_cta
from future_data.download_data_task import get_instance_for_cta, get_instance_for_manual
from util.message_alert import ding_message
from util.trading_period import check_real_trading_period

SETTINGS["log.active"] = True
SETTINGS["log.level"] = INFO
SETTINGS["log.console"] = True


ctp_test_setting = {
    "用户名": "xxxx",
    "密码": "xxxx",
    "经纪商代码": "9999",
    "交易服务器": "180.168.146.187:10202",
    "行情服务器": "180.168.146.187:10212",
    "产品名称": "simnow_client_test",
    "授权编码": "0000000000000000",
    "产品信息": ""
}


# # Chinese futures market trading period (day/night)
DAY_START_1 = time(9, 2)
DAY_END_1 = time(15, 1)

NIGHT_START = time(20, 58)
NIGHT_END = time(23, 1)


def check_trading_period(current=None):
    """判断当前时间是否是交易时间"""
    if current is None:
        current = datetime.now()
    current_time = current.time()
    today = current.weekday() + 1

    trading = False
    if (
            (today < 6 and DAY_START_1 <= current_time <= DAY_END_1)
            or (today < 6 and NIGHT_START <= current_time <= NIGHT_END)
    ):
        trading = True

    return trading


def run_child():
    """
    使用单独进程运行交易服务启动，便于通过主进程强制结束。
    以下代码除账号信息外，基本为固定写法。此示例为vnpy官方示例改造而来。
    """
    SETTINGS["log.file"] = True
    print("start run_child")
    # ding_message('start run_child %s'% datetime.now())
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    # 设置使用ctp网关和cta应用
    main_engine.add_gateway(CtpGateway)
    cta_engine = main_engine.add_app(CtaStrategyApp)
    main_engine.write_log("主引擎创建成功")

    log_engine = main_engine.get_engine("log")
    event_engine.register(EVENT_CTA_LOG, log_engine.process_log_event)
    main_engine.write_log("注册日志事件监听")
    # 输入账号信息
    main_engine.connect(ctp_test_setting, "CTP")

    main_engine.write_log("连接CTP接口")

    sleep(10)

    cta_engine.init_engine()
    main_engine.write_log("CTA策略初始化完成")
    print("start init_all")

    cta_engine.init_all_strategies()
    sleep(100)  # Leave enough time to complete strategy initialization
    main_engine.write_log("CTA策略全部初始化")

    cta_engine.start_all_strategies()
    main_engine.write_log("CTA策略全部启动")
    sleep(10)

    while True:
        trading = check_trading_period()
        if check_real_trading_period():
            for strategy_name in cta_engine.strategies:
                strategy = cta_engine.strategies[strategy_name]
                if not strategy.trading or not strategy.connected:
                    print("!!!!!!!!!!!!!!!!ERROR!!!!!!!!!!!!!!!!!!!")
                    ding_message('vnpy服务启动异常，策略启动异常%s' % strategy_name)
                    trading = False
                    break
        # 非交易时间停止服务
        if not trading:
            print("关闭子进程")
            main_engine.close()
            sys.exit(0)
        # 每30秒判断以下是否仍在交易时间
        sleep(30)


def run_parent():
    """
    Running in the parent process.
    """
    print("启动CTA策略守护父进程")
    # 添加数据下载任务
    task = get_instance_for_cta()
    task2 = get_instance_for_manual()
    task3 = get_change_month_for_cta()
    child_process = None

    while True:
        # check for download
        task.download()
        task2.download()
        task3.auto_change_month()

        trading = check_trading_period()

        # Start child process in trading period
        if trading and (child_process is None or not child_process.is_alive()):
            print("parent启动子进程")
            child_process = multiprocessing.Process(target=run_child)
            child_process.start()
            print("parent子进程启动成功")

        # 非记录时间则退出子进程
        if not trading and child_process is not None:
            try:
                # child_process.join()
                # 延迟300秒强制关闭子进程。避免因文件句柄被锁等场景导致的子进程阻塞。
                # 需要延迟执行，避免子进程尚未完全执行结束时被杀死。
                sleep(300)
                child_process.terminate()
                # child_process.close()
                if not child_process.is_alive():
                    child_process = None
                    print("parent子进程关闭成功")
            except Exception as e:
                print("child_process.close() failed", e)
        sleep(5)


if __name__ == "__main__":
    run_parent()
