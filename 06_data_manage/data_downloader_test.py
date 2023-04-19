from future_data.data_downloader import download_data_from_rq
import time

start = "2022-05-01 00:00:00"
# end = "2016-01-01"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
end = time.strftime(TIME_FORMAT, time.localtime())
# 基本参数
# security_codes = ["MA8888","SA8888","fu8888","m8888","TA8888","i8888","y8888","au8888","FG8888","al8888"]  # XSGE
security_codes = ["TA209.CZCE" ]  # XSGE
if __name__ == '__main__':
    for security_code in security_codes:
        download_data_from_rq(security_code, start, end)
