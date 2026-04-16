"""
直接调用 DeepSeek API 测试脚本（不依赖 langchain/langgraph）
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

    url = "https://api.deepseek.com/chat/completions"

    payload = {
        "messages": [
            {
                "content": "You are a helpful assistant",
                "role": "system",
            },
            {
                "content": "Hi, please introduce yourself briefly.",
                "role": "user",
            },
        ],
        "model": "deepseek-chat",
        "thinking": {
            "type": "disabled",
        },
        "frequency_penalty": 0,
        "max_tokens": 4096,
        "presence_penalty": 0,
        "response_format": {
            "type": "text",
        },
        "stop": None,
        "stream": False,
        "stream_options": None,
        "temperature": 1,
        "top_p": 1,
        "tools": None,
        "tool_choice": "none",
        "logprobs": False,
        "top_logprobs": None,
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    print("📡 正在调用 DeepSeek API...")
    response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    response.raise_for_status()

    result = response.json()
    print("✅ 响应状态码:", response.status_code)
    print("📝 模型回复:")
    print(result["choices"][0]["message"]["content"])
    print("\n📊 Token 使用情况:")
    print(json.dumps(result.get("usage", {}), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
