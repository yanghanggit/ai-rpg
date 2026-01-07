"""
战斗仲裁系统 - 优化版本

核心优化:
1. _generate_combat_arbitration_prompt: 生成战斗仲裁指令(Token优化~60%)
   - 紧凑型卡牌详情(7行 vs 原15行)
   - 压缩战斗公式(150字符 vs 原450字符)
   - 抽象环境互动规则(3行 vs 原25行)
   - 精简输出要求(内嵌JSON示例)

2. 广播消息优化(Token优化~30%)
   - 标题: "通知！战斗回合结算"
   - 段落: "战斗演出" + "数据日志"
   - 提示语精简为单句
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
    """生成每个角色的卡牌和状态详情"""
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
    """生成战斗结算广播消息"""

    return f"""# 通知！第 {current_round_number} 回合结算

## 战斗演出

{narrative}

## 数据日志

{combat_log}

**你的当前HP**: 在 **数据日志** 中定位你的角色名，提取最终HP数值(格式:角色.HP=X/Y)"""


#######################################################################################################################################
def _generate_combat_arbitration_prompt3(
    combat_actions_details: List[CombatActionInfo],
    current_round_number: int,
) -> str:

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
  "combat_log": "依次记录：角色→卡牌→环境互动→伤害→HP变化→环境更新",
  "narrative": "故事化描述战斗过程（感官描写，禁用数字）"
}}
```

**约束**
- combat_log：角色简写、关键词化、删冗余、明确数值、格式(角色.HP=X/Y)
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
        """收集所有参战角色的战斗行动信息。

        从每个角色实体中提取出牌动作、目标、卡牌和战斗属性，封装为 CombatActionInfo 列表。
        用于后续生成战斗仲裁提示词。
        """
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
        """向 AI 发起战斗仲裁请求并处理结果。

        流程：收集角色战斗信息 → 生成仲裁提示词 → 调用 ChatClient 请求 AI 仲裁 → 应用仲裁结果。
        使用场景实体的上下文进行推理，确保仲裁符合当前场景的叙事逻辑。
        """
        # 生成推理参数。
        combat_actions_details = self._collect_combat_action_info(actor_entities)
        assert len(combat_actions_details) > 0

        # 获取当前回合数
        current_round_number = len(self._game.current_combat_sequence.current_rounds)

        # 生成推理信息。
        message = _generate_combat_arbitration_prompt3(
            combat_actions_details, current_round_number
        )

        # 用场景推理（使用推理模型）。
        # assert ChatClient._deepseek_url_config is not None, "DeepSeek URL 配置未设置！"
        chat_client = ChatClient(
            name=stage_entity.name,
            prompt=message,
            context=self._game.get_agent_context(stage_entity).context,
            # url=ChatClient._deepseek_url_config.reasoner_url,
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
        """解析并应用 AI 仲裁结果到游戏状态。

        从 ChatClient 响应中提取 combat_log 和 narrative，更新场景实体的 ArbitrationAction，
        向所有参战角色广播战斗结果，并记录到当前战斗回合数据中。
        """
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
