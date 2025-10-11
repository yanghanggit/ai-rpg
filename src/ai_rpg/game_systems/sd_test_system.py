from typing import List, Set, final, Dict
from loguru import logger
from overrides import override
from ..chat_services.client import ChatClient
from ..entitas import Entity, ExecuteProcessor
from ..game.sd_game import SDGame


###############################################################################################################################################
@final
class SDTestSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: SDGame) -> None:
        self._game: SDGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:

        # 获取玩家实体和舞台实体
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "Player entity must exist"

        # 获取当前舞台实体
        stage_entity = self._game.safe_get_stage_entity(player_entity)
        assert stage_entity is not None, "Stage entity must exist"

        # 获取当前舞台上的所有角色及其外观
        stage_actor_appearances = self._game.get_stage_actor_appearances(stage_entity)
        for actor, appearance in stage_actor_appearances.items():
            logger.info(f"Actor on stage: {actor}, Appearance: {appearance}")

        # 获取当前舞台上存活的角色实体
        alive_actors = self._game.get_alive_actors_on_stage(stage_entity)
        for actor_entity in alive_actors:
            logger.info(f"Alive Actor on stage: {actor_entity.name}")

        # 从 alive_actors 中移除 has PlayerComponent 的实体
        # alive_actors = {
        #     actor for actor in alive_actors if not actor.has(PlayerComponent)
        # }

        # 处理请求
        await self._process_request(alive_actors, stage_actor_appearances)

    ###############################################################################################################################################
    async def _process_request(
        self, entities: Set[Entity], stage_actor_appearances: Dict[str, str]
    ) -> None:

        # 添加请求处理器
        request_handlers: List[ChatClient] = []

        for entity1 in entities:

            # 不同实体生成不同的提示
            gen_prompt = self._generate_prompt(entity1, stage_actor_appearances.copy())
            assert gen_prompt != "", "Generated prompt should not be empty"

            agent_short_term_memory = self._game.get_agent_chat_history(entity1)
            request_handlers.append(
                ChatClient(
                    name=entity1.name,
                    prompt=gen_prompt,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )

        # 并发
        await ChatClient.gather_request_post(clients=request_handlers)

        # 添加上下文。
        for request_handler in request_handlers:

            entity2 = self._game.get_entity_by_name(request_handler.name)
            assert entity2 is not None

            # 使用封装的函数整合聊天上下文
            self._game.append_human_message(
                entity2, request_handler.prompt, kickoff=entity2.name
            )
            self._game.append_ai_message(entity2, request_handler.response_ai_messages)

    ###############################################################################################################################################
    def _generate_prompt(
        self, entity: Entity, stage_actor_appearances: Dict[str, str]
    ) -> str:

        stage_actor_appearances.pop(entity.name, None)  # 移除自己

        # 生成提示词
        return f"""# 注意！这是一次观察。

## 场景中参与游戏的角色的信息(名称+外观信息)：
{stage_actor_appearances}

## 请你基于这些信息，描述你对当前场景的观察。描述要简短(<100字)，并且要符合你的角色身份和背景。

- 你可以猜测谁是狼人，谁是村民，谁是预言家，谁是女巫。"""

    ###############################################################################################################################################
