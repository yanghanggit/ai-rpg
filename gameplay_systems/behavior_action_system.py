from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from my_components.action_components import (
    BehaviorAction,
    SkillTargetAction,
    SkillAction,
    SkillUsePropAction,
    WorldSkillSystemRuleAction,
)
from my_components.components import StageComponent, WeaponComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override, Set, Optional, Any
from extended_systems.prop_file import PropFile
from rpg_game.rpg_game import RPGGame
from my_models.event_models import AgentEvent


################################################################################################################################################


def _generate_behavior_result_prompt(
    actor_name: str, behavior_sentence: str, result: bool
) -> str:
    if result:
        prompt1 = f"""# {actor_name} 准备发起一次使用技能的行动。
## 输入语句
{behavior_sentence}
## 分析过程
输入语句中应至少包含一个技能与一个目标。可以选择性的包含道具。
## 结果
系统经过分析之后允许了这次行动。"""
        return prompt1

    prompt2 = f""" #{actor_name} 准备发起一次使用技能的行动。
## 输入语句
{behavior_sentence}
## 分析过程
输入语句中应至少包含一个技能与一个目标。可以选择性的包含道具。
## 结果
- 注意！系统经过分析之后拒绝了这次行动。
- 请 {actor_name} 检查 输入语句。是否满足 分析过程 中提到的要求。"""

    return prompt2


@final
class BehaviorActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(BehaviorAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(BehaviorAction)

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ######################################################################################################################################################
    def handle(self, entity: Entity) -> None:

        behavior_action = entity.get(BehaviorAction)
        if len(behavior_action.values) == 0:
            return

        behavior_sentence = behavior_action.values[0]
        if behavior_sentence == "":
            return

        # 基础数据
        targets = self.extract_targets_info(entity, behavior_sentence)
        skills = self.extract_skills_info(entity, behavior_sentence)
        # 不用继续了
        if len(targets) == 0 or len(skills) == 0:
            self.on_behavior_action_result_event(entity, behavior_sentence, False)
            return

        props = self.extract_props_info(entity, behavior_sentence)

        # 默认会添加当前武器? 先不用。
        weapon_prop = self.get_current_weapon(entity)
        if weapon_prop is not None:
            pass
            # props.add(weapon_prop)

        # 添加动作
        self.clear_action(entity)
        self.add_skill_target_action(entity, targets)
        self.add_skill_action(entity, skills)
        self.add_skill_use_prop_action(entity, props)

        # 事件通知
        self.on_behavior_action_result_event(entity, behavior_sentence, True)

    ######################################################################################################################################################
    def get_current_weapon(self, entity: Entity) -> Optional[PropFile]:
        if not entity.has(WeaponComponent):
            return None
        current_weapon_comp = entity.get(WeaponComponent)
        return self._context._file_system.get_file(
            PropFile, current_weapon_comp.name, current_weapon_comp.propname
        )

    ######################################################################################################################################################
    def clear_action(
        self,
        entity: Entity,
        actions_comp: Set[type[Any]] = set(
            {
                SkillTargetAction,
                SkillAction,
                SkillUsePropAction,
                WorldSkillSystemRuleAction,
            }
        ),
    ) -> None:

        for action_comp in actions_comp:
            if entity.has(action_comp):
                entity.remove(action_comp)

    ######################################################################################################################################################

    def extract_targets_info(self, entity: Entity, sentence: str) -> Set[str]:

        current_stage_entity = self._context.safe_get_stage_entity(entity)
        assert current_stage_entity is not None
        if current_stage_entity is None:
            return set()

        current_stage_name = current_stage_entity.get(StageComponent).name
        if current_stage_name in sentence:
            # 有场景就是直接是场景的。放弃下面的处理！
            return set({current_stage_name})

        ret: Set[str] = set()
        actor_names = self._context.get_actor_names_in_stage(current_stage_entity)
        for actor_name in actor_names:
            if actor_name in sentence:
                ret.add(actor_name)
        return ret

    ######################################################################################################################################################
    def add_skill_target_action(self, entity: Entity, target_names: Set[str]) -> None:
        if len(target_names) == 0:
            return
        entity.add(
            SkillTargetAction,
            self._context.safe_get_entity_name(entity),
            list(target_names),
        )

    ######################################################################################################################################################
    def extract_skills_info(self, entity: Entity, sentence: str) -> Set[PropFile]:

        safe_name = self._context.safe_get_entity_name(entity)
        skill_files = self._context._file_system.get_files(PropFile, safe_name)

        ret: Set[PropFile] = set()
        for skill_file in skill_files:
            if not skill_file.is_skill:
                continue

            if skill_file.name in sentence:
                ret.add(skill_file)

        return ret

    ######################################################################################################################################################
    def add_skill_action(
        self, entity: Entity, prop_name_as_skill_name: Set[PropFile]
    ) -> None:
        if len(prop_name_as_skill_name) == 0:
            return
        skill_names = [skill.name for skill in prop_name_as_skill_name]
        entity.add(SkillAction, self._context.safe_get_entity_name(entity), skill_names)

    ######################################################################################################################################################
    def extract_props_info(self, entity: Entity, sentence: str) -> Set[PropFile]:

        safe_name = self._context.safe_get_entity_name(entity)
        prop_files = self._context._file_system.get_files(PropFile, safe_name)
        ret: Set[PropFile] = set()
        for prop_file in prop_files:
            if prop_file.is_skill:
                continue
            if prop_file.name in sentence:
                ret.add(prop_file)

        return ret

    ######################################################################################################################################################
    def add_skill_use_prop_action(self, entity: Entity, props: Set[PropFile]) -> None:
        if len(props) == 0:
            return
        prop_names = [prop.name for prop in props]
        entity.add(
            SkillUsePropAction, self._context.safe_get_entity_name(entity), prop_names
        )

    ######################################################################################################################################################
    def on_behavior_action_result_event(
        self, entity: Entity, behavior_sentence: str, processed_result: bool
    ) -> None:

        # 需要给到agent
        self._context.notify_event(
            set({entity}),
            AgentEvent(
                message_content=_generate_behavior_result_prompt(
                    self._context.safe_get_entity_name(entity),
                    behavior_sentence,
                    processed_result,
                )
            ),
        )

    ######################################################################################################################################################
