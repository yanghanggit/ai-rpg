from entitas import ExecuteProcessor, Matcher, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from ecs_systems.components import ActorComponent, StageComponent, StageNarrateComponent
import ecs_systems.cn_builtin_prompt as builtin_prompt
from ecs_systems.cn_constant_prompt import _CNConstantPrompt_
from typing import Set, override, Dict, List
import file_system.helper
from file_system.files_def import PropFile
from rpg_game.rpg_game import RPGGame
from file_system.files_def import (
    PropFile,
    StageArchiveFile,
)


#### 一次处理过程的封装，目前是非常笨的方式（而且不是最终版本），后续可以优化。
###############################################################################################################################################
class UpdateArchiveHelper:
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        ##我的参数
        self._context = context
        self._stages: Set[str] = set()
        self._actors: Set[str] = set()
        self._chat_history: Dict[str, str] = {}
        self._actor_prop_description: Dict[str, List[str]] = {}
        self._rpg_game = rpg_game

        self.build()

    ###############################################################################################################################################
    def build(self) -> None:
        ## step1: 所有拥有初始化记忆的场景拿出来
        self._stages = self.build_stages()
        ## step2: 所有拥有初始化记忆的Actor拿出来
        self._actors = self.build_actors()
        ## step3: 打包Actor的对话历史，方便后续查找
        self._chat_history = self.build_chat_history()
        ## step4: 所有拥有初始化记忆的Actor的道具信息拿出来
        self._actor_prop_description = self.build_actor_prop_description()

    ###############################################################################################################################################
    def build_stages(self) -> Set[str]:
        ret: Set[str] = set()
        stage_entities: Set[Entity] = self._context.get_group(
            Matcher(StageComponent)
        ).entities
        for stage_entity in stage_entities:
            stage_comp = stage_entity.get(StageComponent)
            ret.add(stage_comp.name)
        return ret

    ###############################################################################################################################################
    def build_actors(self) -> Set[str]:
        ret: Set[str] = set()
        actor_entities: Set[Entity] = self._context.get_group(
            Matcher(ActorComponent)
        ).entities
        for actor_entity in actor_entities:
            actor_comp = actor_entity.get(ActorComponent)
            ret.add(actor_comp.name)
        return ret

    ###############################################################################################################################################
    def build_chat_history(self) -> Dict[str, str]:
        tags: Set[str] = {
            self._rpg_game.about_game,
            _CNConstantPrompt_.BATCH_CONVERSATION_ACTION_EVENTS_TAG,
            _CNConstantPrompt_.SPEAK_ACTION_TAG,
            _CNConstantPrompt_.WHISPER_ACTION_TAG,
            _CNConstantPrompt_.BATCH_CONVERSATION_ACTION_EVENTS_TAG,
        }

        ret: Dict[str, str] = {}

        actor_entities = self._context.get_group(Matcher(ActorComponent)).entities
        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            filter_chat_history = (
                self._context._langserve_agent_system.create_filter_chat_history(
                    actor_comp.name, tags
                )
            )
            ret[actor_comp.name] = " ".join(filter_chat_history)

        return ret

    ###############################################################################################################################################
    def build_actor_prop_description(self) -> Dict[str, List[str]]:

        ret: Dict[str, List[str]] = {}

        actor_entities: Set[Entity] = self._context.get_group(
            Matcher(ActorComponent)
        ).entities
        for actor_entity in actor_entities:
            actor_comp = actor_entity.get(ActorComponent)
            prop_files = self._context._file_system.get_files(PropFile, actor_comp.name)
            desc: List[str] = []
            for file in prop_files:
                desc.append(f"{file.name}:{file.description}")
            ret[actor_comp.name] = desc

        return ret

    ###############################################################################################################################################
    @property
    def stage_names(self) -> Set[str]:
        return self._stages

    ###############################################################################################################################################
    @property
    def actor_names(self) -> Set[str]:
        return self._actors

    ###############################################################################################################################################
    def get_actor_prop_description(self, actor_name: str) -> List[str]:
        return self._actor_prop_description.get(actor_name, [])

    ###############################################################################################################################################
    def get_stage_archive(self, actor_name: str) -> Set[str]:

        ret = (
            self.mentioned_in_prop_description(self.stage_names, actor_name)
            | self.mentioned_in_kick_off_message(self.stage_names, actor_name)
            | self.mentioned_in_chat_history(self.stage_names, actor_name)
        )

        # 当前场景总要加一个
        actor_entity = self._context.get_actor_entity(actor_name)
        assert actor_entity is not None
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        assert stage_entity is not None
        safe_name = self._context.safe_get_entity_name(stage_entity)
        ret.add(safe_name)

        return ret

    ###############################################################################################################################################
    def get_actor_archive(self, actor_name: str) -> Set[str]:
        # 取并集
        ret = (
            self.mentioned_in_prop_description(self.actor_names, actor_name)
            | self.mentioned_in_kick_off_message(self.actor_names, actor_name)
            | self.mentioned_in_chat_history(self.actor_names, actor_name)
        )
        ret.discard(actor_name)  ##去掉自己，没必要认识自己
        return ret

    ###############################################################################################################################################
    def mentioned_in_prop_description(
        self, check_names: Set[str], actor_name: str
    ) -> Set[str]:
        ret: Set[str] = set()
        for prop_info in self._actor_prop_description.get(actor_name, []):
            for name in check_names:
                if prop_info.find(name) != -1:
                    ret.add(name)
        return ret

    ###############################################################################################################################################
    def mentioned_in_kick_off_message(
        self, check_names: Set[str], actor_name: str
    ) -> Set[str]:
        ret: Set[str] = set()
        kick_off_message = self._context._kick_off_message_system.get_message(
            actor_name
        )
        for name in check_names:
            if name in kick_off_message:
                ret.add(name)
        return ret

    ###############################################################################################################################################
    def mentioned_in_chat_history(
        self, check_names: Set[str], actor_name: str
    ) -> Set[str]:
        ret: Set[str] = set()
        chat_history = self._chat_history.get(actor_name, "")
        for name in check_names:
            if chat_history.find(name) != -1:
                ret.add(name)
        return ret


###############################################################################################################################################


class UpdateArchiveSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._rpg_game: RPGGame = rpg_game

    ###############################################################################################################################################
    @override
    def execute(self) -> None:
        self.update_archive()

    ###############################################################################################################################################
    def update_archive(self) -> None:
        # 建立数据
        context = self._context
        archive_helper = UpdateArchiveHelper(self._context, self._rpg_game)
        # 对Actor进行处理
        actor_entities: Set[Entity] = context.get_group(
            Matcher(all_of=[ActorComponent])
        ).entities
        for actor_entity in actor_entities:
            # 更新Actor的Actor档案，可能更新了谁认识谁，还有如果在场景中，外观是什么
            self.update_actor_archive(actor_entity, archive_helper)
            # 更新Actor的场景档案，
            self.update_stage_archive(actor_entity, archive_helper)
            self.update_stage_narrate_of_archive(actor_entity)

    ###############################################################################################################################################
    def update_actor_archive(
        self, actor_entity: Entity, helper: UpdateArchiveHelper
    ) -> None:
        #
        actor_comp = actor_entity.get(ActorComponent)
        actor_archives: Set[str] = helper.get_actor_archive(actor_comp.name)
        if len(actor_archives) == 0:
            logger.warning(f"{actor_comp.name} 什么人都不认识，这个合理么？")
            return

        # 补充文件，有可能是新的人，也有可能全是旧的人
        file_system.helper.add_actor_archive_files(
            self._context._file_system, actor_comp.name, actor_archives
        )

        # 更新文件，只更新场景内我能看见的人
        appearance_data = self._context.appearance_in_stage(actor_entity)
        for name in actor_archives:
            appearance = appearance_data.get(name, "")
            if appearance != "":
                file_system.helper.update_actor_archive_file(
                    self._context._file_system, actor_comp.name, name, appearance
                )

        # 更新chat history
        message = builtin_prompt.update_actor_archive_prompt(
            actor_comp.name, actor_archives
        )

        exclude_chat_history: Set[str] = set()
        exclude_chat_history.add(message)

        # 过去的都删除了
        self._context._langserve_agent_system.exclude_content_then_rebuild_chat_history(
            actor_comp.name, exclude_chat_history
        )

        # 添加新的
        self._context.safe_add_human_message_to_entity(actor_entity, message)

    ###############################################################################################################################################
    def update_stage_archive(
        self, actor_entity: Entity, helper: UpdateArchiveHelper
    ) -> None:
        actor_comp = actor_entity.get(ActorComponent)
        stage_archives = helper.get_stage_archive(actor_comp.name)
        if len(stage_archives) == 0:
            logger.warning(f"{actor_comp.name} 什么地点都不知道，这个合理么？")
            return

        # 写文件
        file_system.helper.add_stage_archive_files(
            self._context._file_system, actor_comp.name, stage_archives
        )

        # 更新chat history
        message = builtin_prompt.update_stage_archive_prompt(
            actor_comp.name, stage_archives
        )

        exclude_chat_history: Set[str] = set()
        exclude_chat_history.add(message)

        # 过去的都删除了
        self._context._langserve_agent_system.exclude_content_then_rebuild_chat_history(
            actor_comp.name, exclude_chat_history
        )

        # 添加新的
        self._context.safe_add_human_message_to_entity(actor_entity, message)

    ###############################################################################################################################################
    def update_stage_narrate_of_archive(self, actor_entity: Entity) -> None:
        current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
        if current_stage_entity is None:
            return

        actor_comp = actor_entity.get(ActorComponent)
        stage_narrate_comp = current_stage_entity.get(StageNarrateComponent)
        stage_archive = self._context._file_system.get_file(
            StageArchiveFile, actor_comp.name, stage_narrate_comp.name
        )
        if stage_archive is None or stage_narrate_comp.narrate == "":
            assert stage_archive is not None
            return

        stage_archive._last_stage_narrate = str(stage_narrate_comp.narrate)
        stage_archive._last_stage_narrate_round = stage_narrate_comp.round
        self._context._file_system.write_file(stage_archive)

    ###############################################################################################################################################
