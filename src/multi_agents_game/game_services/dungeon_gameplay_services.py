from fastapi import APIRouter, HTTPException, status
from loguru import logger

from ..game.tcg_game import TCGGameState
from ..game.web_tcg_game import WebTCGGame
from ..game_services.game_server import GameServerInstance
from ..models import (
    DungeonGamePlayRequest,
    DungeonGamePlayResponse,
    DungeonTransHomeRequest,
    DungeonTransHomeResponse,
    Skill,
    XCardPlayerComponent,
)

###################################################################################################################################################################
dungeon_gameplay_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _execute_web_game(web_game: WebTCGGame) -> None:
    assert web_game.player.name != ""
    web_game.player.archive_and_clear_messages()
    await web_game.run()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_router.post(
    path="/dungeon/gameplay/v1/", response_model=DungeonGamePlayResponse
)
async def dungeon_gameplay(
    request_data: DungeonGamePlayRequest,
    game_server: GameServerInstance,
) -> DungeonGamePlayResponse:

    logger.info(f"/dungeon/gameplay/v1/: {request_data.model_dump_json()}")
    try:

        # 是否有房间？！！
        room_manager = game_server.room_manager
        if not room_manager.has_room(request_data.user_name):
            logger.error(
                f"dungeon_run: {request_data.user_name} has no room, please login first."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有登录，请先登录",
            )

        # 是否有游戏？！！
        current_room = room_manager.get_room(request_data.user_name)
        assert current_room is not None
        if current_room.game is None:
            logger.error(
                f"dungeon_run: {request_data.user_name} has no game, please login first."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏，请先登录",
            )

        # 是否是WebTCGGame？！！
        web_game = current_room.game
        assert isinstance(web_game, WebTCGGame)
        assert web_game is not None

        # 判断游戏状态，不是DUNGEON状态不可以推进。
        if web_game.current_game_state != TCGGameState.DUNGEON:
            logger.error(
                f"dungeon_run: {request_data.user_name} game state error = {web_game.current_game_state}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能在地下城状态下使用",
            )

        # 判断是否有战斗
        if len(web_game.current_engagement.combats) == 0:
            logger.error(f"len(web_game.current_engagement.combats) == 0")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有战斗可以进行",
            )

        # 处理逻辑
        match request_data.user_input.tag:

            case "dungeon_combat_kick_off":

                if not web_game.current_engagement.is_kickoff_phase:
                    logger.error(f"not web_game.current_engagement.is_kickoff_phase")
                    # return DungeonGamePlayResponse(
                    #     error=1006,
                    #     message="not web_game.current_engagement.is_kickoff_phase",
                    # )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="not web_game.current_engagement.is_kickoff_phase",
                    )

                # 推进一次游戏, 即可转换ONGOING状态。
                await _execute_web_game(web_game)
                # 返回！
                return DungeonGamePlayResponse(
                    client_messages=web_game.player.client_messages,
                    # error=0,
                    # message="",
                )

            case "dungeon_combat_complete":

                if not web_game.current_engagement.is_complete_phase:
                    logger.error(f"not web_game.current_engagement.is_complete_phase")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="not web_game.current_engagement.is_complete_phase",
                    )

                # 推进一次游戏, 即可转换ONGOING状态。
                await _execute_web_game(web_game)
                # 返回！
                return DungeonGamePlayResponse(
                    client_messages=web_game.player.client_messages,
                )

            case "draw_cards":

                if not web_game.current_engagement.is_on_going_phase:
                    logger.error(f"not web_game.current_engagement.is_on_going_phase")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="not web_game.current_engagement.is_on_going_phase",
                    )

                # 推进一次游戏, 即可抽牌。
                web_game.activate_draw_cards_action()
                await _execute_web_game(web_game)

                # 返回！
                return DungeonGamePlayResponse(
                    client_messages=web_game.player.client_messages,
                )

            case "play_cards":

                if not web_game.current_engagement.is_on_going_phase:
                    logger.error(f"not web_game.current_engagement.is_on_going_phase")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="not web_game.current_engagement.is_on_going_phase",
                    )

                logger.debug(
                    f"玩家输入 = {request_data.user_input.tag}, 准备行动......"
                )
                if web_game.execute_play_card():
                    # 执行一次！！！！！
                    await _execute_web_game(web_game)

                # 返回！
                return DungeonGamePlayResponse(
                    client_messages=web_game.player.client_messages,
                )

            case "x_card":

                if not web_game.current_engagement.is_on_going_phase:
                    logger.error(f"not web_game.current_engagement.is_on_going_phase")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="not web_game.current_engagement.is_on_going_phase",
                    )

                # TODO, 先写死默认往上面加。
                player_entity = web_game.get_player_entity()
                assert player_entity is not None
                logger.debug(
                    f"玩家输入 x_card = \n{request_data.user_input.model_dump_json()}"
                )
                skill_name = request_data.user_input.data.get("name", "")
                skill_description = request_data.user_input.data.get("description", "")
                skill_effect = request_data.user_input.data.get("effect", "")
                if skill_name != "" and skill_description != "" and skill_effect != "":
                    player_entity.replace(
                        XCardPlayerComponent,
                        player_entity._name,
                        Skill(
                            name=skill_name,
                            description=skill_description,
                            effect=skill_effect,
                        ),
                    )

                    return DungeonGamePlayResponse(
                        client_messages=web_game.player.client_messages,
                    )

                else:

                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"技能名称错误: {player_entity._name}, Response = \n{request_data.user_input.data}",
                    )

            case "advance_next_dungeon":

                if not web_game.current_engagement.is_post_wait_phase:
                    logger.error(f"not web_game.current_engagement.is_post_wait_phase")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="not web_game.current_engagement.is_post_wait_phase",
                    )

                if web_game.current_engagement.has_hero_won:
                    next_level = web_game.current_dungeon.next_level()
                    if next_level is None:
                        logger.info("没有下一关，你胜利了，应该返回营地！！！！")
                        raise HTTPException(
                            status_code=status.HTTP_200_OK,
                            detail="没有下一关，你胜利了，应该返回营地！！！！",
                        )
                    else:
                        web_game.advance_next_dungeon()
                        return DungeonGamePlayResponse(
                            client_messages=[],
                        )
                elif web_game.current_engagement.has_hero_lost:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="你已经失败了，不能继续进行游戏",
                    )
            case _:
                logger.error(
                    f"未知的请求类型 = {request_data.user_input.tag}, 不能处理！"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"未知的请求类型 = {request_data.user_input.tag}, 不能处理！",
                )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{request_data.user_input} 是错误的输入，造成无法处理的情况！",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发生错误: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################


@dungeon_gameplay_router.post(
    path="/dungeon/trans_home/v1/", response_model=DungeonTransHomeResponse
)
async def dungeon_trans_home(
    request_data: DungeonTransHomeRequest,
    game_server: GameServerInstance,
) -> DungeonTransHomeResponse:

    logger.info(f"/dungeon/trans_home/v1/: {request_data.model_dump_json()}")
    try:

        # 是否有房间？！！
        room_manager = game_server.room_manager
        if not room_manager.has_room(request_data.user_name):
            logger.error(
                f"dungeon_trans_home: {request_data.user_name} has no room, please login first."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有登录，请先登录",
            )

        # 是否有游戏？！！
        current_room = room_manager.get_room(request_data.user_name)
        assert current_room is not None
        if current_room.game is None:
            logger.error(
                f"dungeon_trans_home: {request_data.user_name} has no game, please login first."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏，请先登录",
            )

        # 是否是WebTCGGame？！！
        web_game = current_room.game
        assert isinstance(web_game, WebTCGGame)
        assert web_game is not None

        # 判断游戏状态，不是DUNGEON状态不可以推进。
        if web_game.current_game_state != TCGGameState.DUNGEON:
            logger.error(
                f"dungeon_trans_home: {request_data.user_name} game state error = {web_game.current_game_state}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能在地下城状态下使用",
            )

        # 判断是否有战斗
        if len(web_game.current_engagement.combats) == 0:
            logger.error(f"len(web_game.current_engagement.combats) == 0")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有战斗可以回家",
            )

        if not web_game.current_engagement.is_post_wait_phase:
            logger.error(f"not web_game.current_engagement.is_post_wait_phase:")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能在战斗结束后回家",
            )

        # 回家
        web_game.return_to_home()
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
