"""副本入口初始化系统（角色侧）：为入口场景内的队伍成员注入场景环境信息，并为队伍成员触发牌库初始化（怪物牌库在各自战斗房间初始化）。"""

from dataclasses import dataclass
from typing import Final, List, Set, final, override

from loguru import logger

from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.dbg_combat_processor import (
    compute_character_stats,
    get_alive_actors_in_stage,
)
from ..game.dbg_game import DBGGame
from ..models import (
    AppearanceComponent,
    CharacterStats,
    DeckComponent,
    InitializeDeckAction,
    MonsterComponent,
    PartyMemberComponent,
    StageDescriptionComponent,
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
def _build_entry_init_prompt(
    stage_name: str,
    stage_description: str,
    other_actors_info: List[OtherActorInfo],
    actor_stats: CharacterStats,
) -> str:
    """生成副本入口场景感知通知"""
    attrs_prompt = f"HP:{actor_stats.hp}/{actor_stats.max_hp} | 攻击:{actor_stats.attack} | 防御:{actor_stats.defense}"

    return f"""# 副本入口场景感知通知

## 场景叙事

{stage_name} ｜ {stage_description}

## 其余角色

{_build_other_actors_info(other_actors_info)}

## 你的属性

{attrs_prompt}"""


###################################################################################################################################################################
@final
class EntryInitActorSystem(ExecuteProcessor):
    """副本入口初始化系统（角色侧）：为入口场景内的队伍成员注入场景环境信息（无 LLM），并触发牌库初始化。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:

        if not self._game.is_current_room_dungeon_entry:
            logger.debug("当前副本房间非入口房间，跳过入口初始化（角色侧）")
            return

        entry_room = self._game.current_dungeon_entry_room
        if entry_room.initialized:
            logger.debug("当前入口房间已完成初始化，跳过入口初始化（角色侧）")
            return

        logger.info(
            "入口初始化（角色侧）开始：注入入口场景环境信息 + 为队伍成员触发牌库初始化..."
        )

        # 获取玩家实体，player 所在场景即入口场景
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "无法找到玩家实体！"

        # 获取当前场景实体
        current_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert current_stage_entity is not None, "无法找到当前场景实体！"
        assert current_stage_entity.has(
            StageDescriptionComponent
        ), "当前场景实体缺少 StageDescriptionComponent 组件！"

        # 获取场景环境组件
        stage_description_comp = current_stage_entity.get(StageDescriptionComponent)

        # 入口场景内仅有队伍成员（怪物分散在各战斗房间，不在此处注入场景环境信息）
        actor_entities = get_alive_actors_in_stage(self._game, player_entity)
        assert len(actor_entities) > 0, "入口场景内不可能没有队伍成员！"

        # 为每个角色注入入口场景环境信息（无 LLM 调用）
        self._inject_entry_scene_environment(
            actor_entities=actor_entities,
            stage_name=current_stage_entity.name,
            stage_description=stage_description_comp.narrative,
        )

        # 为队伍成员触发牌库初始化（精确控制触发对象）
        self._add_initialize_deck_actions()

        # 状态守护：标记入口房间已完成初始化，避免重复触发
        entry_room.initialized = True

    ###################################################################################################################################################################
    def _inject_entry_scene_environment(
        self,
        actor_entities: Set[Entity],
        stage_name: str,
        stage_description: str,
    ) -> None:
        """为所有入口场景内的角色注入场景环境信息（human message + 模拟 AI 回应），无 LLM 调用。"""

        for actor_entity in actor_entities:

            # 幂等保护：同一场景内只注入一次，避免入口初始化任务被重复触发时重复写入场景环境信息
            existing_messages = self._game.filter_messages(
                entity=actor_entity,
                predicate=lambda msg, index, messages: (
                    getattr(msg, "entry_initialization", None) == stage_name
                ),
            )
            if existing_messages:
                logger.debug(
                    f"[{actor_entity.name}] 已注入过 {stage_name} 的入口场景环境信息，跳过"
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

            # 生成入口场景环境提示词
            entry_init_prompt = _build_entry_init_prompt(
                stage_name=stage_name,
                stage_description=stage_description,
                other_actors_info=other_actors_info,
                actor_stats=actor_stats,
            )

            # 注入入口场景环境信息
            self._game.add_human_message(
                entity=actor_entity,
                human_message=HumanMessage(
                    content=entry_init_prompt,
                    entry_initialization=stage_name,
                ),
            )

            # 注入模拟 AI 回应，维护 Human↔AI 交替结构
            self._game.add_ai_message(
                entity=actor_entity,
                ai_message=AIMessage(content="已感知当前场景环境。"),
            )

            logger.debug(
                f"[{actor_entity.name}] 入口场景环境信息注入完成（无 LLM 推理）"
            )

    ###################################################################################################################################################################
    def _add_initialize_deck_actions(self) -> None:
        """为所有队伍成员添加牌库初始化动作（精确控制触发对象）。"""
        count = 0

        party_entities = self._game.get_group(
            Matcher(all_of=[PartyMemberComponent])
        ).entities.copy()
        for entity in party_entities:
            assert entity.has(
                PartyMemberComponent
            ), f"角色 {entity.name} 缺少 PartyMemberComponent，不应被入口初始化选中！"

            assert entity.has(
                DeckComponent
            ), f"队伍成员 {entity.name} 缺少 DeckComponent！"

            entity.replace(InitializeDeckAction, entity.name)
            logger.debug(f"[{entity.name}] 已触发牌库初始化（队伍）")
            count += 1

        logger.info(
            f"[EntryInitActorSystem] 完成，已为 {count} 个队伍成员触发牌库初始化"
        )
