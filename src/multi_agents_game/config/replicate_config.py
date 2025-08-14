#!/usr/bin/env python3
"""
Replicate 配置管理模块
统一管理 Replicate API 配置、模型配置和初始化逻辑
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Final, Optional

import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 常量定义
TEST_URL: Final[str] = "https://api.replicate.com/v1/models"


class ReplicateConfig:
    """Replicate 配置管理类"""

    def __init__(self) -> None:
        """初始化配置"""
        self._api_token: str = ""
        self._image_models: Dict[str, Dict[str, str]] = {}
        self._chat_models: Dict[str, Dict[str, str]] = {}
        self._config_loaded: bool = False

        # 自动加载配置
        self._load_config()

    def _load_config(self) -> None:
        """加载所有配置"""
        try:
            # 加载 API Token
            self._api_token = os.getenv("REPLICATE_API_TOKEN") or ""

            # 加载模型配置
            self._load_models_config()

            self._config_loaded = True

        except Exception as e:
            print(f"⚠️ 配置加载失败: {e}")
            self._config_loaded = False

    def _load_models_config(self) -> None:
        """从 JSON 文件加载模型配置"""
        # 获取项目根目录 - 从 src/multi_agents_game/config/ 到项目根目录
        current_dir = Path(__file__).parent  # src/multi_agents_game/config/
        project_root = current_dir.parent.parent.parent  # 回到项目根目录
        config_file = project_root / "replicate_models.json"

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)

                # 加载图像模型配置
                self._image_models = data.get("image_models", {})

                # 加载对话模型配置
                self._chat_models = data.get("chat_models", {})

        except FileNotFoundError:
            raise FileNotFoundError(f"模型配置文件未找到: {config_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"模型配置文件格式错误: {e}")

    @property
    def api_token(self) -> str:
        """获取 API Token"""
        return self._api_token

    @property
    def image_models(self) -> Dict[str, Dict[str, str]]:
        """获取图像模型配置"""
        return self._image_models

    @property
    def chat_models(self) -> Dict[str, Dict[str, str]]:
        """获取对话模型配置"""
        return self._chat_models

    @property
    def is_config_loaded(self) -> bool:
        """检查配置是否成功加载"""
        return self._config_loaded

    def test_connection(self) -> bool:
        """测试 Replicate API 连接"""
        if not self._api_token:
            print("❌ API Token 未配置")
            return False

        headers = {"Authorization": f"Token {self._api_token}"}

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

    def get_image_model_info(self, model_name: str) -> Optional[Dict[str, str]]:
        """获取指定图像模型的信息"""
        return self._image_models.get(model_name)

    def get_chat_model_info(self, model_name: str) -> Optional[Dict[str, str]]:
        """获取指定对话模型的信息"""
        return self._chat_models.get(model_name)

    def list_image_models(self) -> Dict[str, Dict[str, str]]:
        """列出所有图像模型"""
        return self._image_models.copy()

    def list_chat_models(self) -> Dict[str, Dict[str, str]]:
        """列出所有对话模型"""
        return self._chat_models.copy()

    def validate_image_model(self, model_name: str) -> bool:
        """验证图像模型是否存在"""
        return model_name in self._image_models

    def validate_chat_model(self, model_name: str) -> bool:
        """验证对话模型是否存在"""
        return model_name in self._chat_models

    def get_config_status(self) -> Dict[str, Any]:
        """获取配置状态信息"""
        return {
            "config_loaded": self._config_loaded,
            "api_token_configured": bool(self._api_token),
            "image_models_count": len(self._image_models),
            "chat_models_count": len(self._chat_models),
            "image_models": list(self._image_models.keys()),
            "chat_models": list(self._chat_models.keys()),
        }


# 全局配置实例
_replicate_config: Optional[ReplicateConfig] = None


def get_replicate_config() -> ReplicateConfig:
    """获取全局 Replicate 配置实例（单例模式）"""
    global _replicate_config
    if _replicate_config is None:
        _replicate_config = ReplicateConfig()
    return _replicate_config


# 便捷函数
def get_api_token() -> str:
    """获取 API Token"""
    return get_replicate_config().api_token


def get_image_models() -> Dict[str, Dict[str, str]]:
    """获取图像模型配置"""
    return get_replicate_config().image_models


def get_chat_models() -> Dict[str, Dict[str, str]]:
    """获取对话模型配置"""
    return get_replicate_config().chat_models


def test_api_connection() -> bool:
    """测试 API 连接"""
    return get_replicate_config().test_connection()


def validate_config() -> bool:
    """验证配置是否完整"""
    config = get_replicate_config()
    status = config.get_config_status()

    if not status["config_loaded"]:
        print("❌ 配置加载失败")
        return False

    if not status["api_token_configured"]:
        print("❌ API Token 未配置")
        print("💡 请检查:")
        print("   1. 环境变量 REPLICATE_API_TOKEN 是否设置")
        print("   2. .env 文件是否存在且包含正确的 API Token")
        return False

    if status["image_models_count"] == 0:
        print("⚠️ 警告: 未找到图像模型配置")

    if status["chat_models_count"] == 0:
        print("⚠️ 警告: 未找到对话模型配置")

    return True


def print_config_status() -> None:
    """打印配置状态"""
    config = get_replicate_config()
    status = config.get_config_status()

    print("📋 Replicate 配置状态:")
    print(f"   配置加载: {'✅' if status['config_loaded'] else '❌'}")
    print(f"   API Token: {'✅' if status['api_token_configured'] else '❌'}")
    print(f"   图像模型: {status['image_models_count']} 个")
    print(f"   对话模型: {status['chat_models_count']} 个")

    if status["image_models"]:
        print(f"   图像模型列表: {', '.join(status['image_models'])}")

    if status["chat_models"]:
        print(f"   对话模型列表: {', '.join(status['chat_models'])}")


if __name__ == "__main__":
    """模块测试"""
    print("=" * 60)
    print("🔧 Replicate 配置测试")
    print("=" * 60)

    # 打印配置状态
    print_config_status()

    # 测试连接
    print(f"\n🔗 API 连接测试:")
    test_api_connection()

    # 验证配置
    print(f"\n✅ 配置验证:")
    is_valid = validate_config()
    print(f"配置有效性: {'✅ 通过' if is_valid else '❌ 失败'}")
