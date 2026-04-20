from typing import Any, Dict, Final, List, Optional, final
from ..models.messages import AIMessage
from loguru import logger
from overrides import override
from pydantic import BaseModel, field_validator
from ..deepseek import DeepSeekClient
from ..entitas import Entity, Matcher, GroupEvent, ReactiveProcessor
from ..models import (
    AnnounceAction,
    StageDescriptionComponent,
    QueryAction,
    SpeakAction,
    WhisperAction,
    PlanAction,
    TransStageAction,
    InspectSelfAction,
    EquipItemAction,
    HomeComponent,
    MindEvent,
    ActorComponent,
    AllyComponent,
    PlayerComponent,
    PlayerOnlyStageComponent,
)
from ..utils import extract_json_from_code_block
from ..game import TCGGame

# 玩家「主动行动」对应的 Action 组件类型集合。
# 当任一玩家持有其中任意类型时，视为本轮「有主动行动」，NPC 将进入待命模式。
# 新增/删除行动类型时只在此处修改，其余判断逻辑均引用此常量。
_PLAYER_ACTIVE_ACTION_TYPES: Final = (
    SpeakAction,
    WhisperAction,
    AnnounceAction,
    TransStageAction,
    EquipItemAction,
)


#######################################################################################################################################
def _format_mind_notification(actor_name: str, mind_content: str) -> str:
    """格式化内心活动通知消息。

    Args:
        actor_name: 角色名称
        mind_content: 内心活动内容

    Returns:
        格式化后的通知消息
    """
    return f"# {actor_name} 内心活动: {mind_content}"


#######################################################################################################################################
@final
class ActionPlanResponse(BaseModel):
    """角色行动规划响应数据模型。

    用于解析和验证 AI 返回的角色行动决策 JSON 数据，
    确保响应结构符合预期格式并包含所有必要的行动信息。

    Attributes:
        mind: 内心独白
        query: 数据库检索关键词
        inspect_self: 查阅自身背包与属性（true 时触发 InspectSelfActionSystem）
        equip_weapon: 装备武器槽的物品全名（None 不更换；"" 脱掉）
        equip_armor: 装备套装槽的物品全名（None 不更换；"" 脱掉）
        equip_accessory: 装备饰品槽的物品全名（None 不更换；"" 脱掉）
        speak: 说话行动（目标角色名 -> 内容）
        whisper: 耳语行动（目标角色名 -> 内容）
        announce: 公开宣布
        trans_stage: 移动目标场景名
    """

    mind: str = ""
    query: str = ""
    inspect_self: bool = False
    equip_weapon: Optional[str] = None
    equip_armor: Optional[str] = None
    equip_accessory: Optional[str] = None
    speak: Dict[str, str] = {}
    whisper: Dict[str, str] = {}
    announce: str = ""
    trans_stage: str = ""

    @field_validator("speak", "whisper", mode="before")
    @classmethod
    def _coerce_dict_none(cls, v: Any) -> Any:
        return v if v is not None else {}

    @field_validator("announce", "trans_stage", mode="before")
    @classmethod
    def _coerce_str_none(cls, v: Any) -> Any:
        return v if v is not None else ""


#######################################################################################################################################
def _build_action_planning_prompt(
    current_stage: str,
    current_stage_narration: str,
    other_actors_appearances: Dict[str, str],
    available_home_stages: List[str],
    planning_turn_index: int,
) -> str:
    """构建角色行动规划提示词（完整版，含所有行动类型）。

    包含：query、inspect_self、speak、whisper、announce、equip_weapon/equip_armor/equip_accessory、trans_stage。

    Args:
        current_stage: 场景名称
        current_stage_narration: 场景环境描述
        other_actors_appearances: 其他角色的外观（角色名 -> 外观）
        available_home_stages: 可前往的场景列表
        planning_turn_index: 全局家园规划回合编号

    Returns:
        完整的行动规划提示词
    """
    # 场景内角色外观描述
    other_actors_appearance_info = []
    for actor_name, appearance in other_actors_appearances.items():
        other_actors_appearance_info.append(f"{actor_name}: {appearance}")
    if len(other_actors_appearance_info) == 0:
        other_actors_appearance_info.append("无")

    return f"""# 决定你要做什么，以JSON格式输出。

## 当前回合: {planning_turn_index}

## 你所在场景信息

{current_stage} | {current_stage_narration}

可移动至: {", ".join(available_home_stages) if len(available_home_stages) > 0 else "无"}

## 本场景内其他角色

{"\n".join(other_actors_appearance_info)}

## 核心规则

1. **每回合行动结构**

```
每回合结构：
├─ mind [必填] - 内心独白/思考
├─ 向内查询 [可叠加，互不干扰]
│   ├─ query        - 检索外部知识库（可选）
│   └─ inspect_self - 查阅自身背包与属性（可选）
└─ 主要行动 [每轮至多选一类，与向内查询互斥]
   ├─ A. 对外交流（三选一）
   │   ├─ speak
   │   ├─ whisper
   │   └─ announce
   ├─ B. 装备操作（三槽可同轮并用）
   │   └─ equip_weapon / equip_armor / equip_accessory
   └─ C. trans_stage - 移动场景
```

> `query` / `inspect_self` 可同时使用，来源不同互不干扰。
> 向内查询与主要行动**不能同轮并用**：若本轮执行主要行动（A/B/C 任意一类），则不填 query / inspect_self。

2. **第一人称视角**  
   所有行动和思考必须以第一人称进行。

3. **知识库检索** (`query`)
   - System prompt 是信息目录，需要详细信息时用 query 向外部数据库检索，结果会添加到下一轮 context

4. **自我审视** (`inspect_self`)
   - 设为 `true` 时，系统将把你的背包物品与当前战斗属性注入到下一轮 context
   - 适合在不确定自身装备或状态时使用；不需要填写任何额外参数
   - 可与 `query` 同时使用

5. **对外交流** (`speak` / `whisper` / `announce`) - 三种方式的区别
   - `speak`：对当前场景内指定角色说话（公开，场景内所有人都能听到）
   - `whisper`：对指定角色耳语（私密，只有你和对方知道）
   - `announce`：向所有家园场景发布公告（广播，所有家园场景的角色都能听到）

   **约束**：三种方式每轮只选其一；只能使用 context 中已有的信息；本轮使用对外交流时，query / inspect_self 留空。

6. **装备操作** (`equip_weapon` / `equip_armor` / `equip_accessory`)
   - 三个装备槽**可在同一轮并用**，不操作的槽位填 `null`
   - 填入背包物品精确全名 → 装备该槽；填写 `""` → 脱掉该槽；填 `null` → 不更换
   - **装备分两轮完成**：第一轮用 `inspect_self` 查阅背包确认物品全名，第二轮再执行 `equip_*`；不可在同一轮同时使用 `inspect_self` 和 `equip_*`
   - 本轮使用装备操作时，query / inspect_self 留空

7. **场景移动** (`trans_stage`)
   - 填写目标场景全名（从"可移动至"列表选择）

8. **严格禁止虚构**：`mind`/`speak`/`whisper` 均只能基于 context 中已有的信息。禁止在任何字段中捏造其他角色的动作、反应或对话，禁止虚构 context 中未记录的事件。`mind` 只写你自己的思考，不得描述他人行为。

## 输出格式(JSON)

```json
{{
  "mind": "内心独白",
  "query": "检索关键词",
  "inspect_self": false,
  "equip_weapon": null,
  "equip_armor": null,
  "equip_accessory": null,
  "speak": {{
    "角色全名": "说话内容"
  }},
  "whisper": {{
    "角色全名": "耳语内容"
  }},
  "announce": "公开宣布内容",
  "trans_stage": "移动目标场景全名"
}}
```

**约束规则**：

- 严格按上述JSON格式输出你的行动决策
- 所有字段名不可更改
- `speak` / `whisper` 不使用时填 `{{}}`（空对象），`announce` / `trans_stage` 不使用时填 `""`（空字符串）；**这四个字段禁止填 `null`**"""


#######################################################################################################################################
@final
class HomeActorPlanSystem(ReactiveProcessor):
    """家园角色行动系统。

    响应式处理器，监听 PlanAction 组件触发，生成行动规划提示词，
    调用 AI 服务获取决策，并转化为游戏行动组件。

    Attributes:
        _game: 游戏实例引用
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PlanAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlanAction) and entity.has(ActorComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        planning_turn = self._game.increment_planning_turn()

        player_entities = [e for e in entities if e.has(PlayerComponent)]
        npc_entities = [e for e in entities if not e.has(PlayerComponent)]

        # 玩家：注入场景观察上下文，不调用 LLM
        for player_entity in player_entities:
            self._inject_player_scene_context(player_entity, planning_turn)

        # 若玩家本轮有主动行动，NPC 进入待命模式（跳过 LLM 推理）
        if self._is_player_active(player_entities):
            for npc_entity in npc_entities:
                self._inject_npc_standby_context(npc_entity, planning_turn)
            return

        # NPC：调用 LLM 进行行动规划
        chat_clients: List[DeepSeekClient] = self._create_actor_chat_clients(
            npc_entities, planning_turn
        )
        await DeepSeekClient.batch_chat(clients=chat_clients)

        for chat_client in chat_clients:
            response_entity = self._game.get_entity_by_name(chat_client.name)
            assert (
                response_entity is not None
            ), f"Cannot find entity by name: {chat_client.name}"
            self._execute_actor_actions(response_entity, chat_client)

    #######################################################################################################################################
    def _is_player_active(self, player_entities: List[Entity]) -> bool:
        """判断本轮是否有玩家具有主动行动。

        Args:
            player_entities: 玩家实体列表

        Returns:
            若任一玩家持有 _PLAYER_ACTIVE_ACTION_TYPES 中任意类型则返回 True
        """
        return any(
            e.has(action_type)
            for e in player_entities
            for action_type in _PLAYER_ACTIVE_ACTION_TYPES
        )

    #######################################################################################################################################
    def _inject_npc_standby_context(
        self, npc_entity: Entity, planning_turn_index: int
    ) -> None:
        """向 NPC 实体注入待命状态（跳过 LLM 推理）。

        玩家本轮有主动行动时，NPC 不进行推理，直接注入 passive_mind 并保持对话历史连贯。

        Args:
            npc_entity: NPC 实体
            planning_turn_index: 全局家园规划回合编号
        """
        current_stage = self._game.resolve_stage_entity(npc_entity)
        assert current_stage is not None

        other_actors_appearances = self._get_other_actors_appearances(
            npc_entity, current_stage
        )
        available_home_stages = self._get_available_home_stages(
            npc_entity, current_stage
        )

        prompt = _build_action_planning_prompt(
            current_stage=current_stage.name,
            current_stage_narration=current_stage.get(
                StageDescriptionComponent
            ).narrative,
            other_actors_appearances=other_actors_appearances,
            available_home_stages=[e.name for e in available_home_stages],
            planning_turn_index=planning_turn_index,
        )

        self._game.add_human_message(
            npc_entity,
            prompt,
            home_actor_planning=npc_entity.name,
        )

        passive_mind = f"身处{current_stage.name}，待命。"
        standby_response = ActionPlanResponse(mind=passive_mind)
        self._game.add_ai_message(
            npc_entity,
            AIMessage(content=standby_response.model_dump_json(indent=2)),
        )

        self._game.notify_entities(
            {npc_entity},
            MindEvent(
                message=_format_mind_notification(npc_entity.name, passive_mind),
                actor=npc_entity.name,
                content=passive_mind,
            ),
        )

    #######################################################################################################################################
    def _inject_player_scene_context(
        self, player_entity: Entity, planning_turn_index: int
    ) -> None:
        """向玩家实体注入当前场景观察信息（不调用 LLM）。

        Args:
            player_entity: 玩家实体
            planning_turn_index: 全局家园规划回合编号
        """
        current_stage = self._game.resolve_stage_entity(player_entity)
        assert current_stage is not None

        other_actors_appearances = self._get_other_actors_appearances(
            player_entity, current_stage
        )
        available_home_stages = self._get_available_home_stages(
            player_entity, current_stage
        )

        prompt = _build_action_planning_prompt(
            current_stage=current_stage.name,
            current_stage_narration=current_stage.get(
                StageDescriptionComponent
            ).narrative,
            other_actors_appearances=other_actors_appearances,
            available_home_stages=[e.name for e in available_home_stages],
            planning_turn_index=planning_turn_index,
        )

        self._game.add_human_message(
            player_entity,
            prompt,
            home_actor_planning=player_entity.name,
        )

        # 判断玩家本轮是否有主动动作
        has_action = any(
            player_entity.has(action_type)
            for action_type in _PLAYER_ACTIVE_ACTION_TYPES
        )
        passive_mind = "" if has_action else f"身处{current_stage.name}，待命。"

        mock_response = self._build_player_action_response(player_entity, passive_mind)
        self._game.add_ai_message(
            player_entity, AIMessage(content=mock_response.model_dump_json(indent=2))
        )

        # 被动观察轮：模拟 mind 通知，与 NPC 路径对齐
        if mock_response.mind != "":
            self._game.notify_entities(
                {player_entity},
                MindEvent(
                    message=_format_mind_notification(
                        player_entity.name, mock_response.mind
                    ),
                    actor=player_entity.name,
                    content=mock_response.mind,
                ),
            )

    #######################################################################################################################################
    def _build_player_action_response(
        self, player_entity: Entity, passive_mind: str = ""
    ) -> ActionPlanResponse:
        """根据玩家当前动作组件构建等效的 ActionPlanResponse。

        有主动动作时 mind 为空；无任何动作（被动观察轮）时用 passive_mind 填入。

        Args:
            player_entity: 玩家实体
            passive_mind: 被动观察轮时使用的 mind 文本

        Returns:
            模拟的 ActionPlanResponse
        """
        response = ActionPlanResponse()

        if player_entity.has(SpeakAction):
            response.speak = player_entity.get(SpeakAction).target_messages

        if player_entity.has(WhisperAction):
            response.whisper = player_entity.get(WhisperAction).target_messages

        if player_entity.has(AnnounceAction):
            response.announce = player_entity.get(AnnounceAction).message

        if player_entity.has(TransStageAction):
            response.trans_stage = player_entity.get(TransStageAction).target_stage_name

        if player_entity.has(EquipItemAction):
            equip_action = player_entity.get(EquipItemAction)
            response.equip_weapon = equip_action.weapon
            response.equip_armor = equip_action.armor
            response.equip_accessory = equip_action.accessory

        if not any(
            [
                response.speak,
                response.whisper,
                response.announce,
                response.trans_stage,
            ]
        ) and not any(
            x is not None
            for x in [
                response.equip_weapon,
                response.equip_armor,
                response.equip_accessory,
            ]
        ):
            response.mind = passive_mind

        return response

    #######################################################################################################################################
    def _execute_actor_actions(
        self, actor_entity: Entity, chat_client: DeepSeekClient
    ) -> None:
        """执行角色的行动决策。

        解析 AI 响应并转化为游戏行动组件，保存对话历史。

        Args:
            actor_entity: 角色实体
            chat_client: 聊天客户端（包含 AI 响应）
        """
        try:

            # 验证响应
            validated_response = ActionPlanResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 添加上下文！
            self._game.add_human_message(
                actor_entity,
                chat_client.prompt,
                home_actor_planning=actor_entity.name,
            )
            assert chat_client.response_ai_message is not None
            self._game.add_ai_message(actor_entity, chat_client.response_ai_message)

            # 添加内心独白: 上下文！，这里做直接添加与通知处理
            if validated_response.mind != "":

                self._game.notify_entities(
                    set({actor_entity}),
                    MindEvent(
                        message=_format_mind_notification(
                            actor_entity.name, validated_response.mind
                        ),
                        actor=actor_entity.name,
                        content=validated_response.mind,
                    ),
                )

            # 添加说话动作
            if len(validated_response.speak) > 0:
                actor_entity.replace(
                    SpeakAction, actor_entity.name, validated_response.speak
                )

            # 添加耳语动作
            if len(validated_response.whisper) > 0:
                actor_entity.replace(
                    WhisperAction, actor_entity.name, validated_response.whisper
                )

            # 添加宣布动作
            if validated_response.announce != "":
                actor_entity.replace(
                    AnnounceAction,
                    actor_entity.name,
                    validated_response.announce,
                )

            # 添加查询动作
            if validated_response.query != "":
                actor_entity.replace(
                    QueryAction, actor_entity.name, validated_response.query
                )

            # 添加自我审视动作
            if validated_response.inspect_self:
                actor_entity.replace(InspectSelfAction, actor_entity.name)

            # 添加装备物品动作（任一槽位不为 None 即触发）
            if any(
                x is not None
                for x in [
                    validated_response.equip_weapon,
                    validated_response.equip_armor,
                    validated_response.equip_accessory,
                ]
            ):
                actor_entity.replace(
                    EquipItemAction,
                    actor_entity.name,
                    validated_response.equip_weapon,
                    validated_response.equip_armor,
                    validated_response.equip_accessory,
                )

            # 最后：如果需要可以添加传送场景。
            if validated_response.trans_stage != "":
                actor_entity.replace(
                    TransStageAction,
                    actor_entity.name,
                    validated_response.trans_stage,
                )

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _get_other_actors_appearances(
        self, actor_entity: Entity, current_stage: Entity
    ) -> Dict[str, str]:
        """获取当前场景内除自身以外的所有角色外观描述。

        Args:
            actor_entity: 当前角色实体（将被排除）
            current_stage: 当前所在场景实体

        Returns:
            其他角色的外观描述（角色名 -> 外观）
        """
        appearances = self._game.get_actor_appearances_in_stage(current_stage)
        appearances.pop(actor_entity.name, None)
        return appearances

    #######################################################################################################################################
    def _get_available_home_stages(
        self, actor_entity: Entity, current_stage: Entity
    ) -> set[Entity]:
        """获取角色可前往的家园场景集合。

        玩家可前往所有家园场景；非玩家只能前往不含 PlayerOnlyStageComponent 的场景。
        均排除当前所在场景。

        Args:
            actor_entity: 角色实体
            current_stage: 当前所在场景实体

        Returns:
            可前往的家园场景实体集合
        """
        home_stage_entities = self._game.get_group(
            Matcher(all_of=[HomeComponent])
        ).entities.copy()
        home_stage_entities.discard(current_stage)

        if actor_entity.has(PlayerComponent):
            return home_stage_entities

        return {
            stage
            for stage in home_stage_entities
            if not stage.has(PlayerOnlyStageComponent)
        }

    #######################################################################################################################################
    def _create_actor_chat_clients(
        self, actor_entities: List[Entity], planning_turn_index: int
    ) -> List[DeepSeekClient]:
        """为角色创建聊天客户端。

        收集场景上下文并生成提示词，创建聊天客户端。

        Args:
            actor_entities: 角色实体列表
            planning_turn_index: 全局家园规划回合编号

        Returns:
            聊天客户端列表
        """
        chat_clients: List[DeepSeekClient] = []

        for actor_entity in actor_entities:

            # 找到当前场景
            current_stage = self._game.resolve_stage_entity(actor_entity)
            assert current_stage is not None

            # 找到当前场景内所有角色 & 他们的外观描述（不含自己）
            other_actors_appearances = self._get_other_actors_appearances(
                actor_entity, current_stage
            )

            # 找到当前场景可去往的家园场景
            available_home_stages = self._get_available_home_stages(
                actor_entity, current_stage
            )

            # 生成请求处理器
            chat_clients.append(
                DeepSeekClient(
                    name=actor_entity.name,
                    prompt=_build_action_planning_prompt(
                        current_stage=current_stage.name,
                        current_stage_narration=current_stage.get(
                            StageDescriptionComponent
                        ).narrative,
                        other_actors_appearances=other_actors_appearances,
                        available_home_stages=[e.name for e in available_home_stages],
                        planning_turn_index=planning_turn_index,
                    ),
                    context=self._game.get_agent_context(actor_entity).context,
                )
            )

            # 测试用：向非玩家盟友注入一组连续的 mock 消息，模拟强制发起特定行动的场景。
            self._mock_inject_ally_equip_test(actor_entity)

        return chat_clients

    #######################################################################################################################################
    def _mock_inject_ally_equip_test(self, actor_entity: Entity) -> None:
        """【测试用】向非玩家盟友注入一组连续的 mock 消息，模拟强制发起特定行动的场景。

        流程：
          1. 禁止本轮使用 trans_stage 移动场景
          2. 本轮必须使用 inspect_self 查看背包与装备状态
          3. 下一轮使用 equip_accessory: "" 脱掉饰品槽

        只对非玩家盟友（AllyComponent & ~PlayerComponent）生效。

        Args:
            actor_entity: 待注入的角色实体
        """
        if not actor_entity.has(AllyComponent) or actor_entity.has(PlayerComponent):
            return

        logger.debug(
            "这里清醒mock一个message 添加给学者的上下文，要求在后续的计划行动中不可以使用trans_stage 来移动场景！"
        )
        self._game.add_human_message(
            actor_entity,
            "这是一个测试消息，要求你在后续的计划行动中不可以使用trans_stage 来移动场景！",
        )
        logger.debug(
            "这里清醒mock一个message 添加给学者的上下文，要求本轮使用 inspect_self 查看自身背包与装备状态！"
        )
        self._game.add_human_message(
            actor_entity,
            "这是一个测试消息，要求你在本轮计划行动中必须使用 inspect_self 查看自身背包与装备状态！",
        )
        logger.debug(
            '这里清醒mock一个message 添加给学者的上下文，要求在下一轮使用 equip_accessory: "" 脱掉饰品槽！'
        )
        self._game.add_human_message(
            actor_entity,
            '这是一个测试消息，要求你在查看完自身状态后的下一轮，使用 equip_accessory: "" 脱掉饰品槽！',
        )

    #######################################################################################################################################
