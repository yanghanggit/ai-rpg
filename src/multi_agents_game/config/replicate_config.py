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
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# 加载环境变量
load_dotenv()

# 常量定义
TEST_URL: Final[str] = "https://api.replicate.com/v1/models"


# Pydantic 数据模型定义
class ModelInfo(BaseModel):
    """单个模型信息的数据结构"""

    version: str = Field(..., description="模型版本ID")
    cost_estimate: str = Field(..., description="成本估算描述")
    description: str = Field(..., description="模型描述")

    model_config = ConfigDict(extra="forbid")  # 禁止额外字段


class ImageModels(BaseModel):
    """图像模型配置数据结构"""

    sdxl_lightning: Optional[ModelInfo] = Field(None, alias="sdxl-lightning")
    sdxl: Optional[ModelInfo] = None
    playground: Optional[ModelInfo] = None
    realvis: Optional[ModelInfo] = None
    ideogram_v3_turbo: Optional[ModelInfo] = Field(None, alias="ideogram-v3-turbo")

    model_config = ConfigDict(
        populate_by_name=True,  # 修复: 使用新的参数名
        extra="allow",  # 允许额外的图像模型
    )

    def model_post_init(self, __context: Any) -> None:
        """验证额外字段也符合ModelInfo格式"""
        for field_name, field_value in self.__dict__.items():
            if field_name not in self.model_fields and field_value is not None:
                if isinstance(field_value, dict):
                    # 验证额外的模型是否符合ModelInfo格式
                    ModelInfo(**field_value)


class ChatModels(BaseModel):
    """对话模型配置数据结构"""

    gpt_4o_mini: Optional[ModelInfo] = Field(None, alias="gpt-4o-mini")
    gpt_4o: Optional[ModelInfo] = Field(None, alias="gpt-4o")
    claude_3_5_sonnet: Optional[ModelInfo] = Field(None, alias="claude-3.5-sonnet")
    llama_3_1_405b: Optional[ModelInfo] = Field(None, alias="llama-3.1-405b")
    llama_3_70b: Optional[ModelInfo] = Field(None, alias="llama-3-70b")

    model_config = ConfigDict(
        populate_by_name=True,  # 修复: 使用新的参数名
        extra="allow",  # 允许额外的对话模型
    )

    def model_post_init(self, __context: Any) -> None:
        """验证额外字段也符合ModelInfo格式"""
        for field_name, field_value in self.__dict__.items():
            if field_name not in self.model_fields and field_value is not None:
                if isinstance(field_value, dict):
                    # 验证额外的模型是否符合ModelInfo格式
                    ModelInfo(**field_value)


class ReplicateModelsConfig(BaseModel):
    """Replicate模型配置的完整数据结构"""

    image_models: ImageModels = Field(..., description="图像生成模型配置")
    chat_models: ChatModels = Field(..., description="对话模型配置")

    model_config = ConfigDict(extra="forbid")  # 严格模式，不允许额外字段


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
        """从 JSON 文件加载模型配置，使用 Pydantic 验证格式"""
        # 获取项目根目录 - 从 src/multi_agents_game/config/ 到项目根目录
        current_dir = Path(__file__).parent  # src/multi_agents_game/config/
        project_root = current_dir.parent.parent.parent  # 回到项目根目录
        config_file = project_root / "replicate_models.json"

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)

                # 使用 Pydantic 验证和解析配置
                try:
                    config_model = ReplicateModelsConfig(**data)
                    print("✅ JSON 配置格式验证通过")

                    # 转换为原有的字典格式以保持兼容性
                    self._image_models = {}
                    if config_model.image_models:
                        # 将 Pydantic 模型转换回字典格式
                        image_data = config_model.image_models.model_dump(
                            by_alias=True, exclude_none=True
                        )
                        for key, value in image_data.items():
                            if value:  # 只添加非空值
                                self._image_models[key] = value

                    self._chat_models = {}
                    if config_model.chat_models:
                        # 将 Pydantic 模型转换回字典格式
                        chat_data = config_model.chat_models.model_dump(
                            by_alias=True, exclude_none=True
                        )
                        for key, value in chat_data.items():
                            if value:  # 只添加非空值
                                self._chat_models[key] = value

                    # 如果原始数据有额外字段，也保留它们
                    raw_image_models = data.get("image_models", {})
                    raw_chat_models = data.get("chat_models", {})

                    for key, value in raw_image_models.items():
                        if key not in self._image_models:
                            self._image_models[key] = value

                    for key, value in raw_chat_models.items():
                        if key not in self._chat_models:
                            self._chat_models[key] = value

                except ValidationError as ve:
                    print(f"❌ JSON 配置格式验证失败:")
                    for error in ve.errors():
                        loc = " -> ".join(str(x) for x in error["loc"])
                        print(f"   {loc}: {error['msg']}")
                        if "input" in error:
                            print(f"   输入值: {error['input']}")

                    # 即使验证失败，也尝试加载原始数据
                    print("🔄 尝试使用原始格式加载...")
                    self._image_models = data.get("image_models", {})
                    self._chat_models = data.get("chat_models", {})

        except FileNotFoundError:
            raise FileNotFoundError(f"模型配置文件未找到: {config_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"模型配置文件格式错误: {e}")

    def validate_json_schema(self) -> bool:
        """验证当前配置是否符合 Pydantic 数据模型"""
        try:
            # 构建当前配置数据，将字典转换为模型实例
            image_models_dict = {}
            for key, value in self._image_models.items():
                if isinstance(value, dict):
                    image_models_dict[key] = ModelInfo(**value)
                else:
                    image_models_dict[key] = value

            chat_models_dict = {}
            for key, value in self._chat_models.items():
                if isinstance(value, dict):
                    chat_models_dict[key] = ModelInfo(**value)
                else:
                    chat_models_dict[key] = value

            # 创建子模型实例
            image_models_data = ImageModels(**image_models_dict)
            chat_models_data = ChatModels(**chat_models_dict)

            # 使用 Pydantic 验证
            ReplicateModelsConfig(
                image_models=image_models_data, chat_models=chat_models_data
            )
            print("✅ 当前配置符合数据模型规范")
            return True

        except ValidationError as ve:
            print(f"❌ 当前配置不符合数据模型规范:")
            for error in ve.errors():
                loc = " -> ".join(str(x) for x in error["loc"])
                print(f"   {loc}: {error['msg']}")
            return False

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
            "schema_valid": self.validate_json_schema(),
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

    # 新增：验证数据模型
    if not status.get("schema_valid", False):
        print("⚠️ 警告: JSON 配置不符合数据模型规范")

    return True


def validate_json_file() -> bool:
    """验证 JSON 文件格式是否符合 Pydantic 数据模型"""
    return get_replicate_config().validate_json_schema()


def get_pydantic_models() -> tuple[
    type[ReplicateModelsConfig],
    type[ModelInfo],
    type[ImageModels],
    type[ChatModels],
]:
    """获取 Pydantic 数据模型类，用于外部验证或文档生成"""
    return ReplicateModelsConfig, ModelInfo, ImageModels, ChatModels


def validate_json_file_with_path(json_file_path: str) -> bool:
    """验证指定JSON文件是否符合 Pydantic 数据模型"""
    try:
        from pathlib import Path

        config_file = Path(json_file_path)
        if not config_file.exists():
            print(f"❌ 测试文件不存在: {config_file}")
            return False

        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        try:
            ReplicateModelsConfig(**data)
            print("✅ JSON 配置格式验证通过")
            return True

        except ValidationError as ve:
            print(f"❌ JSON 配置格式验证失败:")
            for error in ve.errors():
                loc = " -> ".join(str(x) for x in error["loc"])
                print(f"   {loc}: {error['msg']}")
                if "input" in error:
                    print(f"   输入值: {error['input']}")
            return False

    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False


def create_example_config() -> Dict[str, Any]:
    """创建一个示例配置，符合 Pydantic 数据模型"""
    example = {
        "image_models": {
            "sdxl-lightning": {
                "version": "bytedance/sdxl-lightning-4step:5f24084160c9089501c1b3545d9be3c27883ae2239b6f412990e82d4a6210f8f",
                "cost_estimate": "$0.005-0.01 (~2-5秒) 推荐测试",
                "description": "快速生成模型，适合测试和原型开发",
            }
        },
        "chat_models": {
            "gpt-4o-mini": {
                "version": "openai/gpt-4o-mini",
                "cost_estimate": "$0.15/1M input + $0.6/1M output tokens",
                "description": "OpenAI 低成本高效对话模型，推荐日常使用",
            }
        },
    }

    # 验证示例配置
    try:
        # 将字典转换为模型实例
        image_models_dict = {}
        for key, value in example["image_models"].items():
            image_models_dict[key] = ModelInfo(**value)

        chat_models_dict = {}
        for key, value in example["chat_models"].items():
            chat_models_dict[key] = ModelInfo(**value)

        # 创建子模型实例
        image_models = ImageModels(**image_models_dict)
        chat_models = ChatModels(**chat_models_dict)

        # 然后创建完整配置
        ReplicateModelsConfig(image_models=image_models, chat_models=chat_models)
        print("✅ 示例配置验证通过")
    except ValidationError as e:
        print(f"❌ 示例配置验证失败: {e}")

    return example
