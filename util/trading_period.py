from datetime import datetime, time

TRADE_DAY_START_1 = time(9, 00)
TRADE_DAY_END_1 = time(11, 31)

TRADE_DAY_START_2 = time(13, 30)
TRADE_DAY_END_2 = time(15, 1)

TRADE_NIGHT_START = time(21, 00)
TRADE_NIGHT_END = time(2, 31)


def check_real_trading_period(current: datetime = None):
    """"""
    current_time = datetime.now().time()
    if current is not None:
        current_time = current.time()

    trading = False
    if (
            (TRADE_DAY_START_1 <= current_time <= TRADE_DAY_END_1)
            or (TRADE_DAY_START_2 <= current_time <= TRADE_DAY_END_2)
            or (TRADE_NIGHT_START <= current_time)
            or (current_time <= TRADE_NIGHT_END)
    ):
        trading = True

    return trading
