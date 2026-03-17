from typing import Final, List, final, override
from loguru import logger
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    WorldComponent,
    DungeonGenerationComponent,
    SetupDungeonAction,
)
from ..game.tcg_game import TCGGame
from ..utils import extract_json_from_code_block
from ..demo.global_settings import RPG_CAMPAIGN_SETTING, RPG_SYSTEM_RULES
from ..demo.entity_factory import build_stage_system_message


####################################################################################################################################
def _build_dungeon_ecology_prompt() -> str:
    """构建地下城生态环境生成提示词。

    无需任何种子数据，完全由世界观框架驱动创作。
    世界观已通过调用方的 SystemMessage 提供给 LLM。

    Returns:
        要求 LLM 创作地下城 name 与 ecology 的提示词
    """
    return """# 任务：创作一个地下城的生态环境

请在当前世界观框架内，为一处自然地点生成名称与生态环境描写。

## 要求

- **name**：地下城全名，采用「地下城.XXXX」命名格式，体现地貌特征
- **ecology**：该地点的生态环境写照，100-200字，只描述「这里有什么」：
  - 地形结构与光照、温湿度等感官细节
  - 植被、土质、水文等自然要素
  - 动物活动留下的痕迹（足迹、爪痕、粪便、巢穴碎片、骨骸），不直接点名生物
  - 气味、声音等环境线索
  - 禁忌：不出现生物名称、不叙述故事、不描写角色行为、不使用「威胁」「挑战」「危险」等评价性词汇

## 输出格式

```json
{{
  "name": "地下城.XXX",
  "ecology": "..."
}}
```

严格按 JSON 格式输出，不要添加其他内容。"""


####################################################################################################################################
@final
class DungeonEcologyResponse(BaseModel):
    """地下城生态环境生成响应数据模型。

    用于解析和验证 AI 返回的地下城概念 JSON 数据。

    Attributes:
        name: 地下城全名，格式为「地下城.XXXX」
        ecology: 地下城生态环境描述
    """

    name: str = ""
    ecology: str = ""


####################################################################################################################################
@final
class DungeonStageResponse(BaseModel):
    """地下城 Stage 设定数据响应模型。

    用于解析和验证 AI 返回的地下城场景设定 JSON 数据。

    Attributes:
        stage_name: 场景全名，格式为「场景.XXXX」
        profile_name: 场景英文标识（snake_case），对应 StageProfile.name
        profile: 场景感官环境描写，对应 StageProfile.profile
    """

    stage_name: str = ""
    profile_name: str = ""
    profile: str = ""


####################################################################################################################################
def _build_dungeon_stage_prompt(
    dungeon_name: str,
    ecology: str,
    stage_index: int,
    total_stages: int,
    existing_stages: List["DungeonStageResponse"],
) -> str:
    """构建地下城 Stage 设定数据生成提示词。

    以地下城生态描述为种子，结合位置序号与已生成场景列表，
    引导 LLM 差异化创作具有递进感的场景。

    Args:
        dungeon_name: 地下城全名
        ecology: 地下城整体生态描述
        stage_index: 当前场景序号（1-based）
        total_stages: 场景总数
        existing_stages: 已生成的场景响应列表，用于避免重复

    Returns:
        完整的 Stage 设定生成提示词
    """
    existing_info = ""
    if existing_stages:
        lines = []
        for i, s in enumerate(existing_stages, start=1):
            lines.append(f"  {i}. {s.stage_name}：{s.profile}")
        existing_info = (
            "## 已生成的场景（禁止重复，内容须有差异）\n\n" + "\n".join(lines) + "\n\n"
        )

    depth_hint = {
        1: "入口区域，相对开阔，生物活动痕迹疏散",
        total_stages: "最深处，空间压迫，生物活动痕迹密集且强烈",
    }.get(stage_index, f"中段区域（第 {stage_index} / 共 {total_stages} 个场景），深度与复杂度介于入口与深处之间")

    return f"""# 任务：为地下城创作第 {stage_index} / 共 {total_stages} 个战斗场景

## 地下城信息

- **地下城名称**：{dungeon_name}
- **整体生态**：{ecology}

## 当前场景的位置定位

{depth_hint}

{existing_info}## 要求

根据上述信息，创作本场景：

- **stage_name**：场景全名，采用「场景.XXXX」命名格式，体现该局部区域的地貌特征，与已有场景名称不重复
- **profile_name**：场景英文标识，snake_case 格式（如 `forest_edge`、`deep_pool`），简洁且有辨识度，与已有标识不重复
- **profile**：该场景的感官环境描写，50-100字，只描述「这里有什么」：
  - 地形结构、光照、温湿度等直观感受
  - 地面材质、植被或水体等自然要素
  - 动物活动留下的痕迹（足迹、爪痕、巢穴残迹、骨骸），不直接点名生物
  - 气味或声音等感官线索
  - 禁忌：不出现生物名称、不叙述故事、不描写角色行为、不使用「威胁」「挑战」「危险」等评价性词汇

## 输出格式

```json
{{
  "stage_name": "场景.XXX",
  "profile_name": "snake_case_name",
  "profile": "..."
}}
```

严格按 JSON 格式输出，不要添加其他内容。"""


####################################################################################################################################
@final
class DungeonGenerationSystem(ReactiveProcessor):
    """地下城生成系统。

    反应式处理器，监听实体上 SetupDungeonAction 的添加事件，
    执行地下城的完整创建流程。

    工作流程：
        1. 监听实体上 SetupDungeonAction 动作组件的添加事件
        2. 获取地下城生成世界系统实体（包含 DungeonGenerationComponent）
        3. 依次执行地下城创建子任务
        4. 由 ActionCleanupSystem 自动清除 SetupDungeonAction

    Attributes:
        _game: 游戏实例引用

    Note:
        - SetupDungeonAction 由 home_actions.activate_setup_dungeon() 在家园状态下添加
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {
            Matcher(SetupDungeonAction): GroupEvent.ADDED,
        }

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SetupDungeonAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        world_system_entities = self._game.get_group(
            Matcher(all_of=[WorldComponent, DungeonGenerationComponent])
        ).entities.copy()

        if not world_system_entities:
            logger.error("未找到地下城生成系统实体，无法执行地下城创建流程")
            return

        assert len(world_system_entities) == 1, "存在多个地下城生成系统实体，数据异常"
        world_system_entity = next(iter(world_system_entities))

        for entity in entities:
            await self._setup_dungeon(entity, world_system_entity)

    ####################################################################################################################################
    async def _setup_dungeon(self, entity: Entity, world_system_entity: Entity) -> None:
        """执行地下城完整创建流程。

        Args:
            entity: 携带 SetupDungeonAction 的实体（玩家实体）
            world_system_entity: 地下城生成世界系统实体（其 SystemMessage 已含世界观）
        """
        logger.info(
            f"[DungeonGenerationSystem] 开始地下城创建流程: entity={entity.name}"
        )

        # Step 1: 生成地下城生态环境概念
        ecology_response = await self._step1_generate_ecology(world_system_entity)
        if ecology_response is None:
            return

        # Step 2: 循环生成地下城 Stage 设定数据
        stage_count = 2
        existing_stages: List[DungeonStageResponse] = []
        for i in range(1, stage_count + 1):
            stage_response = await self._step2_generate_stage(
                world_system_entity, ecology_response, i, stage_count, existing_stages
            )
            if stage_response is not None:
                existing_stages.append(stage_response)
            else:
                logger.warning(
                    f"[DungeonGenerationSystem] Stage {i}/{stage_count} 生成失败，跳过"
                )

    ####################################################################################################################################
    async def _step1_generate_ecology(
        self, world_system_entity: Entity
    ) -> DungeonEcologyResponse | None:
        """Step 1：调用 LLM 生成地下城生态环境概念（name + ecology）。

        Args:
            world_system_entity: 地下城生成世界系统实体

        Returns:
            解析成功的 DungeonEcologyResponse；解析失败时返回 None
        """
        chat_client = ChatClient(
            name=world_system_entity.name,
            prompt=_build_dungeon_ecology_prompt(),
            context=self._game.get_agent_context(world_system_entity).context,
        )
        await chat_client.async_chat()

        try:
            ecology_response = DungeonEcologyResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )
        except Exception as e:
            logger.error(
                f"[DungeonGenerationSystem][Step 1] 解析地下城生态环境失败: {e}\n"
                f"原始内容:\n{chat_client.response_content}"
            )
            return None

        logger.info(
            f"[DungeonGenerationSystem][Step 1] 地下城生态环境生成完成:\n"
            f"  name: {ecology_response.name}\n"
            f"  ecology: {ecology_response.ecology}"
        )
        return ecology_response

    ####################################################################################################################################
    async def _step2_generate_stage(
        self,
        world_system_entity: Entity,
        ecology_response: DungeonEcologyResponse,
        stage_index: int,
        total_stages: int,
        existing_stages: List[DungeonStageResponse],
    ) -> DungeonStageResponse | None:
        """Step 2：调用 LLM 生成一个 Stage 的设定数据。

        生成 stage_name、profile_name、profile 三个字段，并在本地组装出
        system_message（格式与 entity_factory.create_stage 保持一致）。
        本步骤仅生成并记录日志，不创建实体。

        Args:
            world_system_entity: 地下城生成世界系统实体
            ecology_response: Step 1 生成的地下城生态环境数据
            stage_index: 当前场景序号（1-based）
            total_stages: 场景总数
            existing_stages: 已生成的场景列表，用于避免重复

        Returns:
            解析成功的 DungeonStageResponse；失败时返回 None
        """
        chat_client = ChatClient(
            name=world_system_entity.name,
            prompt=_build_dungeon_stage_prompt(
                dungeon_name=ecology_response.name,
                ecology=ecology_response.ecology,
                stage_index=stage_index,
                total_stages=total_stages,
                existing_stages=existing_stages,
            ),
            context=self._game.get_agent_context(world_system_entity).context,
        )
        await chat_client.async_chat()

        try:
            stage_response = DungeonStageResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )
        except Exception as e:
            logger.error(
                f"[DungeonGenerationSystem][Step 2] Stage {stage_index}/{total_stages} 解析失败: {e}\n"
                f"原始内容:\n{chat_client.response_content}"
            )
            return None

        # 按 entity_factory.create_stage 的模板组装 system_message
        system_message = build_stage_system_message(
            stage_name=stage_response.stage_name,
            campaign_setting=RPG_CAMPAIGN_SETTING,
            system_rules=RPG_SYSTEM_RULES,
            profile=stage_response.profile,
        )

        logger.info(
            f"[DungeonGenerationSystem][Step 2] Stage {stage_index}/{total_stages} 生成完成:\n"
            f"  stage_name:   {stage_response.stage_name}\n"
            f"  profile_name: {stage_response.profile_name}\n"
            f"  profile:      {stage_response.profile}\n"
            f"  system_message (前80字): {system_message[:80]}..."
        )
        return stage_response

    ####################################################################################################################################
