#!/usr/bin/env python3
"""
Replicate配置测试总结
这是针对 replicate_config.py 的主要测试场景总结
"""

import pytest
import tempfile
import json
from unittest.mock import patch, Mock
from pathlib import Path

from src.multi_agents_game.config.replicate_config import (
    ModelInfo, 
    ImageModels, 
    ChatModels, 
    ReplicateModelsConfig,
    ReplicateConfig,
    validate_json_file,
    validate_json_file_with_path,
    create_example_config
)


def test_pydantic_model_validation():
    """测试Pydantic数据模型验证的核心功能"""
    
    # 1. 测试有效的ModelInfo
    valid_model = ModelInfo(
        version="test/model:123",
        cost_estimate="$0.01",
        description="Test model"
    )
    assert valid_model.version == "test/model:123"
    
    # 2. 测试完整的配置结构
    valid_config = {
        "image_models": {
            "sdxl": {
                "version": "test/sdxl:123",
                "cost_estimate": "$0.01",
                "description": "SDXL model"
            }
        },
        "chat_models": {
            "gpt-4o-mini": {
                "version": "openai/gpt-4o-mini",
                "cost_estimate": "$0.15/1M tokens",
                "description": "GPT-4o Mini"
            }
        }
    }
    config = ReplicateModelsConfig(**valid_config)
    assert config.image_models is not None
    assert config.chat_models is not None


def test_json_file_validation():
    """测试JSON文件验证功能"""
    
    # 创建有效的JSON测试文件
    valid_config = {
        "image_models": {
            "test-model": {
                "version": "test/model:123",
                "cost_estimate": "$0.01",
                "description": "Test model"
            }
        },
        "chat_models": {
            "test-chat": {
                "version": "test/chat:456",
                "cost_estimate": "$0.02",
                "description": "Test chat model"
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(valid_config, f)
        temp_file = f.name
    
    try:
        with patch("builtins.print"):
            result = validate_json_file_with_path(temp_file)
            assert result is True
    finally:
        Path(temp_file).unlink()


def test_invalid_json_detection():
    """测试无效JSON格式检测"""
    
    # 创建无效的JSON测试文件（额外的不允许字段）
    invalid_config = {
        "image_models": {
            "test-model": {
                "version": "test/model:123",
                "cost_estimate": "$0.01",
                "description": "Test model"
            }
        },
        "chat_models": {
            "test-chat": {
                "version": "test/chat:456",
                "cost_estimate": "$0.02",
                "description": "Test chat model"
            }
        },
        "extra_field_not_allowed": "This should cause validation to fail"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(invalid_config, f)
        temp_file = f.name
    
    try:
        with patch("builtins.print"):
            result = validate_json_file_with_path(temp_file)
            assert result is False
    finally:
        Path(temp_file).unlink()


def test_config_class_basic_functionality():
    """测试ReplicateConfig类的基本功能"""
    
    mock_config_data = {
        "image_models": {
            "test-image": {
                "version": "test/image:123",
                "cost_estimate": "$0.01",
                "description": "Test image model"
            }
        },
        "chat_models": {
            "test-chat": {
                "version": "test/chat:456",
                "cost_estimate": "$0.02",
                "description": "Test chat model"
            }
        }
    }
    
    with patch("src.multi_agents_game.config.replicate_config.Path.open"), \
         patch("json.load") as mock_json_load, \
         patch("builtins.print"):
        
        mock_json_load.return_value = mock_config_data
        config = ReplicateConfig()
        
        assert config.is_config_loaded is True
        assert len(config.image_models) > 0
        assert len(config.chat_models) > 0
        assert config.validate_image_model("test-image") is True
        assert config.validate_chat_model("test-chat") is True
        assert config.validate_image_model("nonexistent") is False


@patch("requests.get")
def test_api_connection_testing(mock_get):
    """测试API连接测试功能"""
    
    # 模拟成功的API响应
    mock_response = Mock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    
    with patch("src.multi_agents_game.config.replicate_config.Path.open"), \
         patch("json.load") as mock_json_load, \
         patch("builtins.print"), \
         patch.dict("os.environ", {"REPLICATE_API_TOKEN": "test-token"}):
        
        mock_json_load.return_value = {"image_models": {}, "chat_models": {}}
        config = ReplicateConfig()
        
        result = config.test_connection()
        assert result is True
        
        # 测试失败的情况
        mock_response.status_code = 401
        result = config.test_connection()
        assert result is False


def test_example_config_creation():
    """测试示例配置创建功能"""
    
    with patch("builtins.print"):
        example = create_example_config()
        
        # 验证示例配置结构
        assert "image_models" in example
        assert "chat_models" in example
        assert isinstance(example["image_models"], dict)
        assert isinstance(example["chat_models"], dict)
        
        # 验证示例配置至少有一个模型
        assert len(example["image_models"]) > 0
        assert len(example["chat_models"]) > 0


def test_current_config_validation():
    """测试当前实际配置文件的验证"""
    
    with patch("builtins.print"):
        # 这个测试会验证项目中实际的 replicate_models.json 文件
        result = validate_json_file()
        assert result is True, "当前配置文件应该通过验证"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
