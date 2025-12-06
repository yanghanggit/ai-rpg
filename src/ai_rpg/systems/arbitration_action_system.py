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
等级:{param.combat_stats_component.stats.level}
卡牌:{param.card.name} → {target_display}
效果:{param.card.description}
属性:{param.combat_stats_component.stats_prompt}
状态效果(status_effects):
{param.combat_stats_component.status_effects_prompt}"""

        details_prompt.append(detail)

    return details_prompt


#######################################################################################################################################
def _generate_combat_arbitration_broadcast(combat_log: str, narrative: str) -> str:
    """生成战斗结算广播消息"""

    return f"""# 通知！战斗回合结算

## 战斗演出

{narrative}

## 数据日志

{combat_log}

**你的当前HP**: 请从上述日志中提取你的最终HP数值(格式: 角色.HP=X/Y)并记录。"""


#######################################################################################################################################
def _generate_combat_arbitration_prompt(
    combat_actions_details: List[CombatActionInfo],
    current_round_number: int,
) -> str:

    # 生成角色&卡牌详情
    details_prompt = _generate_actor_card_details(combat_actions_details)

    return f"""# 指令！这是第 {current_round_number} 回合，战斗回合仲裁

你是战斗仲裁者，需根据输入信息完成本回合战斗结算与演出。

## 行动顺序（从左至右依次执行）

{" → ".join([param.actor for param in combat_actions_details])}

## 参战信息

{"\n\n".join(details_prompt)}

## 仲裁任务

### 战斗规则

**战斗公式**

伤害（A→B）：
- 命中：物伤=max(1,⎡A.物攻×α-B.物防×β⎤)，魔伤=max(1,⎡A.魔攻×α-B.魔防×β⎤)
  → B.当前HP -= (物伤+魔伤+B.持续伤害) - B.持续治疗
  → 若B.当前HP≤0：有复活机制则恢复至Max_HP并说明原因，否则死亡
  → A.当前HP += ⎡(物伤+魔伤)×A.吸血×γ⎤
- 未命中：伤害=0

治疗（A→B）：
- 治疗量=⎡A.魔攻×α⎤ → B.当前HP=min(B.MAX_HP, B.当前HP+治疗量+B.持续治疗)

参数规则：
- 所有数值向上取整⎡⎤
- α/β/γ由剧情逻辑和角色状态效果决定
- 命中率依据剧情逻辑

**环境动态与互动**
- 场景是动态系统：角色行动→环境变化→影响后续战斗
- 卡牌执行可利用或影响环境物体，遵循世界观逻辑
- 环境物体使用限制：先出手角色优先

### 输出要求

```json
{{
  "combat_log": "角色使用卡牌 → 环境互动(含数值) → 伤害计算 → 卡牌代价 → 所有角色最终HP → 环境更新",
  "narrative": "将战斗过程故事化：角色行动→环境响应→影响结果→更新后的环境状态，禁用数字，使用感官描写，紧凑文本"
}}
```

**combat_log必填项：** 完整流程(卡牌→环境→计算→代价) → 最终HP(角色.HP=X/Y) → 所有效果明确数值&时长 → 精简紧凑文本 → 禁用换行/空行

**严格输出合规JSON**
"""


#######################################################################################################################################
def _generate_combat_arbitration_prompt2(
    combat_actions_details: List[CombatActionInfo],
    current_round_number: int,
) -> str:

    # 生成角色&卡牌详情
    details_prompt = _generate_actor_card_details(combat_actions_details)

    return f"""# 指令！这是第 {current_round_number} 回合，战斗回合仲裁

你是战斗仲裁者，需根据输入信息完成本回合战斗结算与演出。

## 行动顺序（从左至右依次执行）

{" → ".join([param.actor for param in combat_actions_details])}

## 参战信息

{"\n\n".join(details_prompt)}

## 仲裁任务

### 战斗规则

**战斗公式**

伤害（A→B）：
- 命中：物伤=max(1,⎡A.物攻×α-B.物防×β⎤)，魔伤=max(1,⎡A.魔攻×α-B.魔防×β⎤)
  → B.当前HP -= (物伤+魔伤+B.持续伤害) - B.持续治疗
  → 若B.当前HP≤0：有复活机制则恢复至Max_HP并说明原因，否则死亡
  → A.当前HP += ⎡(物伤+魔伤)×A.吸血×γ⎤
- 未命中：伤害=0

治疗（A→B）：
- 治疗量=⎡A.魔攻×α⎤ → B.当前HP=min(B.MAX_HP, B.当前HP+治疗量+B.持续治疗)

参数规则：
- 所有数值向上取整⎡⎤
- α/β/γ由剧情逻辑和角色状态效果决定
- 命中率依据剧情逻辑

**环境动态与互动**
- 场景是动态系统：角色行动→环境变化→影响后续战斗
- 卡牌执行可利用或影响环境物体，遵循世界观逻辑
- 环境物体使用限制：先出手角色优先

### 输出要求

```json
{{
  "combat_log": "角色使用卡牌 → 环境互动(含数值) → 伤害计算 → 卡牌代价 → 所有角色最终HP → 环境更新",
  "narrative": "将战斗过程故事化简短概括：角色行动→环境响应→影响结果→更新后的环境状态，禁用数字，使用感官描写，精简紧凑文本"
}}
```

**combat_log必填项：** 完整流程(卡牌→环境→计算→代价) → 最终HP(角色.HP=X/Y) → 所有效果明确数值&时长 → 精简紧凑文本 → 禁用换行/空行
**combat_log压缩优化：** 角色名简写(仅保留最后一段) → 删除所有动作描写 → 卡牌仅写所使用的卡牌名 → 环境互动仅写[物体名]+[效果] → 命中判定删除原因 → 计算公式直接写不加标签 → 状态仅使用[状态名+效果(轮数)] → 代价格式与状态统一 → 删除"→"外所有连接词和修饰词
**narrative压缩优化：** 每个角色行动减少细节描写 → 环境响应减少修饰词 → 结果仅写核心内容

**严格输出合规JSON**
"""


#######################################################################################################################################
@final
class ArbitrationActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: Final[TCGGame] = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(ArbitrationAction): GroupEvent.ADDED}

    ####################################################################################################################################
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
        message = _generate_combat_arbitration_prompt2(
            combat_actions_details, current_round_number
        )

        # 用场景推理。
        chat_client = ChatClient(
            name=stage_entity.name,
            prompt=message,
            context=self._game.get_agent_context(stage_entity).context,
            timeout=60,
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

            # 广播事件
            self._game.broadcast_to_stage(
                entity=stage_entity,
                agent_event=CombatArbitrationEvent(
                    message=_generate_combat_arbitration_broadcast(
                        format_response.combat_log, format_response.narrative
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
