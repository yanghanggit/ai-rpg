from typing import Final, List, NamedTuple, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_services.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    ArbitrationAction,
    DungeonComponent,
    PlayCardsAction,
    CombatStatsComponent,
    Card,
    StageComponent,
    AgentEvent,
    DeathComponent,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class ArbitrationResponse(BaseModel):
    combat_log: str
    narrative: str


#######################################################################################################################################
@final
class PromptParameters(NamedTuple):
    actor: str
    target: str
    card: Card
    combat_stats_component: CombatStatsComponent


#######################################################################################################################################
def _generate_actor_card_details(prompt_params: List[PromptParameters]) -> List[str]:
    """生成每个角色的卡牌和状态详情"""
    details_prompt: List[str] = []
    for param in prompt_params:
        assert param.card.name != ""

        detail = f"""【{param.actor}】
卡牌:{param.card.name} → {param.target}
效果:{param.card.description}
属性:{param.combat_stats_component.stats_prompt}
状态效果(status_effects):
{param.combat_stats_component.status_effects_prompt}"""

        details_prompt.append(detail)

    return details_prompt


#######################################################################################################################################
def _generate_prompt(prompt_params: List[PromptParameters]) -> str:

    # 生成角色&卡牌详情
    details_prompt = _generate_actor_card_details(prompt_params)

    return f"""# 指令！战斗回合仲裁

你是战斗仲裁者，需根据输入信息完成本回合战斗结算与演出。

## 行动顺序（从左至右依次执行）

{" → ".join([param.actor for param in prompt_params])}

## 参战信息

{"\n\n".join(details_prompt)}

## 仲裁任务

### 战斗规则

**战斗公式**

伤害（A→B）：
- 命中：物伤=max(1,⎡A.物攻×α-B.物防×β⎤)，魔伤=max(1,⎡A.魔攻×α-B.魔防×β⎤)
  → B.HP -= (物伤+魔伤+B.持续伤害) - B.持续治疗
  → 若B.HP≤0：有复活机制则恢复至Max_HP并说明原因，否则死亡
  → A.HP += ⎡(物伤+魔伤)×A.吸血×γ⎤
- 未命中：伤害=0

治疗（A→B）：
- 治疗量=⎡A.魔攻×α⎤ → B.HP=min(B.MAX_HP, B.HP+治疗量+B.持续治疗)

参数规则：
- 所有数值向上取整⎡⎤
- α/β/γ由剧情逻辑和角色状态效果决定
- 命中率依据剧情逻辑

**环境互动**
1. 卡牌必须与环境互动，符合物理和化学常识
2. 环境物体由场景描述提供（如：干草、断剑、盔甲碎片、火焰、石块、箭矢等）
3. 互动方式：
   - 物理反应：击碎、砸落、掷出、推撞
   - 化学反应：引燃、引爆、导电、腐蚀
4. 效果要求：
   - 合理的触发条件
   - 额外效果（如额外伤害、状态改变）
   - 持续效果（如燃烧、塌方、导电链条）
5. 状态效果：
   - 必须明确说明环境互动产生的 buff/debuff 的具体数值和持续时间
   - 环境产生的状态效果可持续多回合，在角色行动时触发
6. 同一回合内，同一环境物体只能被先出手角色使用
**约束条件**
1. 必须符合物理/化学常识（例如：火焰遇到干草会蔓延，金属导电，石块砸落会扬起灰尘）
2. 必须符合角色职业特点
3. 战斗结果需逻辑自洽，环境变化能被追踪
4. 卡牌代价规则：
   - 每张卡牌有限制角色自身的状态效果作为使用代价
   - 只要角色尝试使用该卡牌，代价效果就会生效（即使未命中目标）
   - 该效果必须在计算过程中体现

### 输出要求

按以下JSON格式输出战斗结算与演出：

```json
{{
  "combat_log": "角色使用卡牌 → 环境互动(含数值) → 伤害计算 → 卡牌代价 → 所有角色最终HP → 环境更新",
  "narrative": "文学化描写(~200字)，禁用数字"
}}
```

**combat_log必填项：** 完整流程(卡牌→环境→计算→代价) → 最终HP(角色.HP=X/Y) → 环境互动数值&持续 → 环境状态变化 → 尽量精简 → 禁用换行/空行"""


#######################################################################################################################################
@final
class ArbitrationActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

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

        # if len(entities) == 0:
        #     return

        assert (
            self._game.current_combat_sequence.is_ongoing
        ), "当前没有进行中的战斗序列！"
        assert len(entities) == 1, "当前只能有一个场景实体进行仲裁处理！"

        # 排序角色！
        stage_entity = entities[0]
        assert stage_entity.has(StageComponent) and stage_entity.has(
            DungeonComponent
        ), "场景实体缺少StageComponent或DungeonComponent！"

        play_cards_actors = self._game.get_group(
            Matcher(
                all_of=[
                    PlayCardsAction,
                ],
            )
        ).entities

        if len(play_cards_actors) == 0:
            return

        sort_actors: List[Entity] = []
        for (
            action_order
        ) in self._game.current_combat_sequence.latest_round.action_order:
            for entity in play_cards_actors:
                assert not entity.has(DeathComponent)
                if entity.name == action_order:
                    sort_actors.append(entity)
                    break

        for sort_actor in sort_actors:
            logger.info(f"sort_actor: {sort_actor.name}")

        await self._process_request(stage_entity, sort_actors)

    #######################################################################################################################################
    def _generate_action_prompt_parameters(
        self, react_entities: List[Entity]
    ) -> List[PromptParameters]:

        ret: List[PromptParameters] = []
        for entity in react_entities:

            assert entity.has(ActorComponent)
            assert entity.has(CombatStatsComponent)
            assert entity.has(PlayCardsAction)

            play_cards_action = entity.get(PlayCardsAction)
            assert play_cards_action.card.name != ""

            ret.append(
                PromptParameters(
                    actor=entity.name,
                    target=play_cards_action.target,
                    card=play_cards_action.card,
                    combat_stats_component=entity.get(CombatStatsComponent),
                )
            )

        return ret

    #######################################################################################################################################
    async def _process_request(
        self, stage_entity: Entity, actor_entities: List[Entity]
    ) -> None:

        # 生成推理参数。
        params = self._generate_action_prompt_parameters(actor_entities)
        assert len(params) > 0

        # 生成推理信息。
        message = _generate_prompt(params)

        # 用场景推理。
        request_handler = ChatClient(
            name=stage_entity.name,
            prompt=message,
            context=self._game.get_agent_context(stage_entity).context,
        )

        # 用语言服务系统进行推理。
        request_handler.request_post()

        # 处理返回结果。
        self._handle_response(stage_entity, request_handler, actor_entities)

    #######################################################################################################################################
    def _handle_response(
        self,
        stage_entity: Entity,
        request_handler: ChatClient,
        actor_entities: List[Entity],
    ) -> None:

        try:

            format_response = ArbitrationResponse.model_validate_json(
                extract_json_from_code_block(request_handler.response_content)
            )

            # 推理的场景记录下！
            arbitration_action = stage_entity.get(ArbitrationAction)
            stage_entity.replace(
                ArbitrationAction,
                arbitration_action.name,
                format_response.combat_log,
                format_response.narrative,
            )

            message_content = f"""# 发生事件！战斗回合:
## 演出过程
{format_response.narrative}

## 计算过程
{format_response.combat_log}

请注意**计算过程**中的关于**你**的当前生命值/最大生命值的描述，后续你会依据此进行状态更新。
"""

            # 广播事件
            last_round = self._game.current_combat_sequence.latest_round
            self._game.broadcast_to_stage(
                entity=stage_entity,
                agent_event=AgentEvent(
                    message=message_content,
                ),
            )
            # 记录
            last_round.combat_log = format_response.combat_log
            last_round.narrative = format_response.narrative

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
