# from typing import final, override
# #import uuid
# import asyncio
# from pathlib import Path
# from loguru import logger
# from ..entitas import ExecuteProcessor, ExecuteProcessor, Matcher
# from ..game.tcg_game import TCGGame
# from ..models import AppearanceComponent, ActorComponent
# from ..replicate import (
#     load_replicate_config,
#     get_default_generation_params,
#     generate_and_download,
# )
# #import uuid


# @final
# class ImagesSystem(ExecuteProcessor):

#     ####################################################################################################################################
#     def __init__(
#         self,
#         game_context: TCGGame,
#     ) -> None:
#         self._game = game_context
#         # 加载 Replicate 配置
#         self._replicate_config = load_replicate_config(Path("replicate_models.json"))
#         self._models = self._replicate_config.image_models.model_dump(
#             by_alias=True, exclude_none=True
#         )
#         self._default_params = get_default_generation_params()

#     ####################################################################################################################################
#     async def _generate_character_image(
#         self, appearance_comp: AppearanceComponent, game_name: str, player_name: str
#     ) -> str | None:
#         """
#         为单个角色生成图片

#         Args:
#             appearance_comp: 外观组件
#             game_name: 游戏名称

#         Returns:
#             生成的图片路径，失败返回 None
#         """
#         try:
#             # 构建输出目录路径
#             output_dir = (
#                 f"generated_images/{player_name}/{game_name}/{appearance_comp.name}"
#             )

#             # 生成并下载图片
#             saved_path = await generate_and_download(
#                 prompt=appearance_comp.appearance,
#                 model_name="ideogram-v3-turbo",  # 使用稳定的模型
#                 negative_prompt=self._default_params["negative_prompt"],
#                 width=512,  # 固定尺寸
#                 height=512,
#                 num_inference_steps=self._default_params["num_inference_steps"],
#                 guidance_scale=self._default_params["guidance_scale"],
#                 output_dir=output_dir,
#                 models_config=self._models,
#             )

#             logger.info(f"✅ 角色 {appearance_comp.name} 图片生成成功: {saved_path}")
#             return saved_path

#         except Exception as e:
#             logger.error(f"❌ 角色 {appearance_comp.name} 图片生成失败: {e}")
#             return None

#     ####################################################################################################################################
#     @override
#     async def execute(self) -> None:
#         logger.debug("ImagesSystem execute called")
#         entities = self._game.get_group(
#             Matcher(
#                 all_of=[AppearanceComponent, ActorComponent],
#             )
#         ).entities.copy()

#         if not entities:
#             return

#         logger.info(f"🎨 开始为 {len(entities)} 个角色并发生成图片...")

#         # 收集所有需要生成图片的角色信息
#         generation_tasks = []
#         for entity in entities:
#             appearance_comp = entity.get(AppearanceComponent)
#             assert appearance_comp is not None, "Missing AppearanceComponent"
#             logger.debug(
#                 f"{self._game.name}, 准备生成图片: {appearance_comp.name} - {appearance_comp.appearance[:50]}..."
#             )

#             # 创建异步任务
#             task = self._generate_character_image(
#                 appearance_comp=appearance_comp,
#                 game_name=self._game.name,
#                 player_name=self._game._player.name,
#             )
#             generation_tasks.append(task)

#         # 并发执行所有图片生成任务
#         if generation_tasks:
#             results = await asyncio.gather(*generation_tasks, return_exceptions=True)

#             # 统计结果
#             success_count = sum(1 for result in results if isinstance(result, str))
#             total_count = len(results)

#             logger.info(f"🎉 图片生成完成! 成功: {success_count}/{total_count}")

#             # 记录详细结果
#             for i, result in enumerate(results):
#                 if isinstance(result, Exception):
#                     logger.warning(f"任务 {i+1} 异常: {result}")
#                 elif result is None:
#                     logger.warning(f"任务 {i+1} 生成失败")
#                 else:
#                     logger.debug(f"任务 {i+1} 成功: {result}")
#         else:
#             logger.info("📝 没有需要生成图片的角色")

#     ####################################################################################################################################
