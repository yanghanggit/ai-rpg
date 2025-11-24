import random
from typing import Set
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.tcg_game import TCGGame
from .game_server_depends import GameServerInstance
from ..models import (
    DungeonGamePlayRequest,
    DungeonGamePlayResponse,
    DungeonTransHomeRequest,
    DungeonTransHomeResponse,
    DrawCardsAction,
    Dungeon,
    HomeComponent,
    AllyComponent,
    DeathComponent,
    CombatStatsComponent,
    ActorComponent,
    HandComponent,
    PlayCardsAction,
)
from ..entitas import Matcher, Entity
from .dungeon_stage_transition import advance_to_next_stage

###################################################################################################################################################################
dungeon_gameplay_api_router = APIRouter()


###############################################################################################################################################
# TODO, 临时添加行动, 逻辑。
def _combat_actors_draw_cards_action(tcg_game: TCGGame) -> None:

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None

    actor_entities = tcg_game.get_alive_actors_on_stage(player_entity)
    for entity in actor_entities:
        entity.replace(
            DrawCardsAction,
            entity.name,
        )


###############################################################################################################################################
# TODO!!! 临时测试准备传送！！！
def _all_heros_return_home(tcg_game: TCGGame) -> None:

    heros_entities = tcg_game.get_group(Matcher(all_of=[AllyComponent])).entities
    assert len(heros_entities) > 0
    if len(heros_entities) == 0:
        logger.error("没有找到英雄!")
        return

    home_stage_entities = tcg_game.get_group(Matcher(all_of=[HomeComponent])).entities
    assert len(home_stage_entities) > 0
    if len(home_stage_entities) == 0:
        logger.error("没有找到家园!")
        return

    return_home_stage = next(iter(home_stage_entities))
    prompt = f"""# 提示！冒险结束，将要返回: {return_home_stage.name}"""
    for hero_entity in heros_entities:

        # 添加故事。
        tcg_game.append_human_message(hero_entity, prompt)

    # 开始传送。
    tcg_game.stage_transition(heros_entities, return_home_stage)

    # 清空地下城的实体!
    tcg_game.destroy_dungeon_entities(tcg_game.world.dungeon)

    # 设置空的地下城
    tcg_game._world.dungeon = Dungeon(name="")

    # 清除掉所有的战斗状态
    for hero_entity in heros_entities:

        # 不要的组件。
        if hero_entity.has(DeathComponent):
            logger.debug(f"remove death component: {hero_entity.name}")
            hero_entity.remove(DeathComponent)

        # 生命全部恢复。
        assert hero_entity.has(CombatStatsComponent)
        combat_stats_comp = hero_entity.get(CombatStatsComponent)
        combat_stats_comp.stats.hp = combat_stats_comp.stats.max_hp

        # 清空状态效果
        combat_stats_comp.status_effects.clear()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
# TODO, 临时添加行动, 逻辑。 activate_play_cards_action
def _combat_actors_random_play_cards_action(tcg_game: TCGGame) -> bool:
    """
    激活打牌行动，为所有轮次中的角色选择行动并设置执行计划。

    Returns:
        bool: 是否成功激活打牌行动
    """

    # 1. 验证游戏状态
    if len(tcg_game.current_combat_sequence.current_rounds) == 0:
        logger.error("没有回合，不能添加行动！")
        return False

    if not tcg_game.current_combat_sequence.is_ongoing:
        logger.error("没有进行中的回合，不能添加行动！")
        return False

    if tcg_game.current_combat_sequence.latest_round.is_completed:
        logger.error("回合已经完成，不能添加行动！")
        return False

    # 2. 验证所有角色的手牌状态
    actor_entities: Set[Entity] = tcg_game.get_group(
        Matcher(all_of=[ActorComponent, HandComponent], none_of=[DeathComponent])
    ).entities

    if len(actor_entities) == 0:
        logger.error("没有存活的并拥有手牌的角色，不能添加行动！")
        return False

    # 测试一下！
    for actor_entity in actor_entities:

        # 必须没有打牌行动
        assert (
            actor_entity.name
            in tcg_game.current_combat_sequence.latest_round.action_order
        ), f"{actor_entity.name} 不在本回合行动队列里"

        # 必须没有打牌行动
        assert not actor_entity.has(PlayCardsAction)
        hand_comp = actor_entity.get(HandComponent)
        assert len(hand_comp.cards) > 0, f"{actor_entity.name} 没有行动可用"

        # 选择一张卡牌随机使用
        selected_card = random.choice(hand_comp.cards)
        logger.debug(f"为角色 {actor_entity.name} 随机选择卡牌: {selected_card.name}")
        final_target = selected_card.target

        # 创建打牌行动
        actor_entity.replace(
            PlayCardsAction,
            actor_entity.name,
            selected_card,
            final_target,
        )

    return True


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
def _validate_dungeon_prerequisites(
    user_name: str,
    game_server: GameServerInstance,
) -> TCGGame:
    """
    验证地下城操作的前置条件

    Args:
        user_name: 用户名
        game_server: 游戏服务器实例

    Returns:
        WebTCGGame: 验证通过的游戏实例

    Raises:
        HTTPException: 验证失败时抛出异常
    """
    # 是否有房间？！！
    # room_manager = game_server.room_manager
    if not game_server.has_room(user_name):
        logger.error(f"dungeon operation: {user_name} has no room, please login first.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    # 是否有游戏？！！
    current_room = game_server.get_room(user_name)
    assert current_room is not None
    if current_room._tcg_game is None:
        logger.error(f"dungeon operation: {user_name} has no game, please login first.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏，请先登录",
        )

    # 是否是WebTCGGame？！！
    web_game = current_room._tcg_game
    assert isinstance(web_game, TCGGame)
    assert web_game is not None

    # 判断游戏状态，不是DUNGEON状态不可以推进。
    # if web_game.current_game_state != TCGGameState.DUNGEON:
    if not web_game.is_player_in_dungeon:
        logger.error(
            f"dungeon operation: {user_name} game state error !!!!! not in dungeon state."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能在地下城状态下使用",
        )

    # 判断是否有战斗
    if len(web_game.current_combat_sequence.combats) == 0:
        logger.error(f"len(web_game.current_engagement.combats) == 0")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有战斗可以进行",
        )

    return web_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _handle_dungeon_combat_kick_off(
    web_game: TCGGame,
) -> DungeonGamePlayResponse:
    """处理地下城战斗开始"""
    if not web_game.current_combat_sequence.is_starting:
        logger.error(f"not web_game.current_engagement.is_kickoff_phase")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="not web_game.current_engagement.is_kickoff_phase",
        )

    # 推进一次游戏, 即可转换ONGOING状态。
    # web_game.player_session.session_messages.clear()
    await web_game.combat_pipeline.process()
    # 返回！
    return DungeonGamePlayResponse(client_messages=[])


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _handle_draw_cards(web_game: TCGGame) -> DungeonGamePlayResponse:
    """处理抽卡操作"""
    if not web_game.current_combat_sequence.is_ongoing:
        logger.error(f"not web_game.current_engagement.is_on_going_phase")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="not web_game.current_engagement.is_on_going_phase",
        )

    # 推进一次游戏, 即可抽牌。
    # web_game.draw_cards_action()
    _combat_actors_draw_cards_action(web_game)
    # web_game.player_session.session_messages.clear()
    await web_game.combat_pipeline.process()

    # 返回！
    return DungeonGamePlayResponse(
        client_messages=[],
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _handle_play_cards(
    web_game: TCGGame, request_data: DungeonGamePlayRequest
) -> DungeonGamePlayResponse:
    """处理出牌操作"""
    if not web_game.current_combat_sequence.is_ongoing:
        logger.error(f"not web_game.current_engagement.is_on_going_phase")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="not web_game.current_engagement.is_on_going_phase",
        )

    logger.debug(f"玩家输入 = {request_data.user_input.tag}, 准备行动......")
    # if web_game.play_cards_action():
    if _combat_actors_random_play_cards_action(web_game):
        # 执行一次！！！！！
        # web_game.player_session.session_messages.clear()
        await web_game.combat_pipeline.process()

    # 返回！
    return DungeonGamePlayResponse(
        client_messages=[],
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _handle_advance_next_dungeon(web_game: TCGGame) -> DungeonGamePlayResponse:
    """处理前进下一个地下城"""
    if not web_game.current_combat_sequence.is_waiting:
        logger.error(f"not web_game.current_engagement.is_post_wait_phase")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="not web_game.current_engagement.is_post_wait_phase",
        )

    if web_game.current_combat_sequence.hero_won:
        next_level = web_game.current_dungeon.peek_next_stage()
        if next_level is None:
            logger.info("没有下一关，你胜利了，应该返回营地！！！！")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="没有下一关，你胜利了，应该返回营地！！！！",
            )
        else:
            # web_game.next_dungeon()
            advance_to_next_stage(web_game)
            return DungeonGamePlayResponse(
                client_messages=[],
            )
    elif web_game.current_combat_sequence.hero_lost:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="你已经失败了，不能继续进行游戏",
        )

    # 如果既没有胜利也没有失败，这种情况应该不会发生，但为了安全起见
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="战斗状态异常",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/gameplay/v1/", response_model=DungeonGamePlayResponse
)
async def dungeon_gameplay(
    payload: DungeonGamePlayRequest,
    game_server: GameServerInstance,
) -> DungeonGamePlayResponse:

    logger.info(f"/dungeon/gameplay/v1/: {payload.model_dump_json()}")
    try:
        # 验证地下城操作的前置条件
        web_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 处理逻辑
        match payload.user_input.tag:
            case "dungeon_combat_kick_off":
                return await _handle_dungeon_combat_kick_off(web_game)

            # case "dungeon_combat_complete":
            #     return await _handle_dungeon_combat_complete(web_game)

            case "draw_cards":
                return await _handle_draw_cards(web_game)

            case "play_cards":
                return await _handle_play_cards(web_game, payload)

            # case "x_card":
            #     return await _handle_x_card(web_game, payload)

            case "advance_next_dungeon":
                return await _handle_advance_next_dungeon(web_game)

            case _:
                logger.error(f"未知的请求类型 = {payload.user_input.tag}, 不能处理！")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"未知的请求类型 = {payload.user_input.tag}, 不能处理！",
                )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发生错误: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################


@dungeon_gameplay_api_router.post(
    path="/api/dungeon/trans_home/v1/", response_model=DungeonTransHomeResponse
)
async def dungeon_trans_home(
    payload: DungeonTransHomeRequest,
    game_server: GameServerInstance,
) -> DungeonTransHomeResponse:

    logger.info(f"/dungeon/trans_home/v1/: {payload.model_dump_json()}")
    try:
        # 验证地下城操作的前置条件
        web_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        if not web_game.current_combat_sequence.is_waiting:
            logger.error(f"not web_game.current_engagement.is_post_wait_phase:")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能在战斗结束后回家",
            )

        # 回家
        # web_game.return_home()
        _all_heros_return_home(web_game)
        return DungeonTransHomeResponse(
            message="回家了",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发生错误: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
