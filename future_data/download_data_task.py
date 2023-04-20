import enum
import multiprocessing
import sys
from datetime import datetime, time
from datetime import timedelta

from vnpy_ctastrategy import CtaStrategyApp
from vnpy_portfoliostrategy import PortfolioStrategyApp
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.utility import load_json
from vnpy_ctp import CtpGateway

from log.log_init import get_logger
from future_data.data_downloader import download_data
from future_data.tq_data_downloader import download_from_tq
# from util.main_contract_detector import check_all_symbol_main_contract
# from util.message_alert import ding_message

logger = get_logger()


class ApiSource(enum.Enum):
    """
    source of data API
    """
    TQ = "TQ"
    RQ = "RQ"
    JQ = "JQ"


API_SOURCE = ApiSource.TQ
DAY_OPEN = time(9, 0)
NIGHT = time(21, 0)


def get_instance_for_manual():
    """手动下载各种主力和指数连续"""
    vt_symbols = ["rb9999.SHFE", "FG9999.CZCE", "RM9999.CZCE", "IF9999.CFFEX", "TF9999.CFFEX","i9999.DCE",
                  "y9999.DCE", "PK9999.CZCE", "j9999.DCE", "au9999.SHFE", "hc9999.SHFE", "TA9999.CZCE", "MA9999.CZCE",
                  "fu9999.SHFE", "AP9999.CZCE", "ag9999.SHFE", "bu9999.SHFE", "m9999.DCE", "SA9999.CZCE", "sc9999.INE",
                  "T9999.CFFEX", "al9999.SHFE", "jm9999.DCE", "lh9999.DCE", "FG8888.CZCE", "RM8888.CZCE",
                  "rb8888.SHFE", "IF8888.CFFEX",
                  "TF8888.CFFEX","i8888.DCE",
                  "y8888.DCE", "PK8888.CZCE", "j8888.DCE", "au8888.SHFE", "hc8888.SHFE", "TA8888.CZCE", "MA8888.CZCE",
                  "fu8888.SHFE", "AP8888.CZCE", "ag8888.SHFE", "bu8888.SHFE", "m8888.DCE", "SA8888.CZCE", "sc8888.INE",
                  "T8888.CFFEX", "al8888.SHFE", "jm8888.DCE", "lh8888.DCE",
                  "IC9999.CFFEX","IH9999.CFFEX","IC8888.CFFEX","IH8888.CFFEX"]
    cta_task = DownloadDataTask(times=[time(15, 30), time(3, 45)], vt_symbols=vt_symbols)
    cta_task.default_download_size = 2000
    cta_task.download_new_main_contract = False
    return cta_task


def get_instance_for_cta():
    """下载cta策略的数据"""
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(CtpGateway)
    cta_engine = main_engine.add_app(CtaStrategyApp)
    # cta_task = DownloadDataTask(times=[time(9, 2), time(13, 31), time(21, 1), time(15, 6), time(3, 26), time(8, 46)],
    #                             engine=cta_engine)
    cta_task = DownloadDataTask(times=[time(9, 2), time(12, 45), time(20, 45), time(15, 5), time(3, 35), time(7, 45)],
                                engine=cta_engine)
    return cta_task


def get_instance_for_portfolio():
    """下载组合策略的数据"""
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(CtpGateway)
    cta_engine = main_engine.add_app(PortfolioStrategyApp)
    portfolio_cta_task = DownloadDataTask(times=[time(12, 15), time(17, 15), time(3, 15), time(8, 35)], engine=cta_engine)
    return portfolio_cta_task


def run_child(vt_symbols, download_size, download_new_main_contract):
    try:
        while True:
            now = datetime.now()
            logger.info("-------------start download-------------")
            if API_SOURCE == ApiSource.TQ:
                download_for_day_open = now.time() >= DAY_OPEN >= (now - timedelta(minutes=30)).time()
                size = 30 if download_for_day_open else download_size
                logger.info("-------------start download TQ-------------")
                download_from_tq(vt_symbols, size=size)
                logger.info("-------------end download TQ-------------")
                # if not download_for_day_open and download_new_main_contract:
                #     logger.info("-------------start download new main contract TQ-------------")
                #     new_codes, existed_new_codes = check_all_symbol_main_contract(vt_symbols)
                #     if len(new_codes) > 0:
                #         download_from_tq(new_codes, size=8000)
                #     if len(existed_new_codes) > 0:
                #         download_from_tq(existed_new_codes, size=download_size)
                #     in_daytime = DAY_OPEN <= now.time() <= NIGHT
                #     if in_daytime and (len(new_codes) > 0 or len(existed_new_codes) > 0):
                #         ding_message("合约换月,new_codes=%s,existed_new_codes=%s" % (new_codes, existed_new_codes))
                #     logger.info("-------------end download new main contract TQ-------------")
            else:
                for security_code in vt_symbols:
                    download_data(security_code,
                                  end_date=now)
            break
    except (Exception, RuntimeError) as e:
        logger.error(e, stack_info=True, exc_info=True)


class DownloadDataTask:
    """定时下载数据任务"""

    def __init__(self, times=[], engine=None, vt_symbols=[]):
        # 记录当前时间点是否已经下载
        self.done = False
        # 需要触发下载的时间点，支持多个
        self.times = times if times is not None else []
        # 支持传入vnpy的ctaEngine，用于读取对应配置文件
        self.engine = engine
        # 支持手动配置合约，如自动下载需要的主力连续或指数连续合约
        self.vt_symbols = vt_symbols
        # 每次从接口中下载的数据量，视调用频率而定，如每天下载一次，1000数据已可以覆盖一到两天
        self.default_download_size = 1000
        # 是否需要检测并自动下载新的主力合约
        self.download_new_main_contract = True

    def download(self):
        try:
            # 获取当前时间
            now = datetime.now()
            # 无需要下载的内容
            if self.engine is None and len(self.vt_symbols) < 1:
                logger.info("self.engine is None and self.vt_symbols is empty")
                return
            # 判断当前时间是否处于某个任务时间开始的10分钟之内，即当前时刻需要下载数据
            in_time_period = False
            for t in self.times:
                if now.time() >= t >= (now - timedelta(minutes=10)).time():
                    in_time_period = True
                    break
            # 非下载任务时间，将done标记重置
            if not in_time_period:
                self.done = False
                # self.logger.info("not in_time_period")
                return
            # 下载任务时间，但已执行过下载则忽略
            if self.done:
                # self.logger.info("self.done")
                return
            # copy配置项，避免添加配置文件中的选项后导致数组无限增加
            vt_symbols = self.vt_symbols[:]
            # 根据engine读取对应的配置文件并添加到待下载列表
            if self.engine is not None:
                strategy_setting = load_json(self.engine.setting_filename)
                for strategy_name, strategy_config in strategy_setting.items():
                    if "vt_symbol" in strategy_config and strategy_config["vt_symbol"] not in vt_symbols:
                        vt_symbols.append(strategy_config["vt_symbol"])
                    if "vt_symbols" in strategy_config:
                        for vt_symbol in strategy_config["vt_symbols"]:
                            if vt_symbol not in vt_symbols:
                                vt_symbols.append(vt_symbol)
            if len(vt_symbols) < 1:
                logger.info("len(vt_symbols) < 1")
                return
            # 开启子进程单独下载。因tqsdk是一个阻塞api，如在当前进程开启，流程会被挂起
            logger.info("start download, vts= %s" % vt_symbols)
            child_process = multiprocessing.Process(target=run_child, args=(
                vt_symbols, self.default_download_size, self.download_new_main_contract))
            child_process.start()
            # 等待子进程结束，确保下载数据完成再执行策略启动等动作
            child_process.join()
            self.done = True
        except Exception as e:
            logger.error(e, stack_info=True, exc_info=True)

    def close(self):
        # 关闭engine等资源
        if self.engine is not None and self.engine.main_engine is not None:
            self.engine.main_engine.close()
        sys.exit(0)


if __name__ == '__main__':
    task = get_instance_for_cta()
    # 为时间列表添加当前时间，测试是否立即下载数据
    task.times.append(datetime.now().time())
    task.download()
    print(task.done)
    task.download()
    task.close()
