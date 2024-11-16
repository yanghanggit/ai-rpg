from typing import Any, FrozenSet, NamedTuple, List, final


class ActionComponent(NamedTuple):
    name: str
    values: List[str]


# 场景环境的描述
@final
class StageNarrateAction(ActionComponent):
    pass


# 输出场景中所有显著的道具和物件的标记，以便进一步处理或引用。这样，每次场景更新时，系统不仅生成详细的场景描述，还会同步输出这些场景内的道具和物件标记，使得场景内容的处理更加完善和细致。
@final
class StageTagAction(ActionComponent):
    pass


# 内心独白
@final
class MindVoiceAction(ActionComponent):
    pass


# 场景内广播 AnnounceAction
@final
class AnnounceAction(ActionComponent):
    pass


# 私下交流
@final
class WhisperAction(ActionComponent):
    pass


# 对谁说（场景内其他角色能听到）
@final
class SpeakAction(ActionComponent):
    pass


# 标签
@final
class TagAction(ActionComponent):
    pass


# 死亡
@final
class DeadAction(ActionComponent):
    pass


# 离开当前场景并去往
@final
class GoToAction(ActionComponent):
    pass


# 从目标角色处偷取
@final
class StealPropAction(ActionComponent):
    pass


# 将道具交给目标角色
@final
class GivePropAction(ActionComponent):
    pass


# # 行为动作与技能动作
@final
class SkillAction(ActionComponent):
    pass


# 更新外观
@final
class UpdateAppearanceAction(ActionComponent):
    pass


# 处理伤害逻辑
@final
class DamageAction(ActionComponent):
    pass


# 装备道具
@final
class EquipPropAction(ActionComponent):
    pass


CONVERSATION_ACTIONS_REGISTER: FrozenSet[type[Any]] = frozenset(
    {TagAction, MindVoiceAction, SpeakAction, AnnounceAction, WhisperAction}
)

# 场景可以用的所有动作
STAGE_AVAILABLE_ACTIONS_REGISTER: FrozenSet[type[Any]] = (
    frozenset(
        {
            StageNarrateAction,
            StageTagAction,
            DamageAction,
        }
    )
    | CONVERSATION_ACTIONS_REGISTER
)


# 角色交互类动作
ACTOR_INTERACTIVE_ACTIONS_REGISTER: FrozenSet[type[Any]] = frozenset(
    {
        DeadAction,
        GoToAction,
        StealPropAction,
        GivePropAction,
        UpdateAppearanceAction,
        SkillAction,
        DamageAction,
        EquipPropAction,
    }
)

# 角色可以用的所有动作
ACTOR_AVAILABLE_ACTIONS_REGISTER: FrozenSet[type[Any]] = (
    ACTOR_INTERACTIVE_ACTIONS_REGISTER | CONVERSATION_ACTIONS_REGISTER
)
