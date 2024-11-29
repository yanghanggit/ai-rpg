import socket


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# 动态分配端口
port = find_free_port()
print(f"分配到的空闲端口是: {port}")
