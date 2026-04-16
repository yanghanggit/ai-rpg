from typing import Final, List, final, override
from pathlib import Path
from loguru import logger
from pydantic import BaseModel
from ..chat_client import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    WorldComponent,
    DungeonGenerationComponent,
    GenerateDungeonAction,
    IllustrateDungeonAction,
    Dungeon,
    DungeonRoom,
    StageProfile,
    StageType,
    CharacterSheet,
    ActorType,
    CharacterStats,
)
from ..game.tcg_game import TCGGame
from ..game.config import DEBUG_CACHE_DIR, DUNGEONS_DIR
from ..utils import extract_json_from_code_block
from ..demo.global_settings import RPG_CAMPAIGN_SETTING
from ..demo.entity_factory import create_actor, create_stage

# from ..demo.common_skills import BEAST_ATTACK_SKILL
from ..demo.rpg_system_rules import (
    RPG_SYSTEM_RULES,
)


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
    """地下城单个 Stage 设定数据响应模型。

    Attributes:
        stage_name: 场景全名，格式为「场景.XXXX」
        profile_name: 场景英文标识（snake_case），对应 StageProfile.name
        profile: 场景感官环境描写，对应 StageProfile.profile
    """

    stage_name: str = ""
    profile_name: str = ""
    profile: str = ""


####################################################################################################################################
@final
class DungeonStagesResponse(BaseModel):
    """地下城批量 Stage 设定数据响应模型。

    单次 LLM 调用返回指定数量的场景设定，以 stages 数组承载。

    Attributes:
        stages: 场景设定列表，顺序对应从入口到深处的递进
    """

    stages: List[DungeonStageResponse] = []


####################################################################################################################################
@final
class DungeonActorBlueprint(BaseModel):
    """地下城怪物实体创建所需的原始字段（无 system_message，供下一阶段组装）。

    Attributes:
        actor_name: 角色全名，格式为「角色.常物/精怪/大妖.XXXX」
        character_sheet_name: 角色英文标识（snake_case）
        profile: 第一人称 AI 扮演描述（性格、行为习惯）
        base_body: 第三人称外观描述
    """

    actor_name: str = ""
    character_sheet_name: str = ""
    profile: str = ""
    base_body: str = ""


####################################################################################################################################
@final
class DungeonStageBlueprint(BaseModel):
    """地下城单个场景实体创建所需的原始字段（包含配对的怪物蓝图）。

    actor 非 Optional：Step 3 actor 生成失败的场景直接不进入 DungeonBlueprint。

    Attributes:
        stage_name: 场景全名，格式为「场景.XXXX」
        profile_name: 场景英文标识（snake_case）
        profile: 场景感官环境描写
        actor: 与该场景配对的怪物蓝图
    """

    stage_name: str = ""
    profile_name: str = ""
    profile: str = ""
    actor: DungeonActorBlueprint = DungeonActorBlueprint()
    image_url: str = ""


####################################################################################################################################
@final
class DungeonBlueprint(BaseModel):
    """地下城完整蓝图收集器，承载3步 LLM 流程的全部产出。

    由 Step 1 创建骨架，Step 3 向 stages 逐项填充后达到完整状态，
    可直接传入后续实体创建流程。

    Attributes:
        dungeon_name: 地下城全名，格式为「地下城.XXXX」
        ecology: 地下城整体生态环境描述
        stages: 已完整配对（场景+怪物）的场景蓝图列表
    """

    dungeon_name: str = ""
    ecology: str = ""
    stages: List[DungeonStageBlueprint] = []
    image_url: str = ""


####################################################################################################################################
def _build_dungeon_stages_prompt(
    dungeon_name: str, ecology: str, total_stages: int
) -> str:
    """构建批量生成地下城 Stage 设定数据的提示词。

    单次调用要求 LLM 一次性返回 total_stages 个场景，以 JSON 数组输出。
    场景顺序从入口到最深处，具有递进感，各场景名称与标识不重复。

    Args:
        dungeon_name: 地下城全名
        ecology: 地下城整体生态描述
        total_stages: 需要生成的场景数量

    Returns:
        完整的批量 Stage 设定生成提示词
    """
    return f"""# 任务：为地下城一次性创作 {total_stages} 个战斗场景

## 地下城信息

- **地下城名称**：{dungeon_name}
- **整体生态**：{ecology}

## 场景顺序说明

按从入口到最深处的顺序排列，共 {total_stages} 个场景：
- 第 1 个：入口区域，相对开阔，生物活动痕迹疏散
- 第 {total_stages} 个：最深处，空间压迫，生物活动痕迹密集且强烈
- 中间场景：深度与复杂度介于入口与深处之间，逐步递进

## 每个场景的要求

- **stage_name**：场景全名，采用「场景.XXXX」命名格式，体现该局部区域的地貌特征，所有场景名称不重复
- **profile_name**：场景英文标识，snake_case 格式（如 `forest_edge`、`deep_pool`），所有标识不重复
- **profile**：该场景的感官环境描写，50-100字，只描述「这里有什么」：
  - 地形结构、光照、温湿度等直观感受
  - 地面材质、植被或水体等自然要素
  - 动物活动留下的痕迹（足迹、爪痕、巢穴残迹、骨骸），不直接点名生物
  - 气味或声音等感官线索
  - 禁忌：不出现生物名称、不叙述故事、不描写角色行为、不使用「威胁」「挑战」「危险」等评价性词汇

## 输出格式

```json
{{
  "stages": [
    {{
      "stage_name": "场景.XXX",
      "profile_name": "snake_case_name",
      "profile": "..."
    }}
  ]
}}
```

严格按 JSON 格式输出，stages 数组中包含恰好 {total_stages} 个元素，不要添加其他内容。"""


####################################################################################################################################
@final
class DungeonActorResponse(BaseModel):
    """地下城怪物设定数据响应模型（概念/文字，无数值/技能）。

    Attributes:
        actor_name: 角色全名，格式为「角色.常物/精怪/大妖.XXXX」
        character_sheet_name: 角色英文标识（snake_case）
        profile: 第一人称 AI 扮演描述（性格、行为习惯）
        base_body: 第三人称外观描述
    """

    actor_name: str = ""
    character_sheet_name: str = ""
    profile: str = ""
    base_body: str = ""


####################################################################################################################################
def _build_dungeon_actor_prompt(
    dungeon_name: str, ecology: str, stage_name: str, stage_profile: str
) -> str:
    """构建为单个 Stage 生成怪物设定数据的提示词。

    Args:
        dungeon_name: 地下城全名
        ecology: 地下城整体生态描述
        stage_name: 当前场景全名
        stage_profile: 当前场景感官环境描写

    Returns:
        要求 LLM 创作一个栖居于该场景的怪物设定的提示词
    """
    return f"""# 任务：为场景创作一个栖居怪物的设定

## 所在地下城

- **地下城名称**：{dungeon_name}
- **整体生态**：{ecology}

## 当前场景

- **场景名称**：{stage_name}
- **场景环境**：{stage_profile}

## 要求

- **actor_name**：角色全名，采用「角色.常物/精怪/大妖.XXXX」格式，XXXX 体现该生物的特征
- **character_sheet_name**：角色英文标识，snake_case 格式（如 `bone_crawler`、`mist_spirit`）
- **profile**：第一人称 AI 扮演描述，50-100字，描述该生物的性格、行为倾向、与环境的关系
  - 禁忌：不出现战斗数值、技能名称、等级等游戏机制词汇
- **base_body**：第三人称外观描述，30-60字，描述该生物的形态、材质、动态特征
  - 禁忌：不出现战斗数值、技能名称、等级等游戏机制词汇

## 输出格式

```json
{{
  "actor_name": "角色.精怪.XXX",
  "character_sheet_name": "snake_case_name",
  "profile": "...",
  "base_body": "..."
}}
```

严格按 JSON 格式输出，不要添加其他内容。"""


####################################################################################################################################
@final
class GenerateDungeonActionSystem(ReactiveProcessor):
    """地下城文本数据生成系统（Steps 1-4）。

    反应式处理器，监听 GenerateDungeonAction 的添加事件，执行地下城
    生态→场景→怪物→组装 四步文本数据创建流程。
    成功后添加 IllustrateDungeonAction 触发图片生成系统；失败时不添加，
    图片生成系统自然不执行。

    工作流程：
        1. 监听 GenerateDungeonAction 添加事件
        2. 获取地下城生成世界系统实体（包含 DungeonGenerationComponent）
        3. 执行 Steps 1-4 文本创建子任务
        4. 成功后保存 blueprint，添加 IllustrateDungeonAction
        5. 动作由 ActionCleanupSystem 自动清除

    Attributes:
        _game: 游戏实例引用

    Note:
        - GenerateDungeonAction 由 home_actions.activate_generate_dungeon() 在家园状态下添加
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {
            Matcher(GenerateDungeonAction): GroupEvent.ADDED,
        }

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(GenerateDungeonAction)

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
            await self._generate_dungeon(entity, world_system_entity)

    ####################################################################################################################################
    async def _generate_dungeon(
        self, entity: Entity, world_system_entity: Entity
    ) -> None:
        """调用 LLM 执行地下城完整生成流程，输出 JSON/图片文件。

        Args:
            entity: 携带 GenerateDungeonAction 的实体（玩家实体）
            world_system_entity: 地下城生成世界系统实体（其 SystemMessage 已含世界观）
        """
        logger.info(
            f"[GenerateDungeonActionSystem] 开始地下城文本数据创建流程: entity={entity.name}"
        )

        # Step 1: 生成地下城生态环境概念，创建 blueprint 骨架
        blueprint = await self._step1_generate_ecology(world_system_entity)
        if blueprint is None:
            return

        # Step 2: 批量生成地下城 Stage 设定数据
        stage_responses = await self._step2_generate_stages(
            world_system_entity, blueprint, stage_count=2
        )

        # Step 3: 为每个 Stage 并发生成怪物，配对成功后写入 blueprint.stages
        await self._step3_generate_actors(
            world_system_entity,
            blueprint,
            stage_responses,
        )

        logger.info(
            f"[GenerateDungeonActionSystem] Blueprint 收集完成:\n"
            f"  dungeon_name: {blueprint.dungeon_name}\n"
            f"  ecology:      {blueprint.ecology}\n"
            f"  stages ({len(blueprint.stages)}):\n"
            + "\n".join(
                f"    [{i}] stage={s.stage_name}  actor={s.actor.actor_name}"
                for i, s in enumerate(blueprint.stages, start=1)
            )
        )

        # Step 4: 将 DungeonBlueprint 组装为完整 Dungeon 实体树，写入 DUNGEONS_DIR
        dungeon = await self._step4_build_dungeon(blueprint)
        if dungeon is None:
            return

        dungeon_path: Path = DUNGEONS_DIR / f"{dungeon.name}.json"
        dungeon_path.write_text(dungeon.model_dump_json(indent=4), encoding="utf-8")
        logger.info(
            f"[GenerateDungeonActionSystem] Dungeon 已保存: {dungeon_path}\n"
            f"  rooms ({len(dungeon.rooms)}): "
            + ", ".join(
                f"{room.stage.name}({room.stage.actors[0].name if room.stage.actors else 'no actor'})"
                for room in dungeon.rooms
            )
        )

        # 保存 DungeonBlueprint JSON（image_url 字段暂为空，待 IllustrateDungeonActionSystem 填充）
        save_path: Path = DEBUG_CACHE_DIR / f"{blueprint.dungeon_name}.json"
        save_path.write_text(blueprint.model_dump_json(indent=4), encoding="utf-8")
        logger.info(
            f"[GenerateDungeonActionSystem] DungeonBlueprint 已保存: {save_path}"
        )

        # 添加 IllustrateDungeonAction，触发图片生成系统
        entity.replace(IllustrateDungeonAction, entity.name, blueprint.dungeon_name)
        logger.info(
            f"[GenerateDungeonActionSystem] 添加 IllustrateDungeonAction: "
            f"dungeon={blueprint.dungeon_name}"
        )

    ####################################################################################################################################
    async def _step1_generate_ecology(
        self, world_system_entity: Entity
    ) -> DungeonBlueprint | None:
        """Step 1：调用 LLM 生成地下城生态环境概念，创建并返回 DungeonBlueprint 骨架。

        Args:
            world_system_entity: 地下城生成世界系统实体

        Returns:
            含 dungeon_name/ecology、stages 为空列表的 DungeonBlueprint；失败返回 None
        """
        chat_client = DeepSeekClient(
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
                f"[GenerateDungeonActionSystem][Step 1] 解析地下城生态环境失败: {e}\n"
                f"原始内容:\n{chat_client.response_content}"
            )
            return None

        blueprint = DungeonBlueprint(
            dungeon_name=ecology_response.name,
            ecology=ecology_response.ecology,
        )
        logger.info(
            f"[GenerateDungeonActionSystem][Step 1] 地下城生态环境生成完成:\n"
            f"  dungeon_name: {blueprint.dungeon_name}\n"
            f"  ecology:      {blueprint.ecology}"
        )
        return blueprint

    ####################################################################################################################################
    async def _step2_generate_stages(
        self,
        world_system_entity: Entity,
        blueprint: DungeonBlueprint,
        stage_count: int,
    ) -> List[DungeonStageResponse]:
        """Step 2：单次调用 LLM 批量生成所有 Stage 设定数据。

        一次性返回 stage_count 个场景（stages 数组），减少 API 调用次数。
        本步骤仅生成并记录日志，不创建实体，不写入 blueprint（由 Step 3 配对后写入）。

        Args:
            world_system_entity: 地下城生成世界系统实体
            blueprint: Step 1 创建的 DungeonBlueprint 骨架（提供 dungeon_name/ecology）
            stage_count: 需要生成的场景数量

        Returns:
            DungeonStageResponse 列表；解析失败时返回空列表
        """
        chat_client = DeepSeekClient(
            name=world_system_entity.name,
            prompt=_build_dungeon_stages_prompt(
                dungeon_name=blueprint.dungeon_name,
                ecology=blueprint.ecology,
                total_stages=stage_count,
            ),
            context=self._game.get_agent_context(world_system_entity).context,
        )
        await chat_client.async_chat()

        try:
            stages_response = DungeonStagesResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )
        except Exception as e:
            logger.error(
                f"[GenerateDungeonActionSystem][Step 2] 批量解析 Stage 设定数据失败: {e}\n"
                f"原始内容:\n{chat_client.response_content}"
            )
            return []

        for i, stage in enumerate(stages_response.stages, start=1):
            logger.info(
                f"[GenerateDungeonActionSystem][Step 2] Stage {i}/{len(stages_response.stages)} 生成完成:\n"
                f"  stage_name:   {stage.stage_name}\n"
                f"  profile_name: {stage.profile_name}\n"
                f"  profile:      {stage.profile}"
            )
        return stages_response.stages

    ####################################################################################################################################
    async def _step3_generate_actors(
        self,
        world_system_entity: Entity,
        blueprint: DungeonBlueprint,
        stage_responses: List[DungeonStageResponse],
    ) -> None:
        """Step 3：为每个 Stage 并发生成怪物设定，配对成功后写入 blueprint.stages。

        为每个 Stage 创建独立的 DeepSeekClient，通过 batch_chat 并发请求 LLM。
        解析成功的 (stage, actor) 对构造 DungeonStageBlueprint 写入 blueprint.stages；
        解析失败的 Stage 整体跳过，不进入 blueprint。

        Args:
            world_system_entity: 地下城生成世界系统实体
            blueprint: Step 1 创建的 DungeonBlueprint（本步骤向其 stages 写入数据）
            stage_responses: Step 2 生成的场景设定列表
        """
        if not stage_responses:
            return

        context = self._game.get_agent_context(world_system_entity).context
        clients: List[DeepSeekClient] = [
            DeepSeekClient(
                name=stage.stage_name,
                prompt=_build_dungeon_actor_prompt(
                    dungeon_name=blueprint.dungeon_name,
                    ecology=blueprint.ecology,
                    stage_name=stage.stage_name,
                    stage_profile=stage.profile,
                ),
                context=context,
            )
            for stage in stage_responses
        ]

        await DeepSeekClient.batch_chat(clients)

        for i, (client, stage) in enumerate(zip(clients, stage_responses), start=1):
            try:
                actor_response = DungeonActorResponse.model_validate_json(
                    extract_json_from_code_block(client.response_content)
                )
            except Exception as e:
                logger.error(
                    f"[GenerateDungeonActionSystem][Step 3] Stage '{stage.stage_name}' 解析怪物设定失败，该场景不纳入 blueprint: {e}\n"
                    f"原始内容:\n{client.response_content}"
                )
                continue

            stage_blueprint = DungeonStageBlueprint(
                stage_name=stage.stage_name,
                profile_name=stage.profile_name,
                profile=stage.profile,
                actor=DungeonActorBlueprint(
                    actor_name=actor_response.actor_name,
                    character_sheet_name=actor_response.character_sheet_name,
                    profile=actor_response.profile,
                    base_body=actor_response.base_body,
                ),
            )
            blueprint.stages.append(stage_blueprint)
            logger.info(
                f"[GenerateDungeonActionSystem][Step 3] Stage+Actor {i}/{len(stage_responses)} 写入 blueprint:\n"
                f"  stage_name:           {stage_blueprint.stage_name}\n"
                f"  profile_name:         {stage_blueprint.profile_name}\n"
                f"  actor_name:           {stage_blueprint.actor.actor_name}\n"
                f"  character_sheet_name: {stage_blueprint.actor.character_sheet_name}"
            )

    ####################################################################################################################################

    async def _step4_build_dungeon(self, blueprint: DungeonBlueprint) -> Dungeon | None:
        """Step 4：将 DungeonBlueprint 组装为完整的 Dungeon 实体树。

        无 LLM 调用，纯数据组装。对 blueprint.stages 中每个 DungeonStageBlueprint：
        - 用 create_stage 构建 Stage 实体
        - 用 create_actor 构建 Actor 实体，挂载 BEAST_ATTACK_SKILL
        - 拼成 DungeonRoom 列表，最终封装为 Dungeon

        Args:
            blueprint: Step 3 填充完整的 DungeonBlueprint

        Returns:
            完整的 Dungeon 实体；若 blueprint.stages 为空则返回 None
        """
        if not blueprint.stages:
            logger.error(
                "[GenerateDungeonActionSystem][Step 4] blueprint.stages 为空，无法构建 Dungeon"
            )
            return None

        rooms: List[DungeonRoom] = []
        for i, stage_bp in enumerate(blueprint.stages, start=1):
            stage = create_stage(
                name=stage_bp.stage_name,
                stage_profile=StageProfile(
                    name=stage_bp.profile_name,
                    type=StageType.DUNGEON,
                    profile=stage_bp.profile,
                ),
                campaign_setting=RPG_CAMPAIGN_SETTING,
                system_rules=RPG_SYSTEM_RULES,
            )

            actor_bp = stage_bp.actor
            actor = create_actor(
                name=actor_bp.actor_name,
                character_sheet=CharacterSheet(
                    name=actor_bp.character_sheet_name,
                    type=ActorType.ENEMY.value,
                    profile=actor_bp.profile,
                    base_body=actor_bp.base_body,
                    appearance="",
                ),
                character_stats=CharacterStats(),
                campaign_setting=RPG_CAMPAIGN_SETTING,
                system_rules=RPG_SYSTEM_RULES,
            )
            # actor.skills = [BEAST_ATTACK_SKILL.model_copy()]

            stage.actors = [actor]
            rooms.append(DungeonRoom(stage=stage))
            logger.info(
                f"[GenerateDungeonActionSystem][Step 4] Room {i}/{len(blueprint.stages)} 构建完成:\n"
                f"  stage: {stage.name}\n"
                f"  actor: {actor.name}"
            )

        dungeon = Dungeon(
            name=blueprint.dungeon_name,
            ecology=blueprint.ecology,
            rooms=rooms,
        )
        logger.info(
            f"[GenerateDungeonActionSystem][Step 4] Dungeon 构建完成: {dungeon.name} "
            f"({len(dungeon.rooms)} rooms)"
        )
        return dungeon

    ####################################################################################################################################
