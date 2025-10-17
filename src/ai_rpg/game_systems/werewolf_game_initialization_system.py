import copy
from typing import List, final, Dict, Set
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..entitas import ExecuteProcessor, Matcher, Entity
from ..game.tcg_game import TCGGame
from ..models import (
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    AppearanceComponent,
    EnvironmentComponent,
    DiscussionAction,
    MindEvent,
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
class WerewolfGameInitializationSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        assert (
            self._game._werewolf_game_turn_counter == 0
        ), "时间标记必须是0，是夜晚!!!!!!"
        # if self._game._werewolf_game_turn_counter > 0:
        #     log
        #     return
        logger.warning(
            "狼人杀游戏初始化系统执行============================================"
        )

        # 给狼人添加上下文来识别同伴
        self._reveal_werewolf_allies()

        # 第一次观察其他的参赛选手
        self._initialize_player_awareness()

        # 每一个人都自我介绍一下
        await self._conduct_player_introductions()

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
            # logger.info(f"Werewolf {entity.name} 的同伴: {allied_werewolf_names}")
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

介绍你是谁，你的外貌，你的性格，你的兴趣爱好，你的特长。不要提到和自己身份相关的信息。
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

        try:
            response = PlayerAwarenessResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.response_content)
            )

            if response.mind_voice != "":

                self._game.notify_entities(
                    set({entity}),
                    MindEvent(
                        message=f"{entity.name} : {response.mind_voice}",
                        actor=entity.name,
                        content=response.mind_voice,
                    ),
                )

            if response.discussion != "":
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
