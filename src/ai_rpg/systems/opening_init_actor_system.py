"""副本开场初始化系统（角色侧）：为开场场景内的队伍成员注入场景环境信息（无 LLM，按消息标记幂等）。"""

from dataclasses import dataclass
from typing import Final, List, Set, final, override

from loguru import logger

from ..entitas import Entity, ExecuteProcessor
from ..game.dbg_combat_processor import (
    compute_character_stats,
    get_alive_actors_in_stage,
)
from ..game.dbg_game import DBGGame
from ..game.rpg_stage_environment import get_stage_environment
from ..models import (
    AppearanceComponent,
    CharacterStats,
    MonsterComponent,
    PartyMemberComponent,
)
from ..models.messages import AIMessage, HumanMessage
from ..utils import prompt_builder


###################################################################################################################################################################
@dataclass
class OtherActorInfo:
    """其他在场角色的信息"""

    other_name: str  # 其他角色名称
    appearance: str  # 其他角色的外观描述
    camp: str  # 阵营关系（友方/敌方）


###################################################################################################################################################################
@prompt_builder
def _build_other_actors_info(other_actors_info: List[OtherActorInfo]) -> str:
    """格式化其他角色信息为 Markdown 列表"""
    if not other_actors_info:
        return "无"

    lines = []
    for info in other_actors_info:
        lines.append(f"- **{info.other_name}**（{info.camp}）: {info.appearance}")

    return "\n\n".join(lines)


###################################################################################################################################################################
@prompt_builder
def _build_opening_init_prompt(
    stage_name: str,
    environment: str,
    other_actors_info: List[OtherActorInfo],
    actor_stats: CharacterStats,
) -> str:
    """生成副本开场场景感知通知"""
    attrs_prompt = (
        f"HP:{actor_stats.hp}/{actor_stats.max_hp} | 速度:{actor_stats.speed}"
    )

    return f"""# 副本开场场景感知通知

## 场景叙事

{stage_name} ｜ {environment}

## 其余角色

{_build_other_actors_info(other_actors_info)}

## 你的属性

{attrs_prompt}"""


###################################################################################################################################################################
@final
class OpeningInitActorSystem(ExecuteProcessor):
    """副本开场初始化系统（角色侧）：为开场场景内的队伍成员注入场景环境信息（无 LLM），注入按消息标记幂等。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:

        if not self._game.is_current_room_dungeon_opening:
            logger.debug("当前副本房间非开场房间，跳过开场初始化（角色侧）")
            return

        logger.info("开场初始化（角色侧）开始：注入开场场景环境信息...")

        # 获取玩家实体，player 所在场景即开场场景
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "无法找到玩家实体！"

        # 获取当前场景实体
        current_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert current_stage_entity is not None, "无法找到当前场景实体！"

        # 读取场景环境叙事（缺失时降级为占位文案，不阻断开场初始化）
        environment = get_stage_environment(current_stage_entity)

        # 开场场景内仅有队伍成员（怪物分散在各战斗房间，不在此处注入场景环境信息）
        actor_entities = get_alive_actors_in_stage(self._game, player_entity)
        assert len(actor_entities) > 0, "开场场景内不可能没有队伍成员！"

        # 为每个角色注入开场场景环境信息（无 LLM 调用）
        self._inject_opening_scene_environment(
            actor_entities=actor_entities,
            stage_name=current_stage_entity.name,
            environment=environment,
        )

    ###################################################################################################################################################################
    def _inject_opening_scene_environment(
        self,
        actor_entities: Set[Entity],
        stage_name: str,
        environment: str,
    ) -> None:
        """为所有开场场景内的角色注入场景环境信息（human message + 模拟 AI 回应），无 LLM 调用。"""

        for actor_entity in actor_entities:

            # 幂等保护：同一场景内只注入一次，避免开场初始化任务被重复触发时重复写入场景环境信息
            existing_messages = self._game.filter_messages(
                entity=actor_entity,
                predicate=lambda msg, index, messages: (
                    getattr(msg, "opening_initialization", None) == stage_name
                ),
            )
            if existing_messages:
                logger.debug(
                    f"[{actor_entity.name}] 已注入过 {stage_name} 的开场场景环境信息，跳过"
                )
                continue

            # 生成其他角色信息（包含外观和阵营）
            copy_entities = actor_entities.copy()
            copy_entities.remove(actor_entity)

            # 生成其他角色信息列表
            other_actors_info: List[OtherActorInfo] = []
            for other_entity in copy_entities:

                appearance_comp = other_entity.get(AppearanceComponent)
                assert appearance_comp is not None, "每个在场角色都必须有外观组件！"

                # 阵营判定：同是友方或同是敌方视为友方，否则为敌方
                actor_is_ally = actor_entity.has(PartyMemberComponent)
                actor_is_enemy = actor_entity.has(MonsterComponent)
                other_is_ally = other_entity.has(PartyMemberComponent)
                other_is_enemy = other_entity.has(MonsterComponent)
                camp = (
                    "友方"
                    if (actor_is_ally and other_is_ally)
                    or (actor_is_enemy and other_is_enemy)
                    else "敌方"
                )

                # 生成其他角色信息
                other_actors_info.append(
                    OtherActorInfo(
                        other_name=other_entity.name,
                        appearance=appearance_comp.appearance,
                        camp=camp,
                    )
                )

            # 计算角色有效属性（含装备加成）
            actor_stats = compute_character_stats(actor_entity)

            # 生成开场场景环境提示词
            opening_init_prompt = _build_opening_init_prompt(
                stage_name=stage_name,
                environment=environment,
                other_actors_info=other_actors_info,
                actor_stats=actor_stats,
            )

            # 注入开场场景环境信息
            self._game.add_human_message(
                entity=actor_entity,
                human_message=HumanMessage(
                    content=opening_init_prompt,
                    opening_initialization=stage_name,
                ),
            )

            # 注入模拟 AI 回应，维护 Human↔AI 交替结构
            self._game.add_ai_message(
                entity=actor_entity,
                ai_message=AIMessage(content="已感知当前场景环境。"),
            )

            logger.debug(
                f"[{actor_entity.name}] 开场场景环境信息注入完成（无 LLM 推理）"
            )
