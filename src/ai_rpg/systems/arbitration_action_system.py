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

    return f"""# 提示！回合行动指令。根据下列信息执行战斗回合：

## 角色行动序列（后续卡牌在前序执行后生效）

{" -> ".join([param.actor for param in prompt_params])}

## 角色&卡牌详情

{"\n\n".join(details_prompt)}

## 战斗结算规则

伤害流程（A→B）
1. 命中判定 → 未命中：伤害=0
2. 命中时：
   物理伤害 = max(1, ⎡A.物理攻击×α - B.物理防御×β)
   魔法伤害 = max(1, ⎡A.魔法攻击×α - B.魔法防御×β⎤)
   → B.HP -= (物理伤害 + 魔法伤害 + B.持续伤害) - B.持续治疗
   → 若 B.HP <= 0 :
       → 若有，更新B.HP至Max_HP（说明HP更新的原因）
       → 若无，则死亡标记
   → A.HP += ⎡A.吸血量(物理伤害 + 魔法伤害) x γ⎤

治疗流程（A→B）
1. 必中生效：
   治疗量 = ⎡A.魔法攻击×α⎤ （α∈剧情合理值）
   → B.HP = min(B.MAX_HP, B.HP + 治疗量) + B.持续治疗

【核心机制】
1. 所有数值最终向上取整（⎡x⎤表示）。
2. 动态参数：
   - 命中率 ∈ 剧情逻辑。
   - α/β/γ ∈ 情境调整系数，并参考A与B的‘增益/减益‘等状态。
3. 边界控制：
   - 伤害保底≥1。
   - 治疗量不突破MAX_HP最大值。
【环境互动规则】
1. 卡牌必须与环境互动，符合物理和化学常识。
2. 环境物体由场景描述提供，如：干草、断剑、盔甲碎片、火焰、石块、箭矢等。
3. 卡牌必须至少与一个环境物体产生互动，方式包括但不限于：
   - 物理反应：击碎、砸落、掷出、推撞。
   - 化学反应：引燃、引爆、导电、腐蚀。
4. 环境互动需体现：
   - 合理的触发条件
   - 额外效果（如额外伤害、状态改变）
   - 持续效果（如燃烧、塌方、导电链条）
5. 状态效果：
   - 需明确说明 环境互动产生的 buff / debuff 的具体数值和持续时间。
   - 环境产生的状态效果可以持续多回合，并在敌人/我方行动时触发。
6. 同一回合内，同一环境物体只能被先出手角色使用。
【合理性要求】
1. 必须符合物理/化学常识（例如：火焰遇到干草会蔓延，金属导电，石块砸落会扬起灰尘）。
2. 必须符合角色职业特点。
3. 战斗结果需逻辑自洽，环境变化能被追踪。
【卡牌使用代价】
1. 每张卡牌生成时都有一个限制角色自身的状态效果作为使用代价
3. 只要角色尝试使用该卡牌，这个状态效果就会生效，就算卡牌没有命中目标也会生效
2. 该效果必须在计算过程中体现出来

## 输出内容

1. 计算过程：
    - 根据'战斗结算规则'输出详细的计算过程(伤害与治疗的计算过程)。
    - 根据'卡牌与环境反应规则'，描述每张卡牌与环境的互动过程和效果，其中效果描述必须要附上具体细节和数值。
    - 具体格式为：卡牌描述 + 卡牌效果 → 环境互动 + 互动效果 → 数值结算 + 生命值。
    - 环境状态结算
    - 更新环境对象的可用状态。
    - 根据'卡牌使用代价'更新角色的状态
    - **【必须】结算后，必须明确列出每个角色的最终生命值状态，格式为：角色名.当前HP/最大HP。即使HP未变化也必须列出。**
    - 如果角色HP有变化，说明变化原因；如果HP未变化(如仅使用护盾/增益卡牌)，明确说明"HP保持不变"。
2. 演出过程（~200字）
    - 文学化描写，禁用数字与计算过程

## 输出格式规范

```json
{{"combat_log":"计算过程","narrative":"演出过程"}}
```

- 禁用换行/空行
- 直接输出合规JSON"""


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
