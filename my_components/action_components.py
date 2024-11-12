from typing import Any, FrozenSet, NamedTuple, List, final


class ActionComponent(NamedTuple):
    name: str
    values: List[str]


# 场景环境的描述
@final
class StageNarrateAction(ActionComponent):
    pass


# 内心独白
@final
class MindVoiceAction(ActionComponent):
    pass


# 场景内广播
@final
class BroadcastAction(ActionComponent):
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


# 从场景内可以拾取道具
@final
class PickUpPropAction(ActionComponent):
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


# 场景内销毁道具
@final
class RemovePropAction(ActionComponent):
    pass


CONVERSATION_ACTIONS_REGISTER: FrozenSet[type[Any]] = frozenset(
    {TagAction, MindVoiceAction, SpeakAction, BroadcastAction, WhisperAction}
)

# 场景可以用的所有动作
STAGE_AVAILABLE_ACTIONS_REGISTER: FrozenSet[type[Any]] = (
    frozenset(
        {
            StageNarrateAction,
            RemovePropAction,
            DamageAction,
        }
    )
    | CONVERSATION_ACTIONS_REGISTER
)


# 角色交互类动作
ACTOR_INTERACTIVE_ACTIONS_REGISTER: FrozenSet[type[Any]] = frozenset(
    {
        PickUpPropAction,
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
