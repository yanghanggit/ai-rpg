"""战斗仲裁系统

AI驱动的战斗结算系统，生成优化的仲裁提示词并处理AI返回的战斗结果。

核心优化:
- Token压缩60%：紧凑格式 + 精简规则 + 内嵌示例
- 完整流程：卡牌 → 环境 → 效果 → 代价 → HP → 环境
- 支持复活：多段HP变化(X→0→Y)自动识别
- 扩展性强：支持1v1到3v3及更多角色
"""

from typing import Final, List, NamedTuple, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_services.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    ArbitrationAction,
    DungeonComponent,
    PlayCardsAction,
    CombatStatsComponent,
    Card,
    StageComponent,
    DeathComponent,
    CombatArbitrationEvent,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################


#######################################################################################################################################
@final
class ArbitrationResponse(BaseModel):
    combat_log: str
    narrative: str


#######################################################################################################################################
@final
class CombatActionInfo(NamedTuple):
    actor: str
    targets: List[str]
    card: Card
    combat_stats_component: CombatStatsComponent


#######################################################################################################################################
def _generate_actor_card_details(
    combat_actions_details: List[CombatActionInfo],
) -> List[str]:
    """生成角色卡牌详情：卡牌描述 + 属性 + 状态效果"""
    details_prompt: List[str] = []
    for param in combat_actions_details:
        assert param.card.name != ""

        # 格式化目标显示
        if len(param.targets) == 0:
            target_display = "无目标"
            logger.warning(f"{param.actor} 的出牌动作没有目标！")
        elif len(param.targets) == 1:
            target_display = param.targets[0]
        else:
            target_display = f"[{', '.join(param.targets)}]"

        detail = f"""【{param.actor}】
卡牌: {param.card.name} → {target_display} — {param.card.description}
角色属性: {param.combat_stats_component.stats_prompt}
角色当前状态效果(status_effects):
{param.combat_stats_component.status_effects_prompt}"""

        details_prompt.append(detail)

    return details_prompt


#######################################################################################################################################
def _generate_combat_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int
) -> str:
    """生成战斗广播：演出描述 + 数据日志 + HP提示"""

    return f"""# 通知！第 {current_round_number} 回合结算

## 战斗演出

{narrative}

## 数据日志

{combat_log}

**你的当前HP**: 在 **数据日志** 中定位你的角色名，提取最终HP数值(格式:角色.HP=X/Y)"""


#######################################################################################################################################
def _generate_combat_arbitration_prompt(
    combat_actions_details: List[CombatActionInfo],
    current_round_number: int,
) -> str:
    """生成战斗仲裁提示词：行动顺序 + 角色信息 + 输出格式(含复活示例)"""
    # 生成角色&卡牌详情
    details_prompt = _generate_actor_card_details(combat_actions_details)

    return f"""# 指令！第 {current_round_number} 回合：完成战斗结算与演出，以JSON格式返回。

## 行动顺序

{" → ".join([param.actor for param in combat_actions_details])}

先手角色行动优先生效，可改变环境与战场状态，影响后续角色的行动结果。

## 参战信息

{"\n\n".join(details_prompt)}

## 战斗计算

严格按照 System 提示词的 **## 战斗机制** 进行计算

## 仲裁规则

- 角色可利用或改变环境物体（先到先得）
- 环境变化影响后续角色行动
- 状态效果(status_effects)实时计入战斗计算

## 输出格式

```json
{{
  "combat_log": "[角色A|卡牌A→环境A→角色X:伤10 代价:防-2] [角色B|卡牌B→环境B→角色Y:伤50 代价:攻-3] [角色C|卡牌C→角色Z:伤8] HP:角色A=45/50 角色B=30→25/40 角色C=50/50 角色X=40→30/50 角色Y=35→0→50/50 角色Z=42→34/50 [环境]效果1+效果2",
  "narrative": "故事化描述战斗过程（感官描写，禁用数字）"
}}
```

**约束**
- combat_log：格式 `[角色简名|卡牌→环境→目标:效果 代价:X]` 依次记录每个角色的完整行动流程，`HP:角色=X→Y/Z` 集中记录所有角色最终HP（支持多段变化X→Y→Z），`[环境]关键词` 最后记录环境变化。角色名仅保留最后一段
- narrative：感官描写、禁数字、精简核心
- 严格按上述JSON格式输出"""


###########################################################################################################################################
@final
class ArbitrationActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: Final[TCGGame] = game_context

    #######################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(ArbitrationAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(ArbitrationAction) and entity.has(StageComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        assert (
            self._game.current_combat_sequence.is_ongoing
        ), "当前没有进行中的战斗序列！"
        assert len(entities) == 1, "当前只能有一个场景实体进行仲裁处理！"

        # 排序角色！
        stage_entity = entities[0]
        assert stage_entity.has(StageComponent) and stage_entity.has(
            DungeonComponent
        ), "场景实体缺少StageComponent或DungeonComponent！"

        # 获取所有出牌动作的角色实体
        play_cards_actors = self._game.get_group(
            Matcher(
                all_of=[
                    PlayCardsAction,
                ],
            )
        ).entities

        assert len(play_cards_actors) > 0, "没有检测到任何出牌动作的角色！"
        if len(play_cards_actors) == 0:
            logger.warning("没有检测到任何出牌动作的角色！")
            return

        # 依据当前回合的行动顺序排序角色实体
        sort_actors: List[Entity] = []
        for (
            action_order
        ) in self._game.current_combat_sequence.latest_round.action_order:
            for entity in play_cards_actors:
                assert not entity.has(DeathComponent)
                if entity.name == action_order:
                    sort_actors.append(entity)
                    break

        # 日志输出排序结果
        for sort_actor in sort_actors:
            logger.info(f"sort_actor: {sort_actor.name}")

        # 发起仲裁请求
        await self._request_combat_arbitration(stage_entity, sort_actors)

        # 移除出牌动作组件
        self._game.clear_hands()

    #######################################################################################################################################
    def _collect_combat_action_info(
        self, react_entities: List[Entity]
    ) -> List[CombatActionInfo]:
        """收集参战角色的行动信息：卡牌 + 目标 + 战斗属性"""
        ret: List[CombatActionInfo] = []
        for entity in react_entities:

            play_cards_action = entity.get(PlayCardsAction)
            assert play_cards_action.card.name != "", "出牌动作缺少卡牌信息！"

            ret.append(
                CombatActionInfo(
                    actor=entity.name,
                    targets=play_cards_action.targets,
                    card=play_cards_action.card,
                    combat_stats_component=entity.get(CombatStatsComponent),
                )
            )

        return ret

    #######################################################################################################################################
    async def _request_combat_arbitration(
        self, stage_entity: Entity, actor_entities: List[Entity]
    ) -> None:
        """发起AI战斗仲裁：生成提示词 → 调用ChatClient → 应用结果"""
        # 生成推理参数。
        combat_actions_details = self._collect_combat_action_info(actor_entities)
        assert len(combat_actions_details) > 0

        # 获取当前回合数
        current_round_number = len(self._game.current_combat_sequence.current_rounds)

        # 生成推理信息。
        message = _generate_combat_arbitration_prompt(
            combat_actions_details, current_round_number
        )

        # 用场景推理
        chat_client = ChatClient(
            name=stage_entity.name,
            prompt=message,
            context=self._game.get_agent_context(stage_entity).context,
            timeout=60 * 2,  # 战斗推理允许更长时间
        )

        # 用语言服务系统进行推理。
        chat_client.request_post()

        # 处理返回结果。
        self._apply_arbitration_result(
            stage_entity, chat_client, actor_entities, combat_actions_details
        )

    #######################################################################################################################################
    def _apply_arbitration_result(
        self,
        stage_entity: Entity,
        chat_client: ChatClient,
        actor_entities: List[Entity],
        combat_actions_details: List[CombatActionInfo],
    ) -> None:
        """应用AI仲裁结果：解析JSON → 更新场景 → 广播消息 → 记录数据"""
        try:

            format_response = ArbitrationResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 添加上下文
            self._game.add_human_message(
                entity=stage_entity,
                message_content=chat_client.prompt,
            )

            # 添加AI回复
            self._game.add_ai_message(
                entity=stage_entity,
                ai_messages=chat_client.response_ai_messages,
            )

            # 推理的场景记录下！
            arbitration_action = stage_entity.get(ArbitrationAction)
            stage_entity.replace(
                ArbitrationAction,
                arbitration_action.name,
                format_response.combat_log,
                format_response.narrative,
            )

            # 获取当前回合数
            current_round_number = len(
                self._game.current_combat_sequence.current_rounds
            )

            # 广播事件
            self._game.broadcast_to_stage(
                entity=stage_entity,
                agent_event=CombatArbitrationEvent(
                    message=_generate_combat_arbitration_broadcast(
                        format_response.combat_log,
                        format_response.narrative,
                        current_round_number,
                    ),
                    stage=stage_entity.name,
                    combat_log=format_response.combat_log,
                    narrative=format_response.narrative,
                ),
                exclude_entities={stage_entity},
            )

            # 记录数据！
            latest_round = self._game.current_combat_sequence.latest_round
            latest_round.combat_log = format_response.combat_log
            latest_round.narrative = format_response.narrative

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
