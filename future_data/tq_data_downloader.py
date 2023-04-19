import datetime

from tqsdk import TqApi, TqAuth
from vnpy.trader.constant import Interval, Exchange
from vnpy.trader.object import BarData

# from util.message_alert import ding_message
from future_data.data_downloader import save_bar
from util.vt_symbol_util import split_vnpy_format

vnpy_frequency = Interval.MINUTE

mapping_rq = {'CFFEX': Exchange.CFFEX,  # 中国金融期货交易所
              'INE': Exchange.INE,  # 上海国际能源交易中心
              'SHFE': Exchange.SHFE,  # 上期所
              'CZCE': Exchange.CZCE,  # 郑商所
              'DCE': Exchange.DCE  # 大商所
              }


def download_from_tq(vt_symbols: list, size: int = 5000):
    if vt_symbols is None or len(vt_symbols) < 1:
        return
    api = None
    try:
        api = TqApi(auth=TqAuth("username", "password"))
        for vt_symbol in vt_symbols:
            exchange, code, month = split_vnpy_format(vt_symbol)
            tq_symbol = "%s.%s%s" % (exchange, code, month)
            symbol = "%s%s" % (code, month)
            if month == '9999':
                tq_symbol = "KQ.m@%s.%s" % (exchange, code)
            if month == '8888':
                tq_symbol = "KQ.i@%s.%s" % (exchange, code)
            klines = api.get_kline_serial(tq_symbol, 60, data_length=size)
            bars = []
            for i in range(len(klines)):
                # print("K线变化", datetime.datetime.fromtimestamp(klines.iloc[i]["datetime"] / 1e9), klines.open.iloc[i],
                #       klines.close.iloc[i], klines.high.iloc[i], klines.low.iloc[i], klines.close_oi.iloc[i])
                bar: BarData = BarData(gateway_name="TQ",
                                       symbol=symbol,
                                       exchange=mapping_rq.get(exchange),
                                       datetime=datetime.datetime.fromtimestamp(klines.iloc[i]["datetime"] / 1e9),
                                       interval=vnpy_frequency,
                                       volume=klines.volume.iloc[i],
                                       open_price=klines.open.iloc[i],
                                       high_price=klines.high.iloc[i],
                                       low_price=klines.low.iloc[i],
                                       close_price=klines.close.iloc[i],
                                       open_interest=klines.close_oi.iloc[i])
                bars.append(bar)
            save_bar(bars)
    except Exception as e:
        # ding_message("天勤下载数据异常,%s" % e)
        raise e
    finally:
        if api:
            api.close()
    pass

