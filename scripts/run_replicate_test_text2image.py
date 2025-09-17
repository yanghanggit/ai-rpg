#!/usr/bin/env python3
"""
Replicate 文生图工具
一个简单易用的文生图脚本，包含完整功能和使用示例


# 基础使用
python scripts/run_replicate_text2image.py "prompt text"

# 演示功能
python scripts/run_replicate_text2image.py --demo            # 单张演示
python scripts/run_replicate_text2image.py --concurrent     # 并发演示

# 实用功能
python scripts/run_replicate_text2image.py --test           # 测试连接
python scripts/run_replicate_text2image.py --list-models    # 查看模型
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, Final

from ai_rpg.replicate import (
    test_replicate_api_connection,
    load_replicate_config,
    # get_default_generation_params,
    generate_and_download,
    generate_multiple_images,
)

# 全局变量
API_TOKEN: str = os.getenv("REPLICATE_API_TOKEN") or ""

replicate_config = load_replicate_config(Path("replicate_models.json"))

MODELS: Dict[str, Dict[str, str]] = replicate_config.image_models.model_dump(
    by_alias=True, exclude_none=True
)

DEFAULT_OUTPUT_DIR: Final[str] = "generated_images"


def _get_default_generation_params() -> Dict[str, Any]:
    """
    获取默认的图片生成参数

    Returns:
        包含默认参数的字典
    """
    return {
        "model_name": "sdxl-lightning",
        "negative_prompt": "worst quality, low quality, blurry",
        "width": 768,
        "height": 768,
        "num_inference_steps": 4,
        "guidance_scale": 7.5,
    }


async def run_demo() -> None:
    """运行演示示例"""
    print("=" * 60)
    print("🎮 Replicate 文生图演示")
    print("=" * 60)

    # 1. 测试连接
    if not test_replicate_api_connection():
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

        # 获取默认参数
        default_params = _get_default_generation_params()

        saved_path = await generate_and_download(
            prompt=test_prompt,
            model_name=default_params["model_name"],
            negative_prompt=default_params["negative_prompt"],
            width=default_params["width"],
            height=default_params["height"],
            num_inference_steps=default_params["num_inference_steps"],
            guidance_scale=default_params["guidance_scale"],
            output_dir=DEFAULT_OUTPUT_DIR,
            models_config=MODELS,
        )

        print(f"\n🎉 演示完成! 图片已保存到: {saved_path}")
        print("💡 您可以查看生成的图片，然后尝试其他提示词")

    except Exception as e:
        print(f"❌ 演示失败: {e}")


async def run_concurrent_demo() -> None:
    """运行并发生成演示"""
    print("=" * 60)
    print("🚀 Replicate 并发文生图演示")
    print("=" * 60)

    # 1. 测试连接
    if not test_replicate_api_connection():
        print("❌ 连接测试失败，请检查网络设置")
        return

    # 2. 多个提示词
    prompts = [
        "peaceful mountain landscape",
        "ocean waves on sandy beach",
        "forest path in autumn",
    ]

    print(f"\n🎨 并发生成 {len(prompts)} 张图片...")
    print("📝 提示词列表:")
    for i, prompt in enumerate(prompts, 1):
        print(f"  {i}. {prompt}")

    try:
        # 获取默认参数
        default_params = _get_default_generation_params()

        # 并发生成
        results = await generate_multiple_images(
            prompts=prompts,
            model_name="ideogram-v3-turbo",  # 使用相对稳定的模型
            negative_prompt=default_params["negative_prompt"],
            width=512,  # 使用较小尺寸加快测试
            height=512,
            num_inference_steps=default_params["num_inference_steps"],
            guidance_scale=default_params["guidance_scale"],
            output_dir=DEFAULT_OUTPUT_DIR,
            models_config=MODELS,
        )

        print(f"\n🎉 并发生成完成! 生成了 {len(results)} 张图片:")
        for i, path in enumerate(results, 1):
            print(f"  {i}. {path}")
        print("💡 这展示了异步并发的强大能力！")

    except Exception as e:
        print(f"❌ 并发演示失败: {e}")


async def main() -> None:
    """主函数 - 命令行接口"""

    # 检查模型配置是否正确加载
    if not MODELS:
        print("❌ 错误: 图像模型配置未正确加载")
        print("💡 请检查:")
        print("   1. replicate_models.json 文件是否存在")
        print("   2. JSON 文件格式是否正确")
        print("   3. image_models 部分是否配置正确")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Replicate 文生图工具")

    # 获取默认参数
    default_params = _get_default_generation_params()

    parser.add_argument("prompt", nargs="?", help="文本提示词")
    parser.add_argument(
        "--model",
        "-m",
        default=default_params["model_name"],
        choices=list(MODELS.keys()),
        help=f"使用的模型 (默认: {default_params['model_name']})",
    )
    parser.add_argument(
        "--negative",
        "-n",
        default=default_params["negative_prompt"],
        help="负向提示词",
    )
    parser.add_argument(
        "--width",
        "-w",
        type=int,
        default=default_params["width"],
        help=f"图片宽度 (默认: {default_params['width']})",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=default_params["height"],
        help=f"图片高度 (默认: {default_params['height']})",
    )
    parser.add_argument(
        "--size",
        choices=["small", "medium", "large", "wide", "tall"],
        help="预设尺寸: small(512x512), medium(768x768), large(1024x1024), wide(1024x768), tall(768x1024)",
    )
    parser.add_argument(
        "--steps",
        "-s",
        type=int,
        default=default_params["num_inference_steps"],
        help="推理步数",
    )
    parser.add_argument(
        "--guidance",
        "-g",
        type=float,
        default=default_params["guidance_scale"],
        help="引导比例",
    )
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT_DIR, help="输出目录")
    parser.add_argument("--list-models", action="store_true", help="列出可用模型")
    parser.add_argument("--demo", action="store_true", help="运行演示")
    parser.add_argument("--concurrent", action="store_true", help="运行并发生成演示")
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
            await run_demo()
            return

        # 如果是运行并发演示
        if args.concurrent:
            await run_concurrent_demo()
            return

        # 如果是测试连接
        if args.test:
            test_replicate_api_connection()
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
            print(
                "  python run_replicate_text2image.py --demo            # 运行单张演示"
            )
            print(
                "  python run_replicate_text2image.py --concurrent      # 运行并发演示"
            )
            print("  python run_replicate_text2image.py --test            # 测试连接")
            print(
                "  python run_replicate_text2image.py --list-models     # 查看内置模型"
            )
            print('  python run_replicate_text2image.py "生成一只猫"       # 生成图片')
            print("\n尺寸选项:")
            print("  --size small    # 512x512  (最快)")
            print("  --size medium   # 768x768  (推荐)")
            print("  --size large    # 1024x1024 (高质量)")
            print("  --size wide     # 1024x768 (横向)")
            print("  --size tall     # 768x1024 (纵向)")
            print("\n详细帮助:")
            print("  python run_replicate_text2image.py -h")
            return

        # 生成并下载图片
        saved_path = await generate_and_download(
            prompt=args.prompt,
            model_name=args.model,
            negative_prompt=args.negative,
            width=args.width,
            height=args.height,
            num_inference_steps=args.steps,
            guidance_scale=args.guidance,
            output_dir=args.output,
            models_config=MODELS,
        )

        print(f"\n🎉 完成! 图片已保存到: {saved_path}")

    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
