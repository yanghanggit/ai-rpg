#!/usr/bin/env python3
"""
Replicate 文生图工具
一个简单易用的文生图脚本，包含完整功能和使用示例
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from typing import Dict, Final, Optional, Any
import requests
import replicate
from dotenv import load_dotenv
import uuid

# 加载环境变量
load_dotenv()


def load_models_config() -> Dict[str, Dict[str, str]]:
    """从 JSON 文件加载模型配置"""
    # 获取项目根目录
    current_dir = Path(__file__).parent
    project_root = current_dir.parent
    config_file = project_root / "replicate_models.json"

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data: Dict[str, Dict[str, str]] = json.load(f)
            return data
    except FileNotFoundError:
        raise FileNotFoundError(f"模型配置文件未找到: {config_file}")
    except json.JSONDecodeError as e:
        raise ValueError(f"模型配置文件格式错误: {e}")


# 全局变量
try:
    MODELS: Dict[str, Dict[str, str]] = load_models_config()
    API_TOKEN: str = os.getenv("REPLICATE_API_TOKEN") or ""
except Exception as e:
    MODELS = {}
    API_TOKEN = ""
    print(f"⚠️ 配置加载失败: {e}")

DEFAULT_OUTPUT_DIR: Final[str] = "generated_images"
TEST_URL: Final[str] = "https://api.replicate.com/v1/models"


# 测试连接
def test_connection() -> bool:
    """测试连接是否正常"""
    headers = {"Authorization": f"Token {API_TOKEN}"}

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


def generate_image(
    prompt: str,
    model_name: str = "sdxl-lightning",
    negative_prompt: str = "worst quality, low quality, blurry",
    width: int = 768,
    height: int = 768,
    num_inference_steps: int = 4,
    guidance_scale: float = 7.5,
) -> str:
    """
    生成图片

    Args:
        prompt: 文本提示词
        model_name: 模型名称 (sdxl-lightning, sdxl, playground, realvis)
        negative_prompt: 负向提示词
        width: 图片宽度
        height: 图片高度
        num_inference_steps: 推理步数
        guidance_scale: 引导比例

    Returns:
        图片 URL
    """
    if model_name not in MODELS:
        raise ValueError(f"不支持的模型: {model_name}. 可用模型: {list(MODELS.keys())}")

    model_info = MODELS[model_name]
    model_version = model_info["version"]
    cost_estimate = model_info["cost_estimate"]

    print(f"\n🎨 使用模型: {model_name}")
    print(f"💰 预估成本: {cost_estimate}")
    print(f"📝 提示词: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    print(f"⚙️  参数: {width}x{height}, {num_inference_steps} 步")
    print("🔄 生成中...")

    start_time = time.time()

    try:
        # 根据不同模型调整参数
        if model_name == "sdxl-lightning":
            # Lightning 模型使用较少的步数
            num_inference_steps = min(4, num_inference_steps)

        output = replicate.run(
            model_version,
            input={
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "num_outputs": 1,
                "num_inference_steps": num_inference_steps,
                "guidance_scale": guidance_scale,
                "scheduler": "K_EULER",
            },
        )

        # 获取图片 URL
        image_url: str = output[0] if isinstance(output, list) else str(output)

        elapsed_time = time.time() - start_time
        print(f"✅ 生成完成! 耗时: {elapsed_time:.2f}秒")
        print(f"🔗 图片 URL: {image_url}")

        return image_url

    except Exception as e:
        print(f"❌ 生成失败: {e}")
        raise


def download_image(image_url: str, save_path: Optional[str] = None) -> str:
    """
    下载图片

    Args:
        image_url: 图片 URL
        save_path: 保存路径，如果为 None 则自动生成

    Returns:
        保存的文件路径
    """
    if save_path is None:
        # 自动生成文件名
        timestamp = str(uuid.uuid4())
        save_path = f"generated_image_{timestamp}.png"

    # 确保保存目录存在
    save_dir = Path(save_path).parent
    save_dir.mkdir(parents=True, exist_ok=True)

    try:
        print(f"📥 下载图片到: {save_path}")

        # 下载图片
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        # 保存图片
        with open(save_path, "wb") as f:
            f.write(response.content)

        file_size = len(response.content) / 1024  # KB
        print(f"✅ 下载完成! 文件大小: {file_size:.1f} KB")

        return save_path

    except Exception as e:
        print(f"❌ 下载失败: {e}")
        raise


def generate_and_download(prompt: str, output_dir: str, **kwargs: Any) -> str:
    """
    生成并下载图片的便捷方法

    Args:
        prompt: 文本提示词
        output_dir: 输出目录
        **kwargs: 其他生成参数

    Returns:
        保存的文件路径
    """
    # 生成图片
    image_url = generate_image(prompt, **kwargs)

    # 准备保存路径
    timestamp = str(uuid.uuid4())
    model_name = kwargs.get("model_name", "sdxl-lightning")
    filename = f"{model_name}_{timestamp}.png"
    save_path = Path(output_dir) / filename

    # 下载图片
    downloaded_path = download_image(image_url, str(save_path))

    return downloaded_path


def run_demo() -> None:
    """运行演示示例"""
    print("=" * 60)
    print("🎮 Replicate 文生图演示")
    print("=" * 60)

    # 1. 测试连接
    if not test_connection():
        print("❌ 连接测试失败，请检查网络设置")
        return

    # 2. 查看可用模型
    print("\n📋 可用模型:")
    for name, info in MODELS.items():
        cost = info["cost_estimate"]
        description = info["description"]
        print(f"  - {name}: {cost}")
        print(f"    {description}")

    # 3. 生成测试图片
    print("\n🎨 生成测试图片...")

    try:
        # 快速测试 - 使用成本最低的模型
        test_prompt = "a beautiful landscape with mountains and a lake"

        saved_path = generate_and_download(
            prompt=test_prompt,
            model_name="sdxl-lightning",  # 使用最快最便宜的模型
            output_dir=DEFAULT_OUTPUT_DIR,
        )

        print(f"\n🎉 演示完成! 图片已保存到: {saved_path}")
        print("💡 您可以查看生成的图片，然后尝试其他提示词")

    except Exception as e:
        print(f"❌ 演示失败: {e}")


def main() -> None:
    """主函数 - 命令行接口"""
    # 检查配置是否正确加载
    if not MODELS:
        print("❌ 错误: 模型配置未正确加载")
        print("💡 请检查:")
        print("   1. replicate_models.json 文件是否存在")
        print("   2. JSON 文件格式是否正确")
        sys.exit(1)

    if not API_TOKEN:
        print("❌ 错误: API Token 未配置")
        print("💡 请检查:")
        print("   1. 环境变量 REPLICATE_API_TOKEN 是否设置")
        print("   2. .env 文件是否存在且包含正确的 API Token")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Replicate 文生图工具")
    parser.add_argument("prompt", nargs="?", help="文本提示词")
    parser.add_argument(
        "--model",
        "-m",
        default="sdxl-lightning",
        choices=list(MODELS.keys()),
        help="使用的模型 (默认: sdxl-lightning)",
    )
    parser.add_argument(
        "--negative",
        "-n",
        default="worst quality, low quality, blurry",
        help="负向提示词",
    )
    parser.add_argument(
        "--width", "-w", type=int, default=768, help="图片宽度 (默认: 768)"
    )
    parser.add_argument("--height", type=int, default=768, help="图片高度 (默认: 768)")
    parser.add_argument(
        "--size",
        choices=["small", "medium", "large", "wide", "tall"],
        help="预设尺寸: small(512x512), medium(768x768), large(1024x1024), wide(1024x768), tall(768x1024)",
    )
    parser.add_argument("--steps", "-s", type=int, default=4, help="推理步数")
    parser.add_argument("--guidance", "-g", type=float, default=7.5, help="引导比例")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT_DIR, help="输出目录")
    parser.add_argument("--list-models", action="store_true", help="列出可用模型")
    parser.add_argument("--demo", action="store_true", help="运行演示")
    parser.add_argument("--test", action="store_true", help="测试连接")

    args = parser.parse_args()

    try:
        print("✅ Replicate 客户端初始化完成")

        # 处理预设尺寸
        if args.size:
            size_presets = {
                "small": (512, 512),
                "medium": (768, 768),
                "large": (1024, 1024),
                "wide": (1024, 768),
                "tall": (768, 1024),
            }
            args.width, args.height = size_presets[args.size]
            print(f"📐 使用预设尺寸 '{args.size}': {args.width}x{args.height}")

        # 如果是运行演示
        if args.demo:
            run_demo()
            return

        # 如果是测试连接
        if args.test:
            test_connection()
            return

        # 如果只是列出模型
        if args.list_models:
            print("🎨 可用模型:")
            for name, info in MODELS.items():
                cost = info["cost_estimate"]
                description = info["description"]
                print(f"  - {name}: {cost}")
                print(f"    {description}")
            return

        # 如果没有提供提示词，显示帮助
        if not args.prompt:
            print("🎨 Replicate 文生图工具")
            print("\n快速开始:")
            print("  python replicate_text2image.py --demo            # 运行演示")
            print("  python replicate_text2image.py --test            # 测试连接")
            print("  python replicate_text2image.py --list-models     # 查看内置模型")
            print('  python replicate_text2image.py "生成一只猫"       # 生成图片')
            print("\n尺寸选项:")
            print("  --size small    # 512x512  (最快)")
            print("  --size medium   # 768x768  (推荐)")
            print("  --size large    # 1024x1024 (高质量)")
            print("  --size wide     # 1024x768 (横向)")
            print("  --size tall     # 768x1024 (纵向)")
            print("\n详细帮助:")
            print("  python replicate_text2image.py -h")
            return

        # 生成并下载图片
        saved_path = generate_and_download(
            prompt=args.prompt,
            model_name=args.model,
            negative_prompt=args.negative,
            width=args.width,
            height=args.height,
            num_inference_steps=args.steps,
            guidance_scale=args.guidance,
            output_dir=args.output,
        )

        print(f"\n🎉 完成! 图片已保存到: {saved_path}")

    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
