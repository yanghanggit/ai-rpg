import requests


def check_process_health(port):
    try:
        response = requests.get(f"http://127.0.0.1:{port}/health")
        return response.status_code == 200
    except Exception:
        return False


# 示例
if not check_process_health(8001):
    print("进程 8001 不健康，重新启动...")
