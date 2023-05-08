import json

import requests


def ding_message(msg: str):
    if msg is None or len(msg) < 1:
        return
        # 请求的URL，WebHook地址
    if msg[0:4] != "vnpy":
        msg = "vnpy %s" % msg
    # 替换此处web hook
    webhook = "https://oapi.dingtalk.com/robot/send?access_token=xxx"
    # 构建请求头部
    header = {
        "Content-Type": "application/json",
        "Charset": "UTF-8"
    }
    # 构建请求数据
    message = {

        "msgtype": "text",
        "text": {
            "content": msg
        },
        "at": {

            "isAtAll": True
        }

    }
    # 对请求的数据进行json封装
    message_json = json.dumps(message)
    # 发送请求
    info = requests.post(url=webhook, data=message_json, headers=header)
    # 打印返回的结果
    print(info.text)


if __name__ == "__main__":
    ding_message('vnpy 测试方法')
