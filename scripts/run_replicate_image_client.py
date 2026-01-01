#!/usr/bin/env python3
"""
图片生成服务客户端
用于测试和调用 run_replicate_image_server.py 提供的 FastAPI 服务

使用示例:
    # 基础使用
    python scripts/run_replicate_image_client.py -s http://{LOCAL_NETWORK_IP}:{PORT} "a beautiful cat"

    # 批量生成（多个独立配置）
    python scripts/run_replicate_image_client.py -s http://{LOCAL_NETWORK_IP}:{PORT} "cat" "dog" "bird"

    # 指定参数
    python scripts/run_replicate_image_client.py -s http://{LOCAL_NETWORK_IP}:{PORT} "cat" --width 512 --height 512

    # 运行演示
    python scripts/run_replicate_image_client.py -s http://{LOCAL_NETWORK_IP}:{PORT} --demo

    # 列出已生成的图片
    python scripts/run_replicate_image_client.py -s http://{LOCAL_NETWORK_IP}:{PORT} --list

    # 测试服务器连接
    python scripts/run_replicate_image_client.py -s http://{LOCAL_NETWORK_IP}:{PORT} --test
"""

import asyncio
import sys
from typing import Dict, Any, Final, List, Optional

import click
import httpx
from loguru import logger

# 将 src 目录添加到模块搜索路径
import os

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from ai_rpg.configuration import server_configuration
from ai_rpg.replicate import replicate_config

# 局域网地址配置（根据实际情况修改）
LOCAL_NETWORK_IP: Final[str] = "192.168.2.134"


class ReplicateImageClient:
    """图片生成服务客户端"""

    def __init__(self, base_url: str, timeout: float) -> None:
        """
        初始化客户端

        Args:
            base_url: 服务器基础 URL
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url
        self.timeout = timeout
        logger.info(f"📡 连接到服务器: {self.base_url}")

    async def test_connection(self) -> bool:
        """测试服务器连接"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/")
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ 服务器连接成功")
                    logger.info(f"📋 服务信息: {data['message']}")
                    logger.info(f"🔧 版本: {data['version']}")
                    logger.info(f"🎨 可用模型: {', '.join(data['available_models'])}")
                    return True
                else:
                    logger.error(f"❌ 服务器返回错误: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"❌ 连接失败: {e}")
            return False

    async def generate_images(
        self, configs: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        生成图片

        Args:
            configs: 生成配置列表，每个配置对应一张图片

        Returns:
            响应数据，包含生成的图片信息
        """
        try:
            request_data = {"configs": configs}

            logger.info(f"🎨 发送生成请求，配置数量: {len(configs)}")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate/v1", json=request_data
                )

                if response.status_code == 200:
                    data: Dict[str, Any] = response.json()
                    logger.info(f"✅ 生成成功! 耗时: {data['elapsed_time']:.2f}秒")
                    logger.info(f"📊 总共生成: {len(data['images'])} 张图片")

                    # 打印每张图片的信息
                    for i, img in enumerate(data["images"], 1):
                        logger.info(f"  {i}. {img['filename']}")
                        logger.info(f"     提示词: {img['prompt']}")
                        logger.info(f"     模型: {img['model']}")
                        logger.info(f"     URL: {self.base_url}{img['url']}")

                    return data
                else:
                    logger.error(f"❌ 请求失败: {response.status_code}")
                    logger.error(f"错误详情: {response.text}")
                    return None

        except Exception as e:
            logger.error(f"❌ 生成图片时出错: {e}")
            return None

    async def list_images(self) -> Optional[List[str]]:
        """列出已生成的图片"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/images/list/v1")

                if response.status_code == 200:
                    images: List[str] = response.json()
                    logger.info(f"📁 已生成的图片数量: {len(images)}")
                    for i, img in enumerate(images, 1):
                        logger.info(f"  {i}. {img}")
                    return images
                else:
                    logger.error(f"❌ 请求失败: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"❌ 列出图片时出错: {e}")
            return None


async def run_demo(client: ReplicateImageClient) -> None:
    """运行演示 - 测试多个独立配置的批量生成"""
    logger.info("=" * 60)
    logger.info("🚀 图片生成客户端演示")
    logger.info("=" * 60)

    # 准备多个独立的生成配置
    configs = [
        {
            "prompt": "a peaceful mountain landscape at sunset",
            "model": "flux-schnell",
            "width": 1024,
            "height": 1024,
            "num_inference_steps": 4,
        },
        {
            "prompt": "ocean waves crashing on a sandy beach",
            "model": "nano-banana",
            "width": 1024,
            "height": 768,
            "num_inference_steps": 4,
        },
        {
            "prompt": "a mystical forest path in autumn",
            "model": "nano-banana",
            "width": 768,
            "height": 1024,
            "num_inference_steps": 4,
        },
    ]

    # 发送请求
    result = await client.generate_images(configs)

    if result and result.get("images"):
        logger.info(f"\n🎉 演示完成! 生成了 {len(result['images'])} 张图片")
    else:
        logger.error("❌ 演示失败")


@click.command()
@click.argument("prompts", nargs=-1, required=False)
@click.option(
    "--server",
    "-s",
    required=True,
    help=f"服务器地址 (例: http://{LOCAL_NETWORK_IP}:{server_configuration.image_generation_server_port})",
)
@click.option(
    "--model",
    "-m",
    default=None,
    type=click.Choice(list(replicate_config.get_available_models().keys())),
    help="模型名称",
)
@click.option("--width", "-w", default=1024, type=int, help="图片宽度")
@click.option("--height", default=1024, type=int, help="图片高度")
@click.option("--steps", default=4, type=int, help="推理步数")
@click.option("--guidance", "-g", default=7.5, type=float, help="引导比例")
@click.option(
    "--negative",
    "-n",
    default="worst quality, low quality, blurry",
    help="负向提示词",
)
@click.option("--demo", is_flag=True, help="运行演示")
@click.option("--list", "list_images_flag", is_flag=True, help="列出已生成的图片")
@click.option("--test", is_flag=True, help="测试服务器连接")
def main(
    prompts: tuple[str, ...],
    server: Optional[str],
    model: Optional[str],
    width: int,
    height: int,
    steps: int,
    guidance: float,
    negative: str,
    demo: bool,
    list_images_flag: bool,
    test: bool,
) -> None:
    """图片生成服务客户端 - 用于测试和调用图片生成服务"""
    asyncio.run(
        _async_main(
            prompts,
            server,
            model,
            width,
            height,
            steps,
            guidance,
            negative,
            demo,
            list_images_flag,
            test,
        )
    )


async def _async_main(
    prompts: tuple[str, ...],
    server: Optional[str],
    model: Optional[str],
    width: int,
    height: int,
    steps: int,
    guidance: float,
    negative: str,
    demo: bool,
    list_images_flag: bool,
    test: bool,
) -> None:
    """异步主函数"""
    try:
        # 初始化客户端
        assert server is not None, "服务器地址不能为空"
        client = ReplicateImageClient(base_url=server, timeout=300.0)

        # 测试连接
        if test:
            await client.test_connection()
            return

        # 列出图片
        if list_images_flag:
            await client.list_images()
            return

        # 运行演示
        if demo:
            await run_demo(client)
            return

        # 如果没有提供提示词，显示帮助
        if not prompts:
            server_example = f"http://{LOCAL_NETWORK_IP}:{server_configuration.image_generation_server_port}"
            logger.info("🎨 图片生成客户端")
            logger.info("\n快速开始:")
            logger.info(
                f'  python run_replicate_image_client.py -s {server_example} "a cat"'
            )
            logger.info(
                f'  python run_replicate_image_client.py -s {server_example} "cat" "dog"'
            )
            logger.info(
                f"  python run_replicate_image_client.py -s {server_example} --demo"
            )
            logger.info(
                f"  python run_replicate_image_client.py -s {server_example} --list"
            )
            logger.info(
                f"  python run_replicate_image_client.py -s {server_example} --test"
            )
            logger.info("\n详细帮助:")
            logger.info("  python run_replicate_image_client.py --help")
            return

        # 构建配置列表
        configs = []
        for prompt in prompts:
            config = {
                "prompt": prompt,
                "negative_prompt": negative,
                "width": width,
                "height": height,
                "num_inference_steps": steps,
                "guidance_scale": guidance,
            }

            # 可选参数
            if model:
                config["model"] = model

            configs.append(config)

        # 生成图片
        await client.generate_images(configs)

    except KeyboardInterrupt:
        logger.info("\n👋 用户中断")
    except Exception as e:
        logger.error(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
