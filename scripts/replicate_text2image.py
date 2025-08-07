#!/usr/bin/env python3
"""
Replicate 文生图工具
一个简单易用的文生图脚本，包含完整功能和使用示例
"""

import os
import sys
import time
import argparse
from pathlib import Path
import requests
import replicate
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class ReplicateTextToImage:
    """Replicate 文生图客户端"""
    
    # 可用的模型列表
    MODELS = {
        "sdxl-lightning": "bytedance/sdxl-lightning-4step:5f24084160c9089501c1b3545d9be3c27883ae2239b6f412990e82d4a6210f8f",
        "sdxl": "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
        "playground": "playgroundai/playground-v2.5-1024px-aesthetic:a45f82a1382bed5c7aeb861dac7c7d191b0fdf74d8d57c4a0e6ed7d4d0bf7d24",
        "realvis": "adirik/realvisxl-v2.0:7d6a2f9c4754477b12c14ed2a58f89bb85128edcdd581d24ce58b6926029de08",
        "ideogram-v3-turbo": "ideogram-ai/ideogram-v3-turbo:32a9584617b239dd119c773c8c18298d310068863d26499e6199538e9c29a586"
    }
    
    def __init__(self, api_token: str = None):
        """
        初始化 Replicate 客户端
        
        Args:
            api_token: Replicate API Token（可选，默认从环境变量 REPLICATE_API_TOKEN 读取）
        """
        # 从环境变量获取 API Token
        if api_token is None:
            api_token = os.getenv("REPLICATE_API_TOKEN")
            if not api_token:
                raise ValueError("未找到 REPLICATE_API_TOKEN，请在 .env 文件中设置或作为参数传入")
        
        # 设置 API Token
        os.environ["REPLICATE_API_TOKEN"] = api_token
        self.api_token = api_token
        print("✅ Replicate 客户端初始化完成")
    
    def list_models(self) -> dict:
        """获取可用模型列表"""
        return self.MODELS
    
    def estimate_cost(self, model_name: str) -> str:
        """估算单次生成成本"""
        cost_estimates = {
            "sdxl-lightning": "$0.005-0.01 (~2-5秒) 推荐测试",
            "sdxl": "$0.01-0.03 (~5-15秒) 通用推荐",
            "playground": "$0.02-0.04 (~10-20秒) 高质量但严格",
            "realvis": "$0.01-0.03 (~5-15秒) 写实风格",
            "ideogram-v3-turbo": "$0.01-0.02 (~3-8秒) 游戏开发推荐"
        }
        return cost_estimates.get(model_name, "未知")
    
    def get_available_models(self, tag: str = "text-to-image") -> list:
        """
        从Replicate API获取可用的模型列表
        
        Args:
            tag: 模型标签，默认为 "text-to-image"
            
        Returns:
            可用模型列表
        """
        api_url = "https://api.replicate.com/v1/models"
        headers = {"Authorization": f"Token {self.api_token}"}
        
        try:
            print(f"🔄 获取 {tag} 模型列表...")
            
            # 添加查询参数
            params = {}
            if tag:
                # 注意：实际API可能使用不同的参数名，需要查看文档
                params["tag"] = tag
                
            response = requests.get(api_url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("results", [])
                
                print(f"✅ 成功获取到 {len(models)} 个模型")
                
                # 过滤文生图相关模型
                text_to_image_models = []
                for model in models:
                    # 检查模型是否包含文生图相关标签或描述
                    description = (model.get("description") or "").lower()
                    name = (model.get("name") or "").lower()
                    tags = [tag.lower() for tag in (model.get("tags") or []) if tag]
                    
                    # 简单的关键词过滤
                    image_keywords = ["image", "txt2img", "text-to-image", "diffusion", "stable", "sdxl", "dalle"]
                    
                    if any(keyword in description or keyword in name for keyword in image_keywords) or \
                       any("image" in tag for tag in tags):
                        text_to_image_models.append({
                            "name": model.get("name") or "Unknown",
                            "owner": model.get("owner") or "Unknown",
                            "full_name": f"{model.get('owner') or 'Unknown'}/{model.get('name') or 'Unknown'}",
                            "description": (description[:100] + "..." if len(description) > 100 else description) or "无描述",
                            "url": model.get("url") or "",
                            "latest_version": model.get("latest_version", {}).get("id") if model.get("latest_version") else None
                        })
                
                return text_to_image_models
                
            else:
                print(f"❌ 获取模型列表失败，状态码: {response.status_code}")
                if response.status_code == 401:
                    print("💡 API Token 可能无效或已过期")
                return []
                
        except Exception as e:
            print(f"❌ 获取模型列表错误: {e}")
            return []

    def test_connection(self) -> bool:
        """测试连接是否正常"""
        test_url = "https://api.replicate.com/v1/models"
        headers = {"Authorization": f"Token {self.api_token}"}
        
        try:
            print("🔄 测试 Replicate API 连接...")
            response = requests.get(test_url, headers=headers, timeout=10)
            
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
    
    def generate_image(self, 
                      prompt: str,
                      model_name: str = "sdxl-lightning",
                      negative_prompt: str = "worst quality, low quality, blurry",
                      width: int = 768,
                      height: int = 768,
                      num_inference_steps: int = 4,
                      guidance_scale: float = 7.5) -> str:
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
        if model_name not in self.MODELS:
            raise ValueError(f"不支持的模型: {model_name}. 可用模型: {list(self.MODELS.keys())}")
        
        model_version = self.MODELS[model_name]
        cost_estimate = self.estimate_cost(model_name)
        
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
                    "scheduler": "K_EULER"
                }
            )
            
            # 获取图片 URL
            image_url = output[0] if isinstance(output, list) else output
            
            elapsed_time = time.time() - start_time
            print(f"✅ 生成完成! 耗时: {elapsed_time:.2f}秒")
            print(f"🔗 图片 URL: {image_url}")
            
            return image_url
            
        except Exception as e:
            print(f"❌ 生成失败: {e}")
            raise
    
    def download_image(self, image_url: str, save_path: str = None) -> str:
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
            timestamp = int(time.time())
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
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            file_size = len(response.content) / 1024  # KB
            print(f"✅ 下载完成! 文件大小: {file_size:.1f} KB")
            
            return save_path
            
        except Exception as e:
            print(f"❌ 下载失败: {e}")
            raise
    
    def generate_and_download(self, 
                            prompt: str,
                            output_dir: str = "generated_images",
                            **kwargs) -> str:
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
        image_url = self.generate_image(prompt, **kwargs)
        
        # 准备保存路径
        timestamp = int(time.time())
        model_name = kwargs.get('model_name', 'sdxl-lightning')
        filename = f"{model_name}_{timestamp}.png"
        save_path = Path(output_dir) / filename
        
        # 下载图片
        downloaded_path = self.download_image(image_url, str(save_path))
        
        return downloaded_path


def run_demo():
    """运行演示示例"""
    print("=" * 60)
    print("🎮 Replicate 文生图演示")
    print("=" * 60)
    
    # 初始化客户端
    client = ReplicateTextToImage()
    
    # 1. 测试连接
    if not client.test_connection():
        print("❌ 连接测试失败，请检查网络设置")
        return
    
    # 2. 查看可用模型
    print("\n📋 可用模型:")
    models = client.list_models()
    for name in models.keys():
        cost = client.estimate_cost(name)
        print(f"  - {name}: {cost}")
    
    # 3. 生成测试图片
    print("\n🎨 生成测试图片...")
    
    try:
        # 快速测试 - 使用成本最低的模型
        test_prompt = "a cute cat sitting in a garden, sunny day, photorealistic"
        
        saved_path = client.generate_and_download(
            prompt=test_prompt,
            model_name="sdxl-lightning",  # 使用最快最便宜的模型
            output_dir="generated_images"
        )
        
        print(f"\n🎉 演示完成! 图片已保存到: {saved_path}")
        print("💡 您可以查看生成的图片，然后尝试其他提示词")
        
    except Exception as e:
        print(f"❌ 演示失败: {e}")


def main():
    """主函数 - 命令行接口"""
    parser = argparse.ArgumentParser(description="Replicate 文生图工具")
    parser.add_argument("prompt", nargs='?', help="文本提示词")
    parser.add_argument("--model", "-m", default="sdxl-lightning", 
                       choices=list(ReplicateTextToImage.MODELS.keys()),
                       help="使用的模型 (默认: sdxl-lightning)")
    parser.add_argument("--negative", "-n", default="worst quality, low quality, blurry",
                       help="负向提示词")
    parser.add_argument("--width", "-w", type=int, default=768, help="图片宽度 (默认: 768)")
    parser.add_argument("--height", type=int, default=768, help="图片高度 (默认: 768)")
    parser.add_argument("--size", choices=["small", "medium", "large", "wide", "tall"], 
                       help="预设尺寸: small(512x512), medium(768x768), large(1024x1024), wide(1024x768), tall(768x1024)")
    parser.add_argument("--steps", "-s", type=int, default=4, help="推理步数")
    parser.add_argument("--guidance", "-g", type=float, default=7.5, help="引导比例")
    parser.add_argument("--output", "-o", default="generated_images", help="输出目录")
    parser.add_argument("--list-models", action="store_true", help="列出可用模型")
    parser.add_argument("--discover-models", action="store_true", help="从API发现新的文生图模型")
    parser.add_argument("--demo", action="store_true", help="运行演示")
    parser.add_argument("--test", action="store_true", help="测试连接")
    
    args = parser.parse_args()
    
    # 初始化客户端
    try:
        client = ReplicateTextToImage()
        
        # 处理预设尺寸
        if args.size:
            size_presets = {
                "small": (512, 512),
                "medium": (768, 768), 
                "large": (1024, 1024),
                "wide": (1024, 768),
                "tall": (768, 1024)
            }
            args.width, args.height = size_presets[args.size]
            print(f"📐 使用预设尺寸 '{args.size}': {args.width}x{args.height}")
        
        # 如果是运行演示
        if args.demo:
            run_demo()
            return
        
        # 如果是测试连接
        if args.test:
            client.test_connection()
            return
        
        # 如果是发现新模型
        if args.discover_models:
            print("🔍 发现可用的文生图模型:")
            models = client.get_available_models()
            if models:
                for i, model in enumerate(models[:20], 1):  # 只显示前20个
                    print(f"{i:2d}. {model['full_name']}")
                    print(f"    📝 {model['description']}")
                    if model['latest_version']:
                        print(f"    🆔 版本: {model['latest_version']}")
                    print()
                if len(models) > 20:
                    print(f"... 还有 {len(models) - 20} 个模型未显示")
            else:
                print("❌ 未能获取到模型列表")
            return
        
        # 如果只是列出模型
        if args.list_models:
            print("🎨 可用模型:")
            for name, version in client.list_models().items():
                cost = client.estimate_cost(name)
                print(f"  - {name}: {cost}")
            return
        
        # 如果没有提供提示词，显示帮助
        if not args.prompt:
            print("🎨 Replicate 文生图工具")
            print("\n快速开始:")
            print("  python replicate_text2image.py --demo            # 运行演示")
            print("  python replicate_text2image.py --test            # 测试连接")
            print("  python replicate_text2image.py --list-models     # 查看内置模型")
            print("  python replicate_text2image.py --discover-models # 发现新模型")
            print("  python replicate_text2image.py \"生成一只猫\"       # 生成图片")
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
        saved_path = client.generate_and_download(
            prompt=args.prompt,
            model_name=args.model,
            negative_prompt=args.negative,
            width=args.width,
            height=args.height,
            num_inference_steps=args.steps,
            guidance_scale=args.guidance,
            output_dir=args.output
        )
        
        print(f"\n🎉 完成! 图片已保存到: {saved_path}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
