#!/usr/bin/env python3
"""
Replicate 图像编辑测试工具
专门测试 nano-banana 系列模型的图像编辑能力

功能：
- 单图编辑（背景模糊、风格转换、场景替换等）
- 多图融合（nano-banana 特色功能）
- 预设测试场景
- 完全复用 ai_rpg.replicate 的 API

使用示例：
# 运行预设场景
python scripts/run_replicate_image_edit_test.py --demo blur

# 自定义编辑
python scripts/run_replicate_image_edit_test.py \
  --input generated_images/cat.png \
  --prompt "Make the background blurry" \
  --model nano-banana

# 多图融合
python scripts/run_replicate_image_edit_test.py \
  --input img1.png img2.png img3.png \
  --prompt "Combine these images into a cohesive scene" \
  --model nano-banana-pro
"""

import asyncio
import sys
import uuid
from pathlib import Path
from typing import List, Optional

import click

from ai_rpg.replicate import (
    ReplicateImageTask,
    ReplicateImageInput,
    replicate_config,
    test_replicate_api_connection,
    GENERATED_IMAGES_OUTPUT_DIR,
)


# ========== 预设测试场景 ==========

DEMO_SCENARIOS = {
    "blur": {
        "name": "背景模糊",
        "prompt": "Blur the background while keeping the main subject sharp and in focus",
        "description": "将背景虚化，突出主体",
    },
    "watercolor": {
        "name": "水彩风格",
        "prompt": "Convert this image to watercolor painting style",
        "description": "将图片转换为水彩画风格",
    },
    "oil": {
        "name": "油画风格",
        "prompt": "Convert this image to oil painting style with visible brush strokes",
        "description": "转换为油画风格，带有明显笔触",
    },
    "garden": {
        "name": "场景替换",
        "prompt": "Place the main subject in a beautiful garden with colorful flowers and green grass",
        "description": "将主体移到美丽的花园场景",
    },
    "night": {
        "name": "时间转换",
        "prompt": "Change the scene to nighttime with stars and moonlight",
        "description": "将场景改为夜晚，添加星空和月光",
    },
    "hat": {
        "name": "添加装饰",
        "prompt": "Add a colorful party hat on the subject's head",
        "description": "给主体添加彩色派对帽",
    },
    "fusion": {
        "name": "多图融合",
        "prompt": "Seamlessly blend these images into a single cohesive composition",
        "description": "将多张图片融合成统一的构图",
    },
}


def find_test_images(
    directory: Path = GENERATED_IMAGES_OUTPUT_DIR, limit: int = 3
) -> List[Path]:
    """查找测试用图片"""
    if not directory.exists():
        return []

    # 查找最近生成的图片
    images = sorted(
        directory.glob("*.png"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return images[:limit]


def print_demo_scenarios() -> None:
    """打印所有预设场景"""
    print("\n📋 可用的预设测试场景:\n")
    for key, scenario in DEMO_SCENARIOS.items():
        print(f"  {key:12} - {scenario['name']}")
        print(f"               {scenario['description']}")
        print(f"               提示词: {scenario['prompt'][:60]}...")
        print()


async def run_image_edit(
    input_images: List[str],
    prompt: str,
    model: str = "nano-banana",
    output_format: str = "png",
    aspect_ratio: str = "match_input_image",
) -> str:
    """
    执行图像编辑任务

    Args:
        input_images: 输入图片路径列表
        prompt: 编辑指令
        model: 使用的模型
        output_format: 输出格式
        aspect_ratio: 宽高比

    Returns:
        保存的文件路径
    """
    print("=" * 70)
    print(f"🎨 Nano Banana 图像编辑测试")
    print("=" * 70)

    # 打印任务信息
    print(f"\n📝 编辑任务:")
    print(f"  模型: {model}")
    print(f"  输入图片数量: {len(input_images)}")
    for i, img in enumerate(input_images, 1):
        print(f"    {i}. {img}")
    print(f"  编辑指令: {prompt}")
    print(f"  输出格式: {output_format}")
    print(f"  宽高比: {aspect_ratio}")

    # 获取模型版本
    model_version = replicate_config.get_model_version(model)

    # 打开图片文件（传递文件对象给 Replicate API）
    print(f"\n📤 准备上传图片文件...")
    image_files = []
    for img_path in input_images:
        with open(img_path, "rb") as f:
            # 读取文件内容并保存
            image_files.append(open(img_path, "rb"))

    # 构建模型输入（包含 image_input）
    model_input: ReplicateImageInput = {
        "prompt": prompt,
        "image_input": image_files,  # 传递打开的文件对象
        "aspect_ratio": aspect_ratio,
        "output_format": output_format,
    }

    # 准备输出路径
    output_path = str(
        GENERATED_IMAGES_OUTPUT_DIR / f"{model}_edit_{uuid.uuid4()}.{output_format}"
    )

    print(f"\n⏳ 开始执行编辑任务...")

    try:
        # 创建并执行任务
        task = ReplicateImageTask(
            model_version=model_version,
            model_input=dict(model_input),
            output_path=output_path,
        )
        saved_path = await task.execute()

        # 关闭文件
        for f in image_files:
            f.close()

        print(f"\n🎉 编辑完成!")
        print(f"📂 保存位置: {saved_path}")

        return saved_path

    except Exception as e:
        print(f"\n❌ 编辑失败: {e}")
        raise


async def run_demo_scenario(scenario_key: str, model: str = "nano-banana") -> None:
    """运行预设测试场景"""
    if scenario_key not in DEMO_SCENARIOS:
        print(f"❌ 未知场景: {scenario_key}")
        print_demo_scenarios()
        return

    scenario = DEMO_SCENARIOS[scenario_key]

    print("\n" + "=" * 70)
    print(f"🚀 运行预设场景: {scenario['name']}")
    print("=" * 70)
    print(f"描述: {scenario['description']}")
    print(f"提示词: {scenario['prompt']}")

    # 查找测试图片
    if scenario_key == "fusion":
        # 多图融合需要多张图片
        test_images = find_test_images(limit=3)
        if len(test_images) < 2:
            print(f"\n❌ 错误: 多图融合需要至少2张图片")
            print(f"💡 请先生成一些测试图片，或使用 --input 指定多个图片")
            return
    else:
        # 单图编辑只需要1张
        test_images = find_test_images(limit=1)
        if not test_images:
            print(f"\n❌ 错误: 在 {GENERATED_IMAGES_OUTPUT_DIR} 目录下未找到测试图片")
            print(f"💡 请先运行 run_replicate_test_text2image.py 生成一些图片")
            return

    # 转换为字符串路径
    input_paths = [str(img) for img in test_images]

    print(f"\n📸 使用测试图片:")
    for i, path in enumerate(input_paths, 1):
        print(f"  {i}. {path}")

    # 执行编辑
    await run_image_edit(
        input_images=input_paths,
        prompt=scenario["prompt"],
        model=model,
    )


@click.command()
@click.option(
    "--input",
    "-i",
    "input_images",
    multiple=True,
    type=click.Path(exists=True),
    help="输入图片路径（可多个）",
)
@click.option(
    "--prompt",
    "-p",
    help="编辑指令（自然语言描述想要的效果）",
)
@click.option(
    "--model",
    "-m",
    type=click.Choice(["nano-banana", "nano-banana-pro"]),
    default="nano-banana",
    help="使用的模型（默认: nano-banana）",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["png", "jpg", "webp"]),
    default="png",
    help="输出格式",
)
@click.option(
    "--aspect-ratio",
    "-a",
    type=click.Choice(["match_input_image", "1:1", "4:3", "3:4", "16:9", "9:16"]),
    default="match_input_image",
    help="输出宽高比",
)
@click.option(
    "--demo",
    type=click.Choice(list(DEMO_SCENARIOS.keys())),
    help="运行预设测试场景",
)
@click.option(
    "--list-demos",
    is_flag=True,
    help="列出所有预设场景",
)
@click.option(
    "--test",
    is_flag=True,
    help="测试 API 连接",
)
def main(
    input_images: tuple[str, ...],
    prompt: Optional[str],
    model: str,
    output_format: str,
    aspect_ratio: str,
    demo: Optional[str],
    list_demos: bool,
    test: bool,
) -> None:
    """Nano Banana 图像编辑测试工具"""
    asyncio.run(
        _async_main(
            input_images,
            prompt,
            model,
            output_format,
            aspect_ratio,
            demo,
            list_demos,
            test,
        )
    )


async def _async_main(
    input_images: tuple[str, ...],
    prompt: Optional[str],
    model: str,
    output_format: str,
    aspect_ratio: str,
    demo: Optional[str],
    list_demos: bool,
    test: bool,
) -> None:
    """异步主函数"""

    # 列出预设场景
    if list_demos:
        print_demo_scenarios()
        return

    # 测试连接
    if test:
        test_replicate_api_connection()
        return

    # 运行预设场景
    if demo:
        await run_demo_scenario(demo, model)
        return

    # 自定义编辑
    if not input_images or not prompt:
        print("🎨 Nano Banana 图像编辑测试工具\n")
        print("快速开始:")
        print("  # 列出所有预设场景")
        print("  python scripts/run_replicate_image_edit_test.py --list-demos\n")
        print("  # 运行预设场景")
        print("  python scripts/run_replicate_image_edit_test.py --demo blur\n")
        print("  # 自定义编辑")
        print("  python scripts/run_replicate_image_edit_test.py \\")
        print("    --input generated_images/cat.png \\")
        print("    --prompt 'Make the background blurry'\n")
        print("  # 多图融合")
        print("  python scripts/run_replicate_image_edit_test.py \\")
        print("    --input img1.png img2.png img3.png \\")
        print("    --prompt 'Combine into one scene'\n")
        print("详细帮助:")
        print("  python scripts/run_replicate_image_edit_test.py --help")
        return

    # 执行自定义编辑
    try:
        await run_image_edit(
            input_images=list(input_images),
            prompt=prompt,
            model=model,
            output_format=output_format,
            aspect_ratio=aspect_ratio,
        )
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
