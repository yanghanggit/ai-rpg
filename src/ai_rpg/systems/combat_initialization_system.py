"""战斗初始化系统

在战斗触发阶段为参战角色生成初始状态效果，转换战斗状态并启动第一回合。
"""

from dataclasses import dataclass
from typing import Final, List, final, override, Set
from loguru import logger
from pydantic import BaseModel
from ..entitas import ExecuteProcessor, Entity
from ..game.tcg_game import TCGGame
from ..models import (
    EnvironmentComponent,
    CombatStatsComponent,
    AllyComponent,
    EnemyComponent,
    AppearanceComponent,
    StatusEffect,
)
from ..chat_services.client import ChatClient
from ..utils import extract_json_from_code_block
from ..models.entities import CharacterStats


###################################################################################################################################################################
@dataclass
class OtherActorInfo:
    """其他参战角色的信息"""

    actor_name: str  # 当前角色名称
    other_name: str  # 其他角色名称
    appearance: str  # 其他角色的外观描述
    camp: str  # 阵营关系（友方/敌方）


class StatusEffectsInitializationResponse(BaseModel):
    """战斗初始化状态效果响应"""

    status_effects: List[StatusEffect] = []  # 新增的状态效果列表


###################################################################################################################################################################
def _format_other_actors_info(other_actors_info: List[OtherActorInfo]) -> str:
    """格式化其他角色信息为 Markdown 列表

    Args:
        other_actors_info: 其他角色信息列表

    Returns:
        格式化后的 Markdown 字符串
    """
    if not other_actors_info:
        return "无"

    lines = []
    for info in other_actors_info:
        lines.append(f"- **{info.other_name}**（{info.camp}）: {info.appearance}")

    return "\n".join(lines)


###################################################################################################################################################################
def _format_status_effects_notification(status_effects: List[StatusEffect]) -> str:
    """格式化状态效果通知消息

    Args:
        status_effects: 状态效果列表

    Returns:
        格式化的通知消息字符串
    """
    return "# 通知！战斗初始化新增状态效果\n\n" + "\n".join(
        [f"+ {effect.name}: {effect.description}" for effect in status_effects]
    )


###################################################################################################################################################################
def _generate_combat_init_prompt(
    stage_name: str,
    stage_description: str,
    other_actors_info: List[OtherActorInfo],
    actor_stats: CharacterStats,
    max_effects: int = 2,
) -> str:
    """生成战斗初始化状态效果提示词

    为角色生成战斗触发时的上下文信息，要求根据场景、敌我、自身状态
    自主判断并生成初始战斗状态效果。使用第一人称叙事风格。

    Args:
        stage_name: 战斗场景名称
        stage_description: 战斗场景的环境描述
        other_actors_info: 其他参战角色的信息列表（包含名称、外观、阵营）
        actor_stats: 当前角色的属性数据（包含 hp/max_hp/attack/defense）
        max_effects: 生成状态效果的最大数量，默认为2

    Returns:
        要求输出JSON格式状态效果列表的提示词
    """
    # 格式化角色属性
    attrs_prompt = f"HP:{actor_stats.hp}/{actor_stats.max_hp} | 攻击:{actor_stats.attack} | 防御:{actor_stats.defense}"

    return f"""# 指令！战斗触发！生成初始状态效果

## 场景叙事

{stage_name} ｜ {stage_description}

## 其余角色

{_format_other_actors_info(other_actors_info)}

## 你的属性

{attrs_prompt}

## 任务

根据场景、敌我、自身状况，判断你在战斗开始时应具有的状态效果（环境影响、心理状态、战术准备等）。

**状态效果要求**：
- name: 简洁的效果名称（<8字）
- description: 第一人称描述效果的具体表现和氛围感受，简短清晰（2-3句话）

**约束**: 最多生成 {max_effects} 个状态效果

**输出JSON**:

```json
{{
  "status_effects": [
    {{"name": "状态效果名", "description": "第一人称描述效果的具体表现"}}
  ]
}}
```

无新增状态时输出空数组，只输出JSON。"""


###################################################################################################################################################################
@final
class CombatInitializationSystem(ExecuteProcessor):
    """战斗初始化系统

    在战斗触发阶段为参战角色生成战斗上下文，并发调用LLM生成初始状态效果，
    转换战斗状态为进行中并启动第一回合。

    执行时机：
        战斗序列状态为 initializing 时执行，在战斗触发后、第一回合开始前。
    """

    def __init__(self, game_context: TCGGame) -> None:
        self._game: Final[TCGGame] = game_context

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:
        """执行战斗初始化

        为参战角色生成战斗上下文，并发调用LLM生成初始状态效果，转换战斗状态为进行中并启动第一回合。
        """
        # 分析阶段
        if not self._game.current_combat_sequence.is_initializing:
            # 非战斗触发阶段，直接返回
            return

        assert (
            len(self._game.current_combat_sequence.current_rounds) == 0
        ), "战斗触发阶段不允许有回合数！"

        # 获取玩家实体, player在的场景就是战斗发生的场景！
        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        # 获取当前场景实体
        current_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert current_stage_entity is not None

        # 获取场景环境组件
        environment_comp = current_stage_entity.get(EnvironmentComponent)
        assert environment_comp is not None

        # 参与战斗的角色实体列表
        actor_entities = self._game.get_alive_actors_on_stage(player_entity)
        assert len(actor_entities) > 0, "不可能出现没人参与战斗的情况！"

        # 第一步：为每个角色生成战斗初始化提示词并创建ChatClient
        chat_clients = self._generate_chat_clients_for_all_actors(
            actor_entities=actor_entities,
            stage_name=current_stage_entity.name,
            stage_description=environment_comp.description,
        )

        # 第二步：并发调用LLM生成所有角色的初始状态效果
        # logger.debug(f"开始并发生成 {len(chat_clients)} 个角色的初始状态效果...")
        await ChatClient.gather_request_post(clients=chat_clients)

        # 第三步：解析并更新每个角色的状态效果
        self._record_ai_responses(chat_clients)

        # 设置战斗为进行中
        self._game.current_combat_sequence.transition_to_ongoing()

        # 设置第一回合
        if not self._game.create_next_round():
            logger.error(f"not web_game.setup_round()")
            assert False, "无法启动战斗的第一回合！"

    ###################################################################################################################################################################
    def _generate_chat_clients_for_all_actors(
        self,
        actor_entities: Set[Entity],
        stage_name: str,
        stage_description: str,
    ) -> List[ChatClient]:
        """为所有参战角色生成战斗初始化提示词并创建ChatClient列表

        为每个角色生成包含场景信息、其他角色信息、自身属性和状态效果的完整战斗提示词，
        并将提示词添加到各角色的对话上下文中，同时创建用于生成初始状态效果的ChatClient。

        Args:
            actor_entities: 所有参战角色实体集合
            stage_name: 战斗场景名称
            stage_description: 战斗场景的环境描述

        Returns:
            ChatClient列表，用于并发请求LLM生成初始状态效果
        """
        chat_clients: List[ChatClient] = []

        for actor_entity in actor_entities:
            # 获取角色属性组件
            combat_stats_comp = actor_entity.get(CombatStatsComponent)
            assert combat_stats_comp is not None

            # 生成其他角色信息（包含外观和阵营）
            other_actors_info = self._generate_other_actors_info(
                actor_entity, actor_entities
            )

            # 生成提示词
            combat_init_prompt = _generate_combat_init_prompt(
                stage_name=stage_name,
                stage_description=stage_description,
                other_actors_info=other_actors_info,
                actor_stats=combat_stats_comp.stats,
                max_effects=2,
            )

            # 追加提示词到角色对话中
            self._game.add_human_message(
                actor_entity,
                combat_init_prompt,
                combat_initialization=stage_name,
            )

            # 创建ChatClient用于生成初始状态效果
            chat_clients.append(
                ChatClient(
                    name=actor_entity.name,
                    prompt=combat_init_prompt,
                    context=self._game.get_agent_context(actor_entity).context,
                )
            )

        return chat_clients

    ###################################################################################################################################################################
    def _record_ai_responses(self, chat_clients: List[ChatClient]) -> None:
        """解析AI响应并更新角色的初始状态效果

        解析LLM生成的状态效果JSON，追加到各角色的CombatStatsComponent.status_effects中。
        如果解析失败或找不到角色实体，记录日志并跳过。

        Args:
            chat_clients: 包含AI响应的ChatClient列表
        """
        for chat_client in chat_clients:
            actor_entity = self._game.get_entity_by_name(chat_client.name)
            if actor_entity is None:
                logger.warning(f"无法找到角色实体: {chat_client.name}")
                continue

            self._process_status_effects_response(actor_entity, chat_client)

    ###################################################################################################################################################################
    def _process_status_effects_response(
        self, entity: Entity, chat_client: ChatClient
    ) -> None:
        """处理单个角色的状态效果初始化响应

        Args:
            entity: 角色实体
            chat_client: 包含AI响应的ChatClient
        """
        combat_stats = entity.get(CombatStatsComponent)
        if combat_stats is None:
            logger.warning(f"角色 {entity.name} 缺少 CombatStatsComponent")
            return

        try:
            # 获取 LLM 响应
            ai_response = chat_client.response_content

            # AI 回应需要添加入上下文。
            self._game.add_ai_message(
                entity=entity,
                ai_messages=chat_client.response_ai_messages,
            )

            # 提取 JSON
            json_content = extract_json_from_code_block(ai_response)

            # 解析为 Pydantic 模型
            format_response = StatusEffectsInitializationResponse.model_validate_json(
                json_content
            )

            # 追加新状态效果到现有列表
            if format_response.status_effects:
                combat_stats.status_effects.extend(format_response.status_effects)

                # 通知角色新增的状态效果
                added_msg = _format_status_effects_notification(
                    format_response.status_effects
                )
                self._game.add_human_message(entity=entity, message_content=added_msg)

                # logger.debug(
                #     f"[{entity.name}] 战斗初始化新增 {len(format_response.status_effects)} 个状态效果: "
                #     f"{[e.name for e in format_response.status_effects]}"
                # )
            else:
                logger.debug(f"[{entity.name}] 战斗初始化无新增状态效果")

        except Exception as e:
            logger.error(f"[{entity.name}] 解析状态效果初始化失败: {e}")
            logger.error(f"原始响应: {chat_client.response_content}")

    ###################################################################################################################################################################
    def _determine_camp_relationship(
        self, actor_entity: Entity, other_entity: Entity
    ) -> str:
        """判断两个角色之间的阵营关系

        Args:
            actor_entity: 当前角色实体
            other_entity: 其他角色实体

        Returns:
            阵营关系字符串："友方" 或 "敌方"
        """
        actor_is_ally = actor_entity.has(AllyComponent)
        actor_is_enemy = actor_entity.has(EnemyComponent)
        other_is_ally = other_entity.has(AllyComponent)
        other_is_enemy = other_entity.has(EnemyComponent)

        # 同是友方或同是敌方
        if (actor_is_ally and other_is_ally) or (actor_is_enemy and other_is_enemy):
            return "友方"

        return "敌方"

    ###################################################################################################################################################################
    def _generate_other_actors_info(
        self, actor_entity: Entity, actor_entities: Set[Entity]
    ) -> List[OtherActorInfo]:
        """为指定角色生成其他所有参战角色的信息列表

        Args:
            actor_entity: 当前角色实体
            actor_entities: 所有参战角色实体集合

        Returns:
            其他角色的信息列表，包含名称、外观和阵营关系
        """
        # copy生成其他参战角色的列表，但是移除自己
        copy_entities = actor_entities.copy()
        copy_entities.remove(actor_entity)

        # 生成返回数据列表！
        other_actors_info_list: List[OtherActorInfo] = []

        # 生成数据列表
        for other_entity in copy_entities:

            appearance_comp = other_entity.get(AppearanceComponent)
            assert appearance_comp is not None, "每个参战角色都必须有外观组件！"

            other_actor_info = OtherActorInfo(
                actor_name=actor_entity.name,
                other_name=other_entity.name,
                appearance=appearance_comp.appearance,
                camp=self._determine_camp_relationship(actor_entity, other_entity),
            )

            other_actors_info_list.append(other_actor_info)

        return other_actors_info_list


###################################################################################################################################################################
