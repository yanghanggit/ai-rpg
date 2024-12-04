from typing import Final, FrozenSet, NamedTuple, List, final


class ActionComponent(NamedTuple):
    name: str
    values: List[str]


############################################################################################################
############################################################################################################
############################################################################################################
# 内心独白
@final
class MindVoiceAction(ActionComponent):
    pass


# 场景内广播
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


# 特征标签
@final
class TagAction(ActionComponent):
    pass


GENERAL_CONVERSATION_ACTIONS_REGISTER: Final[FrozenSet[type[NamedTuple]]] = frozenset(
    {TagAction, MindVoiceAction, SpeakAction, AnnounceAction, WhisperAction}
)
############################################################################################################
############################################################################################################
############################################################################################################


# 从目标角色处偷取
@final
class StealPropAction(ActionComponent):
    pass


# 将道具转移至目标角色
@final
class TransferPropAction(ActionComponent):
    pass


# 装备道具
@final
class EquipPropAction(ActionComponent):
    pass


ACTOR_PROP_ACTIONS_REGISTER: Final[FrozenSet[type[NamedTuple]]] = frozenset(
    {StealPropAction, TransferPropAction, EquipPropAction}
)
############################################################################################################
############################################################################################################
############################################################################################################


@final
class SkillAction(ActionComponent):
    pass


# 处理伤害逻辑
@final
class DamageAction(ActionComponent):
    pass


# 处理治疗逻辑
@final
class HealAction(ActionComponent):
    pass


SKILL_ACTIONS_REGISTER: Final[FrozenSet[type[NamedTuple]]] = frozenset(
    {SkillAction, DamageAction, HealAction}
)

############################################################################################################
############################################################################################################
############################################################################################################


@final
class DeadAction(ActionComponent):
    pass


# 特殊：更新外观
@final
class UpdateAppearanceAction(ActionComponent):
    pass


# 离开当前场景并去往
@final
class GoToAction(ActionComponent):
    pass


# 特殊：角色A对角色B进行检查，获取有关B的信息，例如携带的道具、健康状态等。
@final
class InspectAction(ActionComponent):
    pass


ACTOR_SPECIFIC_ACTIONS_REGISTER: Final[FrozenSet[type[NamedTuple]]] = frozenset(
    {DeadAction, UpdateAppearanceAction, GoToAction, InspectAction}
)
############################################################################################################
############################################################################################################
############################################################################################################


# 场景专用
# 场景专用: 场景环境的描述
@final
class StageNarrateAction(ActionComponent):
    pass


# 场景专用: 输出场景中所有显著的道具和物件的标记，以便进一步处理或引用。这样，每次场景更新时，系统不仅生成详细的场景描述，还会同步输出这些场景内的道具和物件标记，使得场景内容的处理更加完善和细致。
@final
class StageTagAction(ActionComponent):
    pass


# 场景专用: 场景将道具标记转移给目标角色
@final
class StageTransferAction(ActionComponent):
    pass


# 场景可以用的所有动作
STAGE_AVAILABLE_ACTIONS_REGISTER: Final[FrozenSet[type[NamedTuple]]] = (
    frozenset(
        {
            StageNarrateAction,
            StageTagAction,
            StageTransferAction,
        }
    )
    | SKILL_ACTIONS_REGISTER
    | GENERAL_CONVERSATION_ACTIONS_REGISTER
)
############################################################################################################
############################################################################################################
############################################################################################################


# 角色可以用的所有动作
ACTOR_AVAILABLE_ACTIONS_REGISTER: Final[FrozenSet[type[NamedTuple]]] = (
    ACTOR_PROP_ACTIONS_REGISTER
    | ACTOR_SPECIFIC_ACTIONS_REGISTER
    | SKILL_ACTIONS_REGISTER
    | GENERAL_CONVERSATION_ACTIONS_REGISTER
)
############################################################################################################
############################################################################################################
############################################################################################################
