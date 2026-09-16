#!/usr/bin/env python3
"""
Replicate API 连通性检查模块
"""

import os
from typing import Final

import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 常量定义
TEST_URL: Final[str] = "https://api.replicate.com/v1/models"


def check_replicate_connection() -> bool:
    """
    检查 Replicate API 连接
    独立函数，不依赖配置类实例

    Returns:
        bool: 连接成功返回 True，失败返回 False
    """
    api_token = os.getenv("REPLICATE_API_TOKEN")
    if not api_token:
        print("❌ API Token 未配置")
        return False

    headers = {"Authorization": f"Token {api_token}"}

    try:
        print("🔄 测试 Replicate API 连接...")
        response = requests.get(TEST_URL, headers=headers, timeout=10)

        if response.status_code == 200:
            print("✅ 连接成功! Replicate API 可正常访问")
            return True
        else:
            print(f"❌ 连接失败，状态码: {response.status_code}")
            if response.status_code == 401:
                print("💡 API Token 可能无效或已过期")
            return False

    except Exception as e:
        print(f"❌ 连接错误: {e}")
        print("💡 请检查:")
        print("   1. 网络连接是否正常")
        print("   2. API Token 是否有效")
        return False
