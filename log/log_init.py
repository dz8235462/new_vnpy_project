import logging
import logging.config
import os

import yaml


def load_config():
    """加载日志配置"""
    with open(os.path.dirname(__file__) + '/log_config.yaml', 'r') as f:
        config = yaml.safe_load(f.read())
        # config.get("handlers")
        logging.config.dictConfig(config)


def get_logger(logger_name: str = "main"):
    """获取日志对象"""
    load_config()
    logger_inner = logging.getLogger(logger_name)
    return logger_inner


if __name__ == '__main__':
    logger = get_logger()
    logger.info("test")
