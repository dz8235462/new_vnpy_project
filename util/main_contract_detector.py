from tqsdk import TqApi, TqAuth

from config.account_config import AccountConfig
from util.message_alert import ding_message
from util.vt_symbol_util import split_vnpy_format, split_tq_format, concat_vnpy_format


def check_current_main_contract(vnpy_format_vt_symbol_now: str, tq_api: TqApi):
    """:returns current_main_contract, input param is current_main_contract, whether this change happens today"""
    vt_symbol = vnpy_format_vt_symbol_now
    exchange, code, month = split_vnpy_format(vt_symbol)
    n = 10
    tq_internal_main_vt_symbol = "KQ.m@%s.%s" % (exchange, code)
    df = tq_api.query_his_cont_quotes(symbol=[tq_internal_main_vt_symbol], n=n)
    origin_tq_vt_symbol = df.iloc[n - 1][tq_internal_main_vt_symbol]
    exchange, code, month = split_tq_format(origin_tq_vt_symbol)
    vnpy_format_vt_symbol = concat_vnpy_format(exchange, code, month)
    # print(vnpy_format_vt_symbol)
    # count to show current main contract changes the first time
    count = df[tq_internal_main_vt_symbol].value_counts()[origin_tq_vt_symbol]
    # this param is used to recommend the k-line downloader to get a large size of data for init
    change_of_first_time = count <= 5
    is_the_same = vnpy_format_vt_symbol_now == vnpy_format_vt_symbol
    # print(count)
    return vnpy_format_vt_symbol, is_the_same, change_of_first_time


def get_main_contract(vt_symbols, include_the_same=False):
    tq_api = TqApi(auth=TqAuth(AccountConfig.tq_acct, AccountConfig.tq_pass))
    try:
        main_contract_map = {}
        for vt_symbol in vt_symbols:
            new_main_contract_vt_symbol, is_the_same, change_of_first_time = check_current_main_contract(vt_symbol,
                                                                                                         tq_api)
            if is_the_same and not include_the_same:
                continue
            main_contract_map[vt_symbol] = new_main_contract_vt_symbol
    except Exception as e:
        ding_message("get_main_contract异常,%s" % e)
        raise e
    finally:
        tq_api.close()
    return main_contract_map


def check_all_symbol_main_contract(vt_symbols):
    tq_api = TqApi(auth=TqAuth(AccountConfig.tq_acct, AccountConfig.tq_pass))
    try:
        new_codes = []
        existed_new_codes = []
        for vt_symbol in vt_symbols:
            vnpy_format_vt_symbol, is_the_same, change_of_first_time = check_current_main_contract(vt_symbol, tq_api)
            if is_the_same:
                continue
            if change_of_first_time:
                new_codes.append(vnpy_format_vt_symbol)
            else:
                existed_new_codes.append(vnpy_format_vt_symbol)
    except Exception as e:
        ding_message("check_all_symbol_main_contract异常,%s" % e)
        raise e
    finally:
        tq_api.close()
    return new_codes, existed_new_codes


if __name__ == '__main__':
    api = TqApi(auth=TqAuth(AccountConfig.tq_acct, AccountConfig.tq_pass))
    print(check_current_main_contract("i2212.DCE", tq_api=api))
    api.close()
    print(check_all_symbol_main_contract(["i2212.DCE", "rb2301.SHFE"]))
