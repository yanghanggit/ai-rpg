#!/usr/bin/env python3
"""
Replicate 文生图工具
一个简单易用的文生图脚本，包含完整功能和使用示例


# 基础使用
python scripts/run_replicate_text2image.py "prompt text"

# 演示功能
python scripts/run_replicate_text2image.py --demo           # 运行演示（并发生成多张图片）

# 实用功能
python scripts/run_replicate_text2image.py --test           # 测试连接
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path
from typing import List

from ai_rpg.replicate import (
    test_replicate_api_connection,
    replicate_config,
    generate_and_download,
    execute_tasks,
    ImageGenerationTask,
    ReplicateImageInput,
    DEFAULT_OUTPUT_DIR,
)


async def run_concurrent_demo(prompts: List[str]) -> None:
    """运行并发生成演示"""
    print("=" * 60)
    print("🚀 Replicate 并发文生图演示")
    print("=" * 60)

    # 1. 测试连接
    if not test_replicate_api_connection():
        print("❌ 连接测试失败，请检查网络设置")
        return

    print(f"\n🎨 并发生成 {len(prompts)} 张图片...")
    print("📝 提示词列表:")
    for i, prompt in enumerate(prompts, 1):
        print(f"  {i}. {prompt}")

    try:
        # 获取模型版本
        model_version = replicate_config.get_model_version()

        # 准备任务列表
        tasks = []
        for i, prompt in enumerate(prompts, 1):
            # 构建模型输入参数
            model_input: ReplicateImageInput = {
                "prompt": prompt,
                "negative_prompt": "worst quality, low quality, blurry",
                "aspect_ratio": "1:1",  # ideogram-v3-turbo 使用此参数
                "width": 512,  # 某些模型可能使用
                "height": 512,  # 某些模型可能使用
                "num_outputs": 1,
                "num_inference_steps": 4,
                "guidance_scale": 7.5,
                "scheduler": "K_EULER",
                "magic_prompt_option": "Auto",  # ideogram 专用
            }
            # 准备输出路径
            output_path = str(DEFAULT_OUTPUT_DIR / f"demo_{i:02d}_{uuid.uuid4()}.png")

            # 创建任务
            tasks.append(
                ImageGenerationTask(
                    model_version=model_version,
                    model_input=dict(model_input),
                    output_path=output_path,
                )
            )

        # 并发生成
        results = await execute_tasks(tasks)

        print(f"\n🎉 并发生成完成! 生成了 {len(results)} 张图片:")
        for i, path in enumerate(results, 1):
            print(f"  {i}. {path}")
        print("💡 这展示了异步并发的强大能力！")

    except Exception as e:
        print(f"❌ 并发演示失败: {e}")


async def main() -> None:
    """主函数 - 命令行接口"""

    # 检查模型配置是否正确加载
    if not replicate_config.get_available_models():
        print("❌ 错误: 图像模型配置未正确加载")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Replicate 文生图工具")

    parser.add_argument("prompt", nargs="?", help="文本提示词")
    parser.add_argument(
        "--negative",
        "-n",
        default="worst quality, low quality, blurry",
        help="负向提示词 (默认: worst quality, low quality, blurry)",
    )
    parser.add_argument(
        "--width",
        "-w",
        type=int,
        default=1024,
        help="图片宽度 (默认: 1024)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=1024,
        help="图片高度 (默认: 1024)",
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
        default=4,
        help="推理步数 (默认: 4)",
    )
    parser.add_argument(
        "--guidance",
        "-g",
        type=float,
        default=7.5,
        help="引导比例 (默认: 7.5)",
    )
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT_DIR, help="输出目录")
    parser.add_argument(
        "--demo", action="store_true", help="运行演示（并发生成多张图片）"
    )
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
            await run_concurrent_demo(
                [
                    "peaceful mountain landscape",
                    "ocean waves on sandy beach",
                    "forest path in autumn",
                ]
            )
            return

        # 如果是测试连接
        if args.test:
            test_replicate_api_connection()
            return

        # 如果没有提供提示词，显示帮助
        if not args.prompt:
            print("🎨 Replicate 文生图工具")
            print("\n快速开始:")
            print(
                "  python run_replicate_text2image.py --demo            # 运行演示（并发生成多张图片）"
            )
            print("  python run_replicate_text2image.py --test            # 测试连接")
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

        # 获取模型版本
        model_version = replicate_config.get_model_version()

        # 计算宽高比（用于 ideogram 系列模型）
        aspect_ratio = "1:1"  # 默认
        if args.width == args.height:
            aspect_ratio = "1:1"
        elif args.width > args.height:
            ratio = args.width / args.height
            if abs(ratio - 16 / 9) < 0.1:
                aspect_ratio = "16:9"
            elif abs(ratio - 4 / 3) < 0.1:
                aspect_ratio = "4:3"
        else:
            ratio = args.height / args.width
            if abs(ratio - 16 / 9) < 0.1:
                aspect_ratio = "9:16"
            elif abs(ratio - 4 / 3) < 0.1:
                aspect_ratio = "3:4"

        # 构建模型输入参数 (包含所有可能的参数，模型会选择其支持的使用)
        model_input: ReplicateImageInput = {
            "prompt": args.prompt,
            "negative_prompt": args.negative,
            "aspect_ratio": aspect_ratio,  # ideogram-v3-turbo 使用
            "width": args.width,  # 某些模型 (如 flux) 使用
            "height": args.height,  # 某些模型 (如 flux) 使用
            "num_outputs": 1,
            "num_inference_steps": args.steps,
            "guidance_scale": args.guidance,
            "scheduler": "K_EULER",
            "magic_prompt_option": "Auto",  # ideogram 专用
        }

        # 准备输出路径
        output_path = str(
            Path(args.output)
            / f"{replicate_config.default_image_model}_{uuid.uuid4()}.png"
        )

        # 打印生成信息
        print(f"🎨 使用模型: {replicate_config.default_image_model}")
        print(f"📝 提示词: {args.prompt}")
        print(f"⚙️  参数: {args.width}x{args.height}, {args.steps} 步")

        # 生成并下载图片
        saved_path = await generate_and_download(
            model_version=model_version,
            model_input=dict(model_input),
            output_path=output_path,
        )

        print(f"\n🎉 完成! 图片已保存到: {saved_path}")

    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
