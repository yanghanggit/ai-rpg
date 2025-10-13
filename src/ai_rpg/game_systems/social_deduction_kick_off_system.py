import copy
from typing import List, final, Dict, Set
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..entitas import ExecuteProcessor, InitializeProcessor, Matcher, Entity
from ..game.tcg_game import TCGGame
from ..models import (
    ModeratorComponent,
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    SDCharacterSheetName,
    AppearanceComponent,
    EnvironmentComponent,
    DiscussionAction,
    MindVoiceAction,
)
from ..utils.md_format import format_dict_as_markdown_list
from ..chat_services.client import ChatClient
from ..utils import json_format


###############################################################################################################################################
@final
class PlayerAwarenessResponse(BaseModel):
    mind_voice: str
    discussion: str


###############################################################################################################################################


###############################################################################################################################################
@final
class SocialDeductionKickOffSystem(ExecuteProcessor, InitializeProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def initialize(self) -> None:
        # 分配角色
        self._assign_role_to_all_actors()

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        if self._game._time_marker > 0:
            return
        logger.info("第一夜，狼人请睁眼")

        # 给狼人添加上下文来识别同伴
        self._reveal_werewolf_allies()

        # 第一次观察其他的参赛选手
        self._initialize_player_awareness()

        # 每一个人都自我介绍一下
        await self._conduct_player_introductions()

    ###############################################################################################################################################
    # TODO: 这里可以优化成配置化的, 临时先写死。
    def _assign_role_to_all_actors(self) -> None:
        """为所有角色分配狼人杀角色"""

        all_actors = self._game._world.boot.actors
        for actor in all_actors:

            actor_entity = self._game.get_entity_by_name(actor.name)
            assert actor_entity is not None, f"Actor Entity 不存在: {actor.name}"

            match actor.character_sheet.name:
                case SDCharacterSheetName.MODERATOR:
                    actor_entity.replace(ModeratorComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Moderator")

                case SDCharacterSheetName.WEREWOLF:
                    actor_entity.replace(WerewolfComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Werewolf")

                case SDCharacterSheetName.SEER:
                    actor_entity.replace(SeerComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Seer")

                case SDCharacterSheetName.WITCH:
                    actor_entity.replace(WitchComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Witch")

                case SDCharacterSheetName.VILLAGER:
                    actor_entity.replace(VillagerComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Villager")

                case _:
                    assert False, f"未知的狼人杀角色: {actor.character_sheet.name}"

    ###############################################################################################################################################
    # 写一个函数，给狼人添加上下文来识别同伴
    def _reveal_werewolf_allies(self) -> None:
        """给狼人添加上下文来识别同伴"""
        werewolf_entities = self._game.get_group(
            Matcher(
                all_of=[WerewolfComponent],
            )
        ).entities.copy()

        for entity in werewolf_entities:

            # 每次循环都创建一个新的集合，避免修改原集合
            copy_entities = copy.copy(werewolf_entities)
            copy_entities.discard(entity)

            allied_werewolf_names = [
                e.get(WerewolfComponent).name for e in copy_entities
            ]
            logger.info(f"Werewolf {entity.name} 的同伴: {allied_werewolf_names}")
            self._game.append_human_message(
                entity,
                f"# 提示！你的同伴狼人有: {', '.join(allied_werewolf_names)}",
            )

    ###############################################################################################################################################
    def _get_all_player_entities(self) -> Set[Entity]:
        """获取所有参赛选手实体（排除主持人）"""
        return self._game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
                # none_of=[ModeratorComponent],
            )
        ).entities.copy()

    ###############################################################################################################################################
    def _get_stage_appearance_mapping(
        self, all_actor_entities: Set[Entity]
    ) -> Dict[str, str]:
        """创建角色外貌映射字典"""
        stage_actor_appearances_mapping: Dict[str, str] = {}
        for actor_entity in all_actor_entities:
            appearance_comp = actor_entity.get(AppearanceComponent)
            stage_actor_appearances_mapping[actor_entity.name] = (
                appearance_comp.appearance
            )

        logger.info(
            f"stage_actor_appearances_mapping = {stage_actor_appearances_mapping}"
        )
        return stage_actor_appearances_mapping

    ###############################################################################################################################################
    def _create_awareness_prompt(
        self, environment_description: str, other_players_mapping: Dict[str, str]
    ) -> str:
        """创建玩家感知提示"""
        return f"""# 提示！准备开始比赛！你观察了场景与参赛的人员。

## 场景描述: 
 
{environment_description}

## 参赛选手及外貌:

{format_dict_as_markdown_list(other_players_mapping)}"""

    ###############################################################################################################################################
    # 第一次观察其他的参赛选手
    def _initialize_player_awareness(self) -> None:
        """初始化玩家感知，让每个玩家观察场景和其他玩家"""
        # 获取所有参赛选手
        all_actor_entities = self._get_all_player_entities()

        # 获取环境描述
        environment_description = self._get_environment_description()

        # 获取所有玩家的外貌映射
        stage_actor_appearances_mapping = self._get_stage_appearance_mapping(
            all_actor_entities
        )

        # 为每个玩家生成感知提示
        for actor_entity in all_actor_entities:
            other_players_mapping = self._get_other_players_mapping(
                stage_actor_appearances_mapping, actor_entity.name
            )
            prompt = self._create_awareness_prompt(
                environment_description, other_players_mapping
            )
            self._game.append_human_message(actor_entity, prompt)

    ###############################################################################################################################################
    def _get_environment_description(self) -> str:
        """获取环境描述"""
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "玩家实体不存在"

        stage_entity = self._game.safe_get_stage_entity(player_entity)
        assert stage_entity is not None, "场景实体不存在"

        environment_comp = stage_entity.get(EnvironmentComponent)
        assert environment_comp is not None, "场景组件不存在"

        return environment_comp.description

    ###############################################################################################################################################
    def _get_other_players_mapping(
        self, all_players_mapping: Dict[str, str], current_player_name: str
    ) -> Dict[str, str]:
        """获取其他玩家的外貌映射（排除当前玩家）"""
        other_players_mapping = copy.copy(all_players_mapping)
        other_players_mapping.pop(current_player_name, None)
        return other_players_mapping

    ###############################################################################################################################################
    def _create_introduction_prompt(self) -> str:
        """创建自我介绍提示"""
        response_sample = PlayerAwarenessResponse(
            mind_voice="你此时的内心想法，你为什么要如此的发言。如果你是狼人，请你确认谁是你的同伴。如果是不是，请你猜测谁是狼人。",
            discussion="你要发言的内容。",
        )

        return f"""# 指令！现在请你做一个自我介绍的发言。

## 内容建议

介绍你是谁，你的外貌，你的性格，你的兴趣爱好，你的特长。
注意！不要暴露你的身份信息! 你可以编造一些信息来掩盖你的身份。

## 输出格式

### 标准示例

```json
{response_sample.model_dump_json()}
```

## 输出要求

请严格按照上述的 JSON 标准示例 格式输出！"""

    ###############################################################################################################################################
    def _create_chat_requests(
        self, all_actor_entities: Set[Entity]
    ) -> List[ChatClient]:
        """为所有玩家创建聊天请求"""
        request_handlers: List[ChatClient] = []
        prompt = self._create_introduction_prompt()

        for entity in all_actor_entities:
            agent_short_term_memory = self._game.get_agent_chat_history(entity)
            request_handlers.append(
                ChatClient(
                    name=entity.name,
                    prompt=prompt,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )

        return request_handlers

    ###############################################################################################################################################
    def _process_introduction_response(self, request_handler: ChatClient) -> None:
        """处理单个玩家的自我介绍响应"""
        entity = self._game.get_entity_by_name(request_handler.name)
        assert entity is not None, f"实体不存在: {request_handler.name}"

        logger.info(
            f"{request_handler.name} 的自我介绍: {request_handler.response_content}"
        )

        try:
            response = PlayerAwarenessResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.response_content)
            )

            if response.mind_voice != "":
                logger.info(f"{request_handler.name} 的内心独白: {response.mind_voice}")
                entity.replace(MindVoiceAction, entity.name, response.mind_voice)

            if response.discussion != "":
                logger.info(f"{request_handler.name} 的发言: {response.discussion}")
                entity.replace(DiscussionAction, entity.name, response.discussion)

        except Exception as e:
            logger.error(f"Exception: {e}")
            # 出现异常时，添加一个默认的讨论动作
            entity.replace(DiscussionAction, entity.name, "大家好，很高兴见到大家！")

    ###############################################################################################################################################
    # 每一个人都自我介绍一下
    async def _conduct_player_introductions(self) -> None:
        """每一个人都自我介绍一下"""
        # 获取所有参赛选手
        all_actor_entities = self._get_all_player_entities()

        # 创建聊天请求
        request_handlers = self._create_chat_requests(all_actor_entities)

        # 并发执行所有请求
        await ChatClient.gather_request_post(clients=request_handlers)

        # 处理所有响应
        for request_handler in request_handlers:
            self._process_introduction_response(request_handler)

    ###############################################################################################################################################
