from typing import Final, List, NamedTuple, final

from loguru import logger
from overrides import override
from pydantic import BaseModel

from ..chat_services.chat_request_handler import ChatRequestHandler
from ..entitas import Entity, GroupEvent, Matcher
from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    ActorComponent,
    DirectorAction,
    DungeonComponent,
    FeedbackAction,
    PlayCardsAction,
    RPGCharacterProfileComponent,
    Skill,
    StageComponent,
    TurnAction,
)
from ..utils import json_format

COMBAT_MECHANICS_DESCRIPTION: Final[
    str
] = f"""伤害流程（A→B）
1. 命中判定 → 未命中：伤害=0
2. 命中时：
   物理伤害 = max(1, ⎡A.物理攻击×α - B.物理防御×β)
   魔法伤害 = max(1, ⎡A.魔法攻击×α - B.魔法防御×β⎤)
   → B.HP -= (物理伤害 + 魔法伤害 + B.持续伤害) - B.持续治疗
   → 若 B.HP <= 0 : 死亡标记
   → A.HP += ⎡A.吸血量(物理伤害 + 魔法伤害) x γ⎤

治疗流程（A→B）
1. 必中生效：
   治疗量 = ⎡A.魔法攻击×α⎤ （α∈剧情合理值）
   → B.HP = min(B.MAX_HP, B.HP + 治疗量) + B.持续治疗

核心机制
1. 所有数值最终向上取整（⎡x⎤表示）。
2. 动态参数：
   - 命中率 ∈ 剧情逻辑。
   - α/β/γ ∈ 情境调整系数，并参考A与B的‘增益/减益‘等状态。
3. 边界控制：
   - 伤害保底≥1。
   - 治疗量不突破MAX_HP。
4. 对于环境互动，环境利用类的技能，如果一个环境物体在一回合内被使用，则该物体在该回合内不可被其他角色重复利用，并且该物体在这次战斗中从环境中消失，角色无法再和该物体互动。如果其他角色试图使用该物体，则会取消使用这个技能，并使用另一个技能。"""


#######################################################################################################################################
@final
class DirectorResponse(BaseModel):
    calculation: str
    performance: str


#######################################################################################################################################
@final
class ActionPromptParameters(NamedTuple):
    actor: str
    targets: List[str]
    skill: Skill
    rpg_character_profile_component: RPGCharacterProfileComponent
    dialogue: str


#######################################################################################################################################
def _generate_prompt(prompt_params: List[ActionPromptParameters]) -> str:

    details_prompt: List[str] = []
    for param in prompt_params:

        assert param.skill.name != ""

        detail = f"""### {param.actor}
技能: {param.skill.name}
目标: {param.targets}
描述: {param.skill.description}
技能效果: {param.skill.effect}
角色演出时说的话: {param.dialogue}
属性:
{param.rpg_character_profile_component.attrs_prompt}
角色状态:
{param.rpg_character_profile_component.status_effects_prompt}"""

        details_prompt.append(detail)

    # 模版
    director_response_sample = DirectorResponse(
        calculation="计算过程", performance="演出过程"
    )

    return f"""# 提示！回合行动指令。根据下列信息执行战斗回合：
## 角色行动序列（后续技能在前序执行后生效）
{" -> ".join([param.actor for param in prompt_params])}
## 角色&技能详情
{"\n".join(details_prompt)}
## 战斗结算规则
{COMBAT_MECHANICS_DESCRIPTION}
## 输出内容
1. 计算过程：
    - 根据‘战斗结算规则’输出详细的计算过程(伤害与治疗的计算过程)。
    - 结算后，需明确每个角色的当前生命值/最大生命值。
2. 演出过程（~200字）
    - 文学化描写，禁用数字与计算过程
## 输出格式规范
{director_response_sample.model_dump_json()}
- 禁用换行/空行
- 直接输出合规JSON"""


#######################################################################################################################################
@final
class DirectorActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(DirectorAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(DirectorAction) and entity.has(StageComponent)

    #######################################################################################################################################
    @override
    async def a_execute2(self) -> None:

        if len(self._react_entities_copy) == 0:
            return

        assert self._game.current_engagement.is_on_going_phase
        assert len(self._react_entities_copy) == 1

        # 排序角色！
        stage_entity = self._react_entities_copy[0]
        assert stage_entity.has(StageComponent)
        assert stage_entity.has(DungeonComponent)

        turn_then_play_cards_actors = self._game.get_group(
            Matcher(
                all_of=[
                    TurnAction,
                    PlayCardsAction,
                ],
            )
        ).entities

        if len(turn_then_play_cards_actors) == 0:
            return

        sort_actors = sorted(
            turn_then_play_cards_actors, key=lambda entity: entity.get(TurnAction).turn
        )

        await self._process_request(stage_entity, sort_actors)

    #######################################################################################################################################
    def _generate_action_prompt_parameters(
        self, react_entities: List[Entity]
    ) -> List[ActionPromptParameters]:

        ret: List[ActionPromptParameters] = []
        for entity in react_entities:

            assert entity.has(ActorComponent)
            assert entity.has(RPGCharacterProfileComponent)
            assert entity.has(PlayCardsAction)

            play_cards_action = entity.get(PlayCardsAction)
            assert play_cards_action.skill.name != ""

            ret.append(
                ActionPromptParameters(
                    actor=entity._name,
                    targets=play_cards_action.targets,
                    skill=play_cards_action.skill,
                    rpg_character_profile_component=entity.get(
                        RPGCharacterProfileComponent
                    ),
                    dialogue=play_cards_action.dialogue,
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
        request_handler = ChatRequestHandler(
            agent_name=stage_entity._name,
            prompt=message,
            chat_history=self._game.get_agent_short_term_memory(
                stage_entity
            ).chat_history,
        )

        # 用语言服务系统进行推理。
        self._game.chat_system.handle([request_handler])

        # 处理返回结果。
        if request_handler.last_message_content == "":
            return

        # 处理返回结果。
        self._handle_response(stage_entity, request_handler, actor_entities)

    #######################################################################################################################################
    def _handle_response(
        self,
        stage_entity: Entity,
        request_handler: ChatRequestHandler,
        actor_entities: List[Entity],
    ) -> None:

        try:

            format_response = DirectorResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.last_message_content)
            )

            # 推理的场景记录下！
            stage_director_action = stage_entity.get(DirectorAction)
            stage_entity.replace(
                DirectorAction,
                stage_director_action.name,
                format_response.calculation,
                format_response.performance,
            )

            # 通知角色！！！！
            for actor_entity in actor_entities:

                actor_entity.replace(
                    FeedbackAction,
                    actor_entity._name,
                    format_response.calculation,
                    format_response.performance,
                    "",
                    0,
                    0,
                    [],
                )

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
