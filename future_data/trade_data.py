import time
from vnpy.trader.database import (database,get_database)  # 重要，需要此步骤加载vnpy的数据库管理器
from vnpy_mysql.mysql_database import db
from datetime import datetime
from enum import Enum

from vnpy.trader.constant import Exchange, Direction, Offset
from peewee import (
    AutoField,
    CharField,
    DateTimeField,
    FloatField, IntegerField,
    Model,
    MySQLDatabase as PeeweeMySQLDatabase,
    ModelSelect,
    ModelDelete,
    chunked,
    fn, Desc
)
from vnpy.trader.constant import Exchange, Direction, Offset
from vnpy.trader.object import TradeData


class TradeStatus(Enum):
    """
    未平仓1，已平仓2
    """
    UN_CLOSED = 1
    CLOSED = 2


class DbTradeData(Model):
    """交易记录"""

    id = AutoField()
    # 策略名称
    strategy_name: str = CharField()
    # 成交后资金量
    capital: float = FloatField()
    # gateway engine的名称
    gateway_name: str = CharField()
    # 期货合约编码
    symbol: str = CharField()
    # 交易所编码
    exchange: str = CharField()
    # 下单指令id
    orderid: str = CharField()
    # 交易id
    tradeid: str = CharField()
    # 交易方向 LONG SHORT
    direction: str = CharField()
    # 平仓开仓 OPEN CLOSE 或CLOSETODAY
    offset: str = CharField()
    # 成交价
    price: float = FloatField()
    # 成交量
    volume: int = IntegerField()
    # 已平仓手数
    closed_volume: int = IntegerField()
    # 状态 1未平仓2已平仓
    status: int = IntegerField()
    # 交易时间
    datetime: datetime = DateTimeField()

    class Meta:
        database = db
        indexes = ((("strategy_name", "tradeid"), False),)


# def get_last_trade(strategy_name: str, symbol: str, direction: str):
#     # database=get_database()
#     # database.db.connect(reuse_if_open=True)
#     with db.atomic():
#         results = DbTradeData.select().where(
#             DbTradeData.strategy_name == strategy_name
#             , DbTradeData.symbol == symbol
#             , DbTradeData.direction == direction
#             , DbTradeData.offset == Offset.OPEN.name).order_by(
#             DbTradeData.datetime.desc()).limit(1)
#         if results is not None and len(results) > 0:
#             return results.get()
#     return None
#     pass
#
#
# def get_last_trade2(strategy_name: str, symbol: str, direction: str, offset: Offset):
#     with db.atomic():
#         results = DbTradeData.select().where(
#             DbTradeData.strategy_name == strategy_name
#             , DbTradeData.symbol == symbol
#             , DbTradeData.direction == direction
#             , DbTradeData.offset % ("%s%%" % offset.name)).order_by(
#             DbTradeData.datetime.desc()).limit(1)
#         if results is not None and len(results) > 0:
#             return results.get()
#     return None
#     pass
#
#
def get_unclosed_trades(strategy_name: str, symbol: str, direction: str):
    """获取所有未完全平仓的数据"""
    # database=get_database()
    # database.db.connect(reuse_if_open=True)
    with db.atomic():
        results = DbTradeData.select().where(
            DbTradeData.strategy_name == strategy_name
            , DbTradeData.symbol == symbol
            , DbTradeData.direction == direction
            , DbTradeData.status == TradeStatus.UN_CLOSED.value
            , DbTradeData.offset == Offset.OPEN.name).order_by(
            DbTradeData.datetime.asc())
        size = len(results)
        if size > 0:
            data = results.peek(n=size)
            return [data] if size == 1 else data
    return []
    pass


def save_trade_data(strategy_name: str, capital: float, trade: TradeData, use_local_time=False):
    """
    储存数据
    :param strategy_name: 策略名称
    :param capital: 交易后资金量
    :param trade: vnpy的trade数据
    :param use_local_time: 是否使用本地时间，回测时建议使用数据虚拟时间
    :return:
    """
    # 获取数据库并重新连接
    database=get_database()
    database.db.connect(reuse_if_open=True)
    db_trade_data: DbTradeData = DbTradeData()
    db_trade_data.strategy_name = strategy_name
    db_trade_data.capital = capital
    db_trade_data.gateway_name = trade.gateway_name
    db_trade_data.symbol = trade.symbol + '.' + trade.exchange.value
    db_trade_data.exchange = trade.exchange.value
    db_trade_data.orderid = trade.orderid
    db_trade_data.tradeid = trade.tradeid
    db_trade_data.direction = trade.direction.name
    db_trade_data.offset = trade.offset.name
    db_trade_data.price = trade.price
    db_trade_data.volume = trade.volume
    db_trade_data.closed_volume = trade.closed_volume
    db_trade_data.status = TradeStatus.UN_CLOSED.value if trade.offset == Offset.OPEN else TradeStatus.CLOSED.value
    db_trade_data.datetime = datetime.now() if use_local_time else trade.datetime
    with database.db.atomic():
        db_trade_data.save()
    pass


def update_db_trade_data(db_trade_data: DbTradeData):
    # database=get_database()
    # database.db.connect(reuse_if_open=True)
    with db.atomic():
        db_trade_data.save()
    pass


if __name__ == '__main__':
    # 初始化表结构
    database = get_database()
    database.db.create_tables([DbTradeData])
    pass
