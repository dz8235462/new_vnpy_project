from vnpy.trader.constant import Exchange

Exchange_mapping = {'CFFEX': Exchange.CFFEX,  # 中国金融期货交易所
                    'INE': Exchange.INE,  # 上海国际能源交易中心
                    'SHFE': Exchange.SHFE,  # 上期所
                    'CZCE': Exchange.CZCE,  # 郑商所
                    'DCE': Exchange.DCE  # 大商所
                    }


def concat_vnpy_format(exchange, code, month):
    VNPY_FORMAT = "%s%s.%s"
    return VNPY_FORMAT % (code, month, exchange)


def concat_tq_format(exchange, code, month):
    TQ_FORMAT = "%s.%s%s"
    return TQ_FORMAT % (exchange, code, month)


def split_vnpy_format(vt_symbol: str):
    """
    :param vt_symbol:
    :return: exchange, code, month
    """
    if vt_symbol is None:
        return None, None, None
    strs = vt_symbol.split(".")
    if len(strs) < 2:
        return None, None, None
    symbol, exchange = strs[0], strs[1]
    last_idx = -1
    while '0' <= symbol[last_idx] <= '9':
        last_idx -= 1
    code = symbol[:last_idx + 1]
    month = symbol[last_idx + 1:]
    return exchange, code, month


def split_tq_format(vt_symbol: str):
    """TQ default format like DCE.i2301 """
    if vt_symbol is None:
        return None, None, None
    strs = vt_symbol.split(".")
    if len(strs) < 2:
        return None, None, None
    exchange, symbol = strs[0], strs[1]
    last_idx = -1
    while '0' <= symbol[last_idx] <= '9':
        last_idx -= 1
    code = symbol[:last_idx + 1]
    month = symbol[last_idx + 1:]
    return exchange, code, month


if __name__ == '__main__':
    print(split_tq_format("DCE.i2301"))
