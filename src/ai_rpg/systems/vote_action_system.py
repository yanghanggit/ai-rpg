import random
from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import VoteAction, DayVoteOutComponent, AgentEvent, VoteEvent
from loguru import logger
from ..game.sdg_game import SDGGame


@final
class VoteActionSystem(ReactiveProcessor):

    def __init__(self, game_context: SDGGame) -> None:
        super().__init__(game_context)
        self._game: SDGGame = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(VoteAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(VoteAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        # logger.debug("投票行动系统触发")

        # 加一个统计的数据结构dict[str, int], 将投票结果统计出来， str是 target_name， int是票数
        vote_count: dict[str, int] = {}
        for entity in entities:
            vote_action = entity.get(VoteAction)
            assert vote_action is not None, "实体必须有 VoteAction 组件"
            target_name = vote_action.target_name
            if target_name not in vote_count:
                vote_count[target_name] = 0
            vote_count[target_name] += 1

            # 发送投票细节
            self._game.notify_entities(
                set({entity}),
                VoteEvent(
                    message=f"{entity.name} 投票给 {target_name}",
                    actor=entity.name,
                    target=target_name,
                ),
            )
        logger.success(f"投票行动: {entity.name} 投票给 {target_name}")

        # 从 vote_count 中找出票数最高的 target_name
        if len(vote_count) == 0:
            logger.debug("没有投票结果")
            return

        #
        logger.info(f"!!!!!投票统计结果!!!!!!!: \n{vote_count}")

        max_votes = max(vote_count.values())
        winners = [name for name, count in vote_count.items() if count == max_votes]

        # 如果有多个最高票数的，说明是平票，随机选一个
        if len(winners) > 1:
            logger.debug(f"投票结果平票，随机选择一个: {winners}")
            chosen_one = random.choice(winners)
        else:
            chosen_one = winners[0]

        logger.info(
            f"最终投票结果（如果有平局就会系统从最高票数中随机选择）: {chosen_one} 获得最高票数 {max_votes}"
        )
        target_entity = self._game.get_entity_by_name(chosen_one)
        if target_entity is None:
            logger.error(f"无法找到投票结果实体: {chosen_one}")
            return

        logger.info(f"玩家 {target_entity.name} 被投票出局了")
        # 给被投票出局的玩家添加死亡标记
        target_entity.replace(DayVoteOutComponent, target_entity.name)

        # 宣布被投票出局了
        self._game.broadcast_to_stage(
            entity=target_entity,
            agent_event=AgentEvent(
                message=f"# 发生事件！{target_entity.name} 被投票出局了！",
            ),
        )

    ####################################################################################################################################
