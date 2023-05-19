import json
import re

global_vt_settings = {
    "sizes": {
        "rb8888.SHFE": 10,
        "IF8888.CFFEX": 300,
        "ag8888.SHFE": 15,
        "m8888.DCE": 10,
        "TA8888.CZCE": 5,
        "i8888.DCE": 100,
        "y8888.DCE": 10,
        "au8888.SHFE": 1000,
        "FG8888.CZCE": 20,
        "sc8888.INE": 1000,
        "al8888.SHFE": 5,
        "jm8888.DCE": 60,
        "lh8888.DCE": 16,
        "MA8888.CZCE": 10,
    },
    "rates": {
        "rb8888.SHFE": 0.25 / 10000,
        "IF8888.CFFEX": 0.51 / 10000,
        "ag8888.SHFE": 0.51 / 10000,
        "m8888.DCE": 0.51 / 10000,
        "TA8888.CZCE": 0.51 / 10000,
        "i8888.DCE": 0.51 / 10000,
        "y8888.DCE": 0.51 / 10000,
        "au8888.SHFE": 0.51 / 10000,
        "FG8888.CZCE": 0.51 / 10000,
        "sc8888.INE": 0.51 / 10000,
        "al8888.SHFE": 0.51 / 10000,
        "jm8888.DCE": 0.51 / 10000,
        "lh8888.DCE": 0.51 / 10000,
        "MA8888.CZCE": 0.51 / 10000,
    },
    # 预估滑点，仅在回测时使用
    "slippages": {
        "rb8888.SHFE": 1,
        "IF8888.CFFEX": 0.2,
        "ag8888.SHFE": 1,
        "m8888.DCE": 1,
        "TA8888.CZCE": 2,
        "i8888.DCE": 0.5,
        "y8888.DCE": 2,
        "au8888.SHFE": 0.02,
        "FG8888.CZCE": 2,
        "sc8888.INE": 0.01,
        "al8888.SHFE": 5,
        "jm8888.DCE": 0.5,
        "lh8888.DCE": 5,
        "MA8888.CZCE": 1,
    },
    "deposit_rates": {
        "rb8888.SHFE": 10,
        "IF8888.CFFEX": 12,
        "ag8888.SHFE": 12,
        "m8888.DCE": 10,
        "TA8888.CZCE": 10,
        "i8888.DCE": 10,
        "y8888.DCE": 10,
        "au8888.SHFE": 10,
        "FG8888.CZCE": 10,
        "sc8888.INE": 10,
        "al8888.SHFE": 10,
        "jm8888.DCE": 10,
        "lh8888.DCE": 10,
        "MA8888.CZCE": 10,
    },
    "priceticks": {
        "rb8888.SHFE": 1,
        "IF8888.CFFEX": 0.2,
        "ag8888.SHFE": 1,
        "m8888.DCE": 1,
        "TA8888.CZCE": 2,
        "i8888.DCE": 0.5,
        "y8888.DCE": 2,
        "au8888.SHFE": 0.02,
        "FG8888.CZCE": 2,
        "sc8888.INE": 0.01,
        "al8888.SHFE": 5,
        "jm8888.DCE": 0.5,
        "lh8888.DCE": 5,
        "MA8888.CZCE": 1,
    },
    "vt_relation_arrays": [["rb8888.SHFE", "i8888.DCE", "FG8888.CZCE", "jm8888.DCE"], ["IF8888.CFFEX"],
                           ["ag8888.SHFE", "au8888.SHFE", "al8888.SHFE"],
                           ["m8888.DCE", "y8888.DCE", "lh8888.DCE"],
                           ["TA8888.CZCE", "sc8888.INE", "MA8888.CZCE"]]
}


def _unify_config(fullname_vt_settings=global_vt_settings):
    """移除月份后缀，仅使用期货品种编码即可"""
    json_str = json.JSONEncoder().encode(fullname_vt_settings)
    json_str = re.sub("8888[.].*?\"", "\"", json_str)
    return json.JSONDecoder().decode(json_str)


vt_settings_with_short_code = _unify_config()
