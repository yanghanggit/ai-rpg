import requests
from ws_config import WS_CONFIG


# 定义请求的URL
url = f"http://{WS_CONFIG.Host.value}:{WS_CONFIG.Port.value}/process/"

# 要发送的数据
data = {"message": "你好，服务器！"}


if __name__ == "__main__":
    # 发送POST请求
    response = requests.post(url, json=data)

    # 输出服务器的响应
    print("服务器响应：", response.json())
