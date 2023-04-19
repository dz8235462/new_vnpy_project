import logging

import pytz

from log.log_init import get_logger
import time
from datetime import datetime

from vnpy.trader.database import (database,get_database)  # 重要，需要此步骤加载vnpy的数据库管理器
from vnpy_mysql.mysql_database import DbBarOverview, db
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData, HistoryRequest
from vnpy_rqdata.rqdata_datafeed import RqdataDatafeed
from vnpy.trader.setting import SETTINGS

from util.vt_symbol_util import split_vnpy_format

logger = get_logger()


mapping_rq = {'CFFEX': Exchange.CFFEX,  # 中国金融期货交易所
              'INE': Exchange.INE,  # 上海国际能源交易中心
              'SHFE': Exchange.SHFE,  # 上期所
              'CZCE': Exchange.CZCE,  # 郑商所
              'DCE': Exchange.DCE  # 大商所
              }

start = "2022-05-01 00:00:00"
# end = "2016-01-01"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
end = time.strftime(TIME_FORMAT, time.localtime())
frequency = '1m'
vnpy_frequency = Interval.MINUTE
USE_RQ = False


def download_data(vt_symbol, start_date=start, end_date=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())):
    if USE_RQ:
        download_data_from_rq(vt_symbol,start_date,end_date)


def save_bar(bars):
    if bars is None or len(bars) < 1:
        return
    database = get_database()
    batch_size = 200
    start_idx = 0
    while start_idx < len(bars):
        end_idx = start_idx + batch_size
        if end_idx > len(bars):
            end_idx = len(bars)
        sub_list = bars[start_idx:end_idx]
        if len(sub_list) > 0:
            print(sub_list[-1])
            database.save_bar_data(sub_list)
        print("data saved, start= %s, total =%s" % (start_idx, len(bars)))
        logger.info("data saved, start= %s, total =%s" % (start_idx, len(bars)))
        start_idx += batch_size
        pass
    pass


def download_data_from_rq(vt_symbol, start_date=start, end_date=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())):
    exchange, symbol, month = split_vnpy_format(vt_symbol)
    exchange_code = exchange
    assert exchange_code in mapping_rq
    exchange = mapping_rq.get(exchange_code)
    if exchange == Exchange.CZCE and month != "9999" and month != "8888":
        # 郑商所月份仅有3位，为兼容将4位转为3位
        security_code_inner = symbol + month[-3:]
    logger.info('security_code= %s' % security_code_inner)
    database = get_database()
    # database.db.connect(reuse_if_open=True)
    with db.atomic():
        # database.db.ping(reconnect=True)
        overview: DbBarOverview = DbBarOverview.get_or_none(
            DbBarOverview.symbol == security_code,
            DbBarOverview.exchange == exchange.value,
            DbBarOverview.interval == vnpy_frequency.value,
        )
        logger.info('DbBarOverview= %s' % overview)
        if overview is not None:
            # 仅可处理向后新增的数据，如处理历史数据，可直接删除overview
            start_date = overview.end
            logger.info("start_date changed, new=%s" % start_date)
        # 兼容早期版本vnpy
        SETTINGS["rqdata.username"] = SETTINGS["datafeed.username"] = "xxxxx"
        SETTINGS["rqdata.password"] = SETTINGS["datafeed.password"] = "xxxxx"
        rqClient = RqdataDatafeed()
        rqClient.init()
        start_date = datetime.strptime(start_date, TIME_FORMAT) if type(start_date) == str else start_date
        end_date = datetime.strptime(end_date, TIME_FORMAT) if type(end_date) == str else end_date
        print("start_date=%s" % start_date)
        print("end_date=%s" % end_date)
        req = HistoryRequest(symbol=security_code, exchange=exchange,
                             start=start_date, end=end_date,
                             interval=vnpy_frequency)
        data_list = rqClient.query_bar_history(req)
        if data_list is None or len(data_list) < 1:
            logger.error("none data returned")
            return
        logger.info("start_date=%s" % start_date.replace(tzinfo=pytz.timezone("Etc/GMT-8")))
        logger.info(data_list[-1].datetime)
        if len(data_list) < 1:
            logger.error("all data saved")
            return
        logger.info("new_start_data=%s" % data_list[0].datetime)
        save_bar(data_list)
        pass


# 基本参数
# security_codes = ["MA8888","SA8888","fu8888","m8888","TA8888","i8888","y8888","au8888","FG8888","al8888"]  # XSGE
security_codes = ["TA209.CZCE" ]  # XSGE
if __name__ == '__main__':
    for security_code in security_codes:
        download_data_from_rq(security_code, start, end)
