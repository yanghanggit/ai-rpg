#!/usr/bin/env python3
"""Replicate 文生图脚本。

python scripts/run_replicate_generate_image.py "prompt"   单张生成
python scripts/run_replicate_generate_image.py --demo     并发生成多张
python scripts/run_replicate_generate_image.py --test     测试连接

选项：--model / --negative / --size small|medium|large|wide|tall / --width / --height / --steps / --guidance
资产固定输出到 .images/，每个 raw 文件配一个同名 .meta。
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

import click

from ai_rpg.models import ImageMeta
from ai_rpg.replicate import (
    TextToImageJob,
    batch_text_to_images,
    check_replicate_connection,
    replicate_config,
    text_to_image,
)


async def run_concurrent_demo(prompts: List[str]) -> None:
    """运行并发生成演示"""
    print("=" * 60)
    print("🚀 Replicate 并发文生图演示")
    print("=" * 60)

    # 1. 测试连接
    if not check_replicate_connection():
        print("❌ 连接测试失败，请检查网络设置")
        return

    print(f"\n🎨 并发生成 {len(prompts)} 张图片...")
    print("📝 提示词列表:")
    for i, prompt in enumerate(prompts, 1):
        print(f"  {i}. {prompt}")

    try:
        jobs = [
            TextToImageJob(
                model=replicate_config.default_image_model,
                prompt=prompt,
                negative_prompt="worst quality, low quality, blurry",
                width=512,
                height=512,
            )
            for prompt in prompts
        ]

        results = await batch_text_to_images(jobs=jobs)

        metas: List[ImageMeta] = [m for m in results if m is not None]
        print(f"\n🎉 并发生成完成! 成功 {len(metas)}/{len(jobs)} 张:")
        for i, meta in enumerate(metas, 1):
            print(f"  {i}. {meta.local_path}  ({meta.url})")
        print("💡 这展示了异步并发的强大能力！")

    except Exception as e:
        print(f"❌ 并发演示失败: {e}")


@click.command()
@click.argument("prompt", required=False)
@click.option(
    "--model",
    "-m",
    type=click.Choice(list(replicate_config.get_available_models().keys())),
    help=f"选择模型 (默认: {replicate_config.default_image_model})",
)
@click.option(
    "--negative",
    "-n",
    default="worst quality, low quality, blurry",
    help="负向提示词",
)
@click.option("--width", "-w", default=1024, type=int, help="图片宽度")
@click.option("--height", default=1024, type=int, help="图片高度")
@click.option(
    "--size",
    type=click.Choice(["small", "medium", "large", "wide", "tall"]),
    help="预设尺寸: small(512x512), medium(768x768), large(1024x1024), wide(1024x768), tall(768x1024)",
)
@click.option("--steps", "-s", default=4, type=int, help="推理步数")
@click.option("--guidance", "-g", default=7.5, type=float, help="引导比例")
@click.option("--demo", is_flag=True, help="运行演示（并发生成多张图片）")
@click.option("--test", is_flag=True, help="测试连接")
def main(
    prompt: Optional[str],
    model: Optional[str],
    negative: str,
    width: int,
    height: int,
    size: Optional[str],
    steps: int,
    guidance: float,
    demo: bool,
    test: bool,
) -> None:
    """Replicate 文生图工具"""
    asyncio.run(
        _async_main(
            prompt,
            model,
            negative,
            width,
            height,
            size,
            steps,
            guidance,
            demo,
            test,
        )
    )


async def _async_main(
    prompt: Optional[str],
    model: Optional[str],
    negative: str,
    width: int,
    height: int,
    size: Optional[str],
    steps: int,
    guidance: float,
    demo: bool,
    test: bool,
) -> None:
    """异步主函数"""
    # 检查模型配置是否正确加载
    if not replicate_config.get_available_models():
        print("❌ 错误: 图像模型配置未正确加载")
        sys.exit(1)

    try:
        print("✅ Replicate 客户端初始化完成")

        # 处理预设尺寸
        if size:
            size_presets = {
                "small": (512, 512),
                "medium": (768, 768),
                "large": (1024, 1024),
                "wide": (1024, 768),
                "tall": (768, 1024),
            }
            width, height = size_presets[size]
            print(f"📐 使用预设尺寸 '{size}': {width}x{height}")

        # 如果是运行演示
        if demo:
            await run_concurrent_demo(
                [
                    "peaceful mountain landscape",
                    "ocean waves on sandy beach",
                    "forest path in autumn",
                ]
            )
            return

        # 如果是测试连接
        if test:
            check_replicate_connection()
            return

        # 如果没有提供提示词，显示帮助
        script = Path(__file__).name
        if not prompt:
            print("🎨 Replicate 文生图工具")
            print("\n快速开始:")
            print(
                f"  python scripts/{script} --demo            # 运行演示（并发生成多张图片）"
            )
            print(f"  python scripts/{script} --test            # 测试连接")
            print(f'  python scripts/{script} "生成一只猫"       # 生成图片')
            print("\n尺寸选项:")
            print("  --size small    # 512x512  (最快)")
            print("  --size medium   # 768x768  (推荐)")
            print("  --size large    # 1024x1024 (高质量)")
            print("  --size wide     # 1024x768 (横向)")
            print("  --size tall     # 768x1024 (纵向)")
            print("\n详细帮助:")
            print(f"  python scripts/{script} --help")
            return

        model_name = model if model else replicate_config.default_image_model

        # 打印生成信息
        print(f"🎨 使用模型: {model_name}")
        print(f"📝 提示词: {prompt}")
        print(f"⚙️  参数: {width}x{height}, {steps} 步")

        # 生成并写入配套 meta（aspect_ratio 由 width/height 自动推导）
        meta = await text_to_image(
            job=TextToImageJob(
                model=model_name,
                prompt=prompt,
                negative_prompt=negative,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=guidance,
            )
        )

        print(f"\n🎉 完成! 图片已保存到: {meta.local_path}")
        print(f"📝 元数据: {meta.meta_path}")
        print(f"🔗 URL: {meta.url}")

    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
