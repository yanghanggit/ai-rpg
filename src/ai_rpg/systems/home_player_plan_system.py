"""家园玩家规划注入系统。"""

import json
import uuid
from typing import Any, Dict, Final, List, Tuple, final

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game import DBGGame
from ..models import (
    ActorComponent,
    AnnounceAction,
    NPCComponent,
    PlanAction,
    PlayerComponent,
    SpeakAction,
    TransStageAction,
    WhisperAction,
)
from ..models.messages import AIMessage, HumanMessage, ToolMessage
from .home_planning import (
    build_action_planning_tool_prompt,
    build_planning_context,
)


#######################################################################################################################################
@final
class HomePlayerPlanSystem(ReactiveProcessor):
    """家园玩家规划注入系统。让 Player Agent 以为自己走了工具调用规划，从而与 NPC 的记忆格式一致。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PlanAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PlanAction)
            and entity.has(PlayerComponent)
            and entity.has(ActorComponent)
            and entity.has(NPCComponent)
            and (
                entity.has(SpeakAction)
                or entity.has(WhisperAction)
                or entity.has(AnnounceAction)
                or entity.has(TransStageAction)
            )
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert (
            len(entities) == 1
        ), "HomePlayerPlanSystem expects exactly one player entity at a time."
        self._inject_player_mimic_messages(entities[0])

    #######################################################################################################################################
    def _inject_player_mimic_messages(self, player_entity: Entity) -> None:
        """伪造一条与 NPC 等价的 submit_action_plan 工具调用轨迹写入玩家记忆。"""

        ctx = build_planning_context(self._game, player_entity)
        prompt = build_action_planning_tool_prompt(ctx)

        action_type, target_messages, message, target_stage_name = (
            self._extract_action_from_components(player_entity)
        )

        submit_args: Dict[str, Any] = {"mind": "", "action_type": action_type}
        if action_type in ("speak", "whisper"):
            submit_args["target_messages"] = target_messages
        elif action_type == "announce":
            submit_args["message"] = message
        elif action_type == "trans_stage":
            submit_args["target_stage_name"] = target_stage_name

        call_id = f"call_shadow_{uuid.uuid4().hex}"
        ai_message = AIMessage(
            content="",
            additional_kwargs={
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": "submit_action_plan",
                            "arguments": json.dumps(submit_args, ensure_ascii=False),
                        },
                    }
                ]
            },
        )
        tool_message = ToolMessage(content="行动计划已提交", tool_call_id=call_id)

        # 直接追加：tool call 的 AIMessage content 为空，不能走 add_ai_message 的断言
        memory = self._game.get_agent_memory(player_entity)
        memory.messages.append(HumanMessage(content=prompt))
        memory.messages.append(ai_message)
        memory.messages.append(tool_message)

    #######################################################################################################################################
    def _extract_action_from_components(
        self, player_entity: Entity
    ) -> Tuple[str, Dict[str, str], str, str]:
        """从玩家当前挂载的主动行动组件反推 submit_action_plan 参数。"""

        if player_entity.has(SpeakAction):
            return "speak", player_entity.get(SpeakAction).target_messages, "", ""
        if player_entity.has(WhisperAction):
            return "whisper", player_entity.get(WhisperAction).target_messages, "", ""
        if player_entity.has(AnnounceAction):
            return "announce", {}, player_entity.get(AnnounceAction).message, ""
        if player_entity.has(TransStageAction):
            return (
                "trans_stage",
                {},
                "",
                player_entity.get(TransStageAction).target_stage_name,
            )

        # filter 已保证至少存在一个主动行动组件，此处兜底
        logger.warning(
            f"HomePlayerPlanSystem: 玩家 {player_entity.name} 挂载 PlanAction 但无任何主动行动组件"
        )
        return "none", {}, "", ""


#######################################################################################################################################
