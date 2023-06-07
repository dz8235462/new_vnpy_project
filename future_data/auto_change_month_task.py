import multiprocessing
from datetime import datetime, time
from datetime import timedelta

from peewee import fn
from vnpy_ctastrategy import CtaEngine
from vnpy_mysql.mysql_database import DbBarData
from vnpy.trader.utility import load_json, save_json
from vnpy_portfoliostrategy import StrategyEngine

from log.log_init import get_logger
from util.main_contract_detector import get_main_contract
from util.message_alert import ding_message
from util.vt_symbol_util import split_vnpy_format

logger = get_logger()
logger.info("test")

KEY_POS = "pos"
KEY_CAPITAL = "capital"
KEYS_UNCHANGEABLE = [KEY_POS, KEY_CAPITAL, "vt_used_capital", "vt_used_unit"]


class AutoChangeMonthConfig:

    def __init__(self, settings_file_path=None, data_file_path=None, day_limit=None):
        self.settings_file_path = settings_file_path
        self.data_file_path = data_file_path
        self.day_limit = day_limit


def get_change_month_for_cta_test():
    config = AutoChangeMonthConfig(settings_file_path="test_" + CtaEngine.setting_filename,
                                   data_file_path="test_" + CtaEngine.data_filename, day_limit=6)
    cta_task = AutoChangeMonthTask(
        times=[time(6, 0)], config=config
    )
    return cta_task


def get_change_month_for_portfolio_test():
    config = AutoChangeMonthConfig(settings_file_path="test_" + StrategyEngine.setting_filename,
                                   data_file_path="test_" + StrategyEngine.data_filename, day_limit=11)
    cta_task = AutoChangeMonthTask(
        times=[time(6, 0)], config=config
    )
    return cta_task


def get_change_month_for_cta():
    config = AutoChangeMonthConfig(settings_file_path=CtaEngine.setting_filename,
                                   data_file_path=CtaEngine.data_filename, day_limit=6)
    cta_task = AutoChangeMonthTask(
        times=[time(6, 0)], config=config
    )
    return cta_task


def get_change_month_for_portfolio():
    config = AutoChangeMonthConfig(settings_file_path=StrategyEngine.setting_filename,
                                   data_file_path=StrategyEngine.data_filename, day_limit=11)
    cta_task = AutoChangeMonthTask(
        times=[time(17, 30)],
        config=config)
    return cta_task


def run_child(config: AutoChangeMonthConfig):
    try:
        strategy_settings = load_json(config.settings_file_path)
        data_json = load_json(config.data_file_path)
        vt_symbols = set()
        for strategy_name in strategy_settings:
            setting = strategy_settings[strategy_name]
            if "vt_symbol" in setting and setting["vt_symbol"] not in vt_symbols:
                vt_symbols.add(setting["vt_symbol"])
            if "vt_symbols" in setting:
                for vt_symbol in setting["vt_symbols"]:
                    vt_symbols.add(vt_symbol)
            # print(strategy_name)
            logger.info(setting)
        new_main_contracts = get_main_contract(vt_symbols, include_the_same=False)
        logger.info(new_main_contracts)
        if len(new_main_contracts) <= 0:
            logger.info("no change")
            return
        # 修改数据
        ding_message("执行合约换月,new_main_contracts=%s" % new_main_contracts)
        logger.info("===========start change month=============")
        need_save = False
        for strategy_name in strategy_settings:
            setting = strategy_settings[strategy_name]
            strategy_data = {}
            if strategy_name in data_json:
                strategy_data = data_json[strategy_name]
            # cta
            if "vt_symbol" in setting:
                changed, _setting, _data = change_settings_of_cta(strategy_name, setting, strategy_data,
                                                                  new_main_contracts, config)
                if changed:
                    need_save = True
                    strategy_settings[strategy_name] = _setting
                    data_json[strategy_name] = _data
            # portfolio
            if "vt_symbols" in setting:
                changed, _setting, _data = change_settings_of_portfolio(strategy_name, setting, strategy_data,
                                                                        new_main_contracts,
                                                                        config)
                if changed:
                    need_save = True
                    strategy_settings[strategy_name] = _setting
                    data_json[strategy_name] = _data
        if not need_save:
            logger.info("no need to change data")
            return
        logger.info(strategy_settings)
        logger.info(data_json)
        # save
        save_json(config.settings_file_path, strategy_settings)
        save_json(config.data_file_path, data_json)
    except (Exception, RuntimeError) as e:
        logger.error(e, stack_info=True, exc_info=True)


def change_settings_of_cta(strategy_name, strategy_setting, strategy_data, new_main_contracts, config) \
        -> [bool, dict, dict]:
    current_vt_symbol = strategy_setting["vt_symbol"]
    if current_vt_symbol not in new_main_contracts:
        return False, strategy_setting, strategy_data
    new_vt_symbol = new_main_contracts[current_vt_symbol]
    exchange, symbol, month = split_vnpy_format(new_vt_symbol)
    days = get_days_of_bar_data(symbol + month)
    logger.info("days of new_vt_symbol %s is %s" % (new_vt_symbol, days))
    if days <= config.day_limit:
        return False, strategy_setting, strategy_data
    # cta策略等待平仓后再换月
    pos = get_pos_of_strategy_data_cta(strategy_data)
    if pos != 0:
        logger.info("strategy %s has pos = %s" % (strategy_name, pos))
        return False, strategy_setting, strategy_data
    # 开始修改数据
    logger.info("start update setting %s, %s to %s" % (strategy_name, strategy_setting["vt_symbol"], new_vt_symbol))
    strategy_setting["vt_symbol"] = new_vt_symbol
    keys = [k for k in strategy_data]
    for key in keys:
        if key == KEY_POS or key == KEY_CAPITAL:
            continue
        strategy_data.pop(key)
    return True, strategy_setting, strategy_data


def get_pos_of_strategy_data_cta(strategy_data):
    if KEY_POS in strategy_data:
        return int(strategy_data[KEY_POS])
    return 0


def get_pos_of_strategy_data_portfolio(strategy_data, vt_symbol):
    if KEY_POS in strategy_data:
        pos = strategy_data[KEY_POS]
        if vt_symbol in pos:
            return int(pos[vt_symbol])
    return 0


def change_settings_of_portfolio(strategy_name, strategy_setting, strategy_data, new_main_contracts, config):
    current_vt_symbols = [v for v in strategy_setting["vt_symbols"]]
    changed = False
    for current_vt_symbol in current_vt_symbols:
        if current_vt_symbol not in new_main_contracts:
            continue
        new_vt_symbol = new_main_contracts[current_vt_symbol]
        exchange, symbol, month = split_vnpy_format(new_vt_symbol)
        short_vt_symbol = symbol + month
        days = get_days_of_bar_data(short_vt_symbol)
        logger.info("days of new_vt_symbol %s is %s" % (new_vt_symbol, days))
        if days <= config.day_limit:
            continue
        pos = get_pos_of_strategy_data_portfolio(strategy_data, current_vt_symbol)
        # 开始修改数据
        changed = True

        logger.info("start update setting %s, %s to %s" % (strategy_name, current_vt_symbol, new_vt_symbol))
        if pos == 0:
            strategy_setting["vt_symbols"].remove(current_vt_symbol)
        new_exist = new_vt_symbol in strategy_setting["vt_symbols"]
        if not new_exist:
            strategy_setting["vt_symbols"].append(new_vt_symbol)
        if pos == 0 and current_vt_symbol in strategy_data[KEY_POS]:
            strategy_data[KEY_POS].pop(current_vt_symbol)
        if new_exist:
            continue
        keys = [k for k in strategy_data]
        for key in keys:
            if key in KEYS_UNCHANGEABLE:
                continue
            data = strategy_data[key]
            if symbol in data:
                data.pop(symbol)
            if short_vt_symbol in data:
                data.pop(short_vt_symbol)
        if "Turtle" == strategy_name:
            strategy_data["use_new_donchian"][symbol] = True
    return changed, strategy_setting, strategy_data


def get_days_of_bar_data(symbol) -> int:
    """return days of vt_symbol, to determine whether to change code used in strategies"""
    query = DbBarData.select(fn.count(fn.left(DbBarData.datetime, 10).distinct())) \
        .where(DbBarData.symbol == symbol)
    days = query.scalar()
    print(query)
    # print(days)
    return days


class AutoChangeMonthTask:
    """
    自动换月工具
    定期读取各策略配置文件，如发现主力合约已换，根据新合约数据是否满足一定天数触发换月
    """

    def __init__(self, times=[], config: AutoChangeMonthConfig = None):
        self.done = False
        self.times = times if times is not None else []
        self.config = config

    def auto_change_month(self):
        try:
            now = datetime.now()
            if self.config is None:
                logger.info("self.settings_file_path is None")
                return
            in_time_period = False
            for t in self.times:
                if now.time() >= t >= (now - timedelta(minutes=10)).time():
                    in_time_period = True
                    break
            if not in_time_period:
                self.done = False
                # self.logger.info("not in_time_period")
                return
            if self.done:
                # self.logger.info("self.done")
                return
            child_process = multiprocessing.Process(target=run_child,
                                                    args=(self.config,))
            child_process.start()
            child_process.join()
            self.done = True
        except Exception as e:
            logger.error(e, stack_info=True, exc_info=True)


if __name__ == '__main__':
    task = get_change_month_for_cta_test()
    task.times.append(datetime.now().time())
    task.auto_change_month()
    print(task.done)
    # task = get_instance_for_portfolio()
    # task.times.append(datetime.now().time())
    # task.auto_change_month()
    # task.auto_change_month()
    # get_days_of_bar_data("rb2301")
