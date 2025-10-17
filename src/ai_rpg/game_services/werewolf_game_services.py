from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from ..game_services.game_server import GameServerInstance
from ..models import (
    WerewolfGameStartRequest,
    WerewolfGameStartResponse,
    WerewolfGamePlayRequest,
    WerewolfGamePlayResponse,
    WerewolfGameStateResponse,
    World,
    WerewolfGameActorDetailsResponse,
    EntitySerialization,
    World,
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    NightKillTargetComponent,
    DeathComponent,
    DayDiscussedComponent,
    NightActionReadyComponent,
    DayVotedComponent,
)
from ..demo.werewolf_game_world import create_demo_sd_game_boot
from ..game_services.game_server import GameServerInstance
from ..game.player_client import PlayerClient
from ..game.tcg_game import TCGGame
from ..settings import (
    initialize_server_settings_instance,
)
from ..chat_services import ChatClient
from ..game.config import GLOBAL_SD_GAME_NAME
from typing import List, Set
from ..entitas import Entity, Matcher
from ..game_systems.werewolf_day_vote_system import WerewolfDayVoteSystem

###################################################################################################################################################################
werewolf_game_api_router = APIRouter()


###############################################################################################################################################
def announce_night_phase(tcg_game: TCGGame) -> None:
    """
    宣布夜晚阶段开始,并进行夜晚阶段的初始化工作:
    1. 向所有存活玩家宣布进入夜晚
    2. 清理上一个白天阶段的标记(讨论和投票组件)
    """

    # 验证当前回合计数器是否处于夜晚阶段
    # 回合计数器规则: 0=游戏开始, 1=第一夜, 2=第一白天, 3=第二夜, 4=第二白天...
    # 夜晚阶段的特征: 计数器为奇数(1,3,5...)
    assert (
        tcg_game._werewolf_game_turn_counter % 2 == 1
        or tcg_game._werewolf_game_turn_counter > 0
    ), "当前时间标记不是夜晚"

    logger.warning(f"进入夜晚,时间标记 = {tcg_game._werewolf_game_turn_counter}")

    # 获取所有角色玩家(狼人、预言家、女巫、村民)
    all_role_players = tcg_game.get_group(
        Matcher(
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
                VillagerComponent,
            ],
        )
    ).entities.copy()

    # 计算当前是第几个夜晚(从1开始计数)
    current_night_number = (tcg_game._werewolf_game_turn_counter + 1) // 2

    # 向所有玩家发送夜晚开始的消息
    for player in all_role_players:
        tcg_game.append_human_message(
            player, f"# 注意!天黑请闭眼!这是第 {current_night_number} 个夜晚"
        )

    # 清理白天阶段的标记组件
    # 获取所有带有白天讨论或投票标记的玩家
    players_with_day_markers = tcg_game.get_group(
        Matcher(
            any_of=[DayDiscussedComponent, DayVotedComponent, NightKillTargetComponent],
        )
    ).entities.copy()

    # 移除这些玩家身上的白天阶段标记
    for player in players_with_day_markers:

        # 前一个白天的讨论标记，进入新的夜晚也要清理掉
        if player.has(DayDiscussedComponent):
            player.remove(DayDiscussedComponent)

        # 前一个白天的投票标记，进入新的夜晚也要清理掉
        if player.has(DayVotedComponent):
            player.remove(DayVotedComponent)

        # 前一天晚上的击杀标记，进入新的夜晚也要清理掉
        if player.has(NightKillTargetComponent):
            player.remove(NightKillTargetComponent)


###############################################################################################################################################
def announce_day_phase(tcg_game: TCGGame) -> None:
    """
    宣布白天阶段开始,并进行白天阶段的初始化工作:
    1. 向所有存活玩家宣布进入白天
    2. 公布昨夜死亡的玩家信息
    3. 处理被杀玩家的状态转换(从夜晚击杀标记转为死亡状态)
    4. 清理夜晚阶段的计划标记
    """

    # 验证当前回合计数器是否处于白天阶段
    # 回合计数器规则: 0=游戏开始, 1=第一夜, 2=第一白天, 3=第二夜, 4=第二白天...
    # 白天阶段的特征: 计数器为偶数且大于0(2,4,6...)
    assert (
        tcg_game._werewolf_game_turn_counter % 2 == 0
        and tcg_game._werewolf_game_turn_counter > 0
    ), "当前时间标记不是白天"

    logger.warning(f"进入白天,时间标记 = {tcg_game._werewolf_game_turn_counter}")

    # 获取所有角色玩家(狼人、预言家、女巫、村民)
    all_role_players = tcg_game.get_group(
        Matcher(
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
                VillagerComponent,
            ],
        )
    ).entities.copy()

    # 计算当前是第几个白天(从1开始计数)
    current_day_number = tcg_game._werewolf_game_turn_counter // 2

    # 向所有玩家发送白天开始的消息
    for player in all_role_players:
        tcg_game.append_human_message(
            player, f"# 注意!天亮请睁眼!这是第 {current_day_number} 个白天"
        )

    # 获取所有在昨夜被标记为击杀的玩家
    players_killed_last_night = tcg_game.get_group(
        Matcher(
            all_of=[NightKillTargetComponent],
        )
    ).entities.copy()

    # 公布昨夜死亡信息
    if players_killed_last_night:
        # 格式化死亡玩家列表信息
        death_announcement = ", ".join(
            f"{player.name}(被杀害)" for player in players_killed_last_night
        )
        logger.info(f"在夜晚,以下玩家被杀害: {death_announcement}")

        # 向所有玩家广播死亡信息
        for player in all_role_players:
            tcg_game.append_human_message(
                player, f"# 昨晚被杀害的玩家有: {death_announcement}"
            )
    else:
        # 平安夜,无人死亡
        logger.info("在夜晚,没有玩家被杀害")
        for player in all_role_players:
            tcg_game.append_human_message(player, f"# 昨晚没有玩家被杀害,平安夜")

    # 处理被杀玩家的状态转换
    for killed_player in players_killed_last_night:
        # 添加正式的死亡状态标记
        logger.info(
            f"玩家 {killed_player.name} 在第 {current_day_number} 个白天 被标记为死亡状态, 昨夜因为某种原因被杀害"
        )
        killed_player.replace(DeathComponent, killed_player.name)

    # 清理夜晚阶段的计划标记组件
    # 获取所有带有夜晚计划标记的实体
    entities_with_night_plans = tcg_game.get_group(
        Matcher(
            all_of=[NightActionReadyComponent],
        )
    ).entities.copy()

    # 移除所有夜晚计划标记,为新的一天做准备
    for entity_with_plan in entities_with_night_plans:
        entity_with_plan.remove(NightActionReadyComponent)


###################################################################################################################################################################
@werewolf_game_api_router.post(
    path="/api/werewolf/start/v1/", response_model=WerewolfGameStartResponse
)
async def start_werewolf_game(
    request_data: WerewolfGameStartRequest,
    game_server: GameServerInstance,
) -> WerewolfGameStartResponse:

    logger.info(f"Starting werewolf game: {request_data.model_dump_json()}")

    # 先检查房间是否存在，存在就删除旧房间
    if game_server.has_room(request_data.user_name):

        logger.debug(f"start/v1: {request_data.user_name} room exists, removing it")

        pre_room = game_server.get_room(request_data.user_name)
        assert pre_room is not None

        game_server.remove_room(pre_room)

    assert not game_server.has_room(
        request_data.user_name
    ), "Room should have been removed."

    # 然后创建一个新的房间
    new_room = game_server.create_room(
        user_name=request_data.user_name,
    )
    logger.info(
        f"start/v1: {request_data.user_name} create room = {new_room._username}"
    )
    assert new_room._game is None

    # 创建boot数据
    assert GLOBAL_SD_GAME_NAME == request_data.game_name, "目前只支持 SD 游戏"
    world_boot = create_demo_sd_game_boot(request_data.game_name)
    assert world_boot is not None, "WorldBoot 创建失败"

    # 创建游戏实例
    new_room._game = terminal_game = TCGGame(
        name=request_data.game_name,
        player_client=PlayerClient(
            name=request_data.user_name, actor="角色.主持人"  # 写死先！
        ),
        world=World(boot=world_boot),
    )

    # 创建服务器相关的连接信息。
    server_settings = initialize_server_settings_instance(Path("server_settings.json"))
    ChatClient.initialize_url_config(server_settings)

    # 新游戏！
    terminal_game.new_game().save()

    # 测试一下玩家控制角色，如果没有就是错误。
    assert terminal_game.get_player_entity() is not None, "玩家实体不存在"

    # 初始化!
    await terminal_game.initialize()

    # 在这里添加启动游戏的逻辑
    return WerewolfGameStartResponse(
        message=terminal_game.world.model_dump_json(indent=2)
    )


###################################################################################################################################################################


@werewolf_game_api_router.post(
    path="/api/werewolf/gameplay/v1/", response_model=WerewolfGamePlayResponse
)
async def play_werewolf_game(
    request_data: WerewolfGamePlayRequest,
    game_server: GameServerInstance,
) -> WerewolfGamePlayResponse:
    logger.info(f"Playing werewolf game: {request_data.model_dump_json()}")

    try:

        # 是否有房间？！！
        if not game_server.has_room(user_name=request_data.user_name):
            logger.error(f"{request_data.user_name} has no room, please login first.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有登录，请先登录",
            )

        # 是否有游戏？！！
        current_room = game_server.get_room(user_name=request_data.user_name)
        assert current_room is not None
        if current_room._game is None:
            logger.error(f"{request_data.user_name} has no game, please login first.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏，请先登录",
            )

        user_input = request_data.data.get("user_input", "")
        logger.info(f"{request_data.user_name} user_input: {user_input}")

        web_game = current_room._game

        if user_input == "/k" or user_input == "/kickoff":

            if web_game._werewolf_game_turn_counter == 0:

                logger.info("游戏开始，准备入场记阶段！！！！！！")

                # 清理之前的消息
                web_game.player_client.clear_messages()

                # 初始化游戏的开场流程
                await web_game.werewolf_game_kickoff_pipeline.process()

                # 返回当前的客户端消息
                return WerewolfGamePlayResponse(
                    client_messages=web_game.player_client.client_messages
                )

            else:
                logger.error(
                    f"当前时间标记不是0，是{web_game._werewolf_game_turn_counter}，不能执行 /kickoff 命令"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="游戏已经开始，不能重复执行 /kickoff 命令",
                )

        if user_input == "/t" or user_input == "/time":

            last = web_game._werewolf_game_turn_counter
            web_game._werewolf_game_turn_counter += 1
            logger.info(
                f"时间推进了一步，{last} -> {web_game._werewolf_game_turn_counter}"
            )

            # 判断是夜晚还是白天
            if web_game._werewolf_game_turn_counter % 2 == 1:

                # 进入下一个夜晚
                announce_night_phase(web_game)

            else:
                # 进入下一个白天
                announce_day_phase(web_game)

            # 返回！
            return WerewolfGamePlayResponse(client_messages=[])

        if user_input == "/n" or user_input == "/night":

            # 如果是夜晚
            if web_game._werewolf_game_turn_counter % 2 == 1:

                # 清除之前的消息
                web_game.player_client.clear_messages()

                # 运行游戏逻辑
                await web_game.werewolf_game_night_pipeline.process()

                #
                return WerewolfGamePlayResponse(
                    client_messages=web_game.player_client.client_messages
                )

            else:

                logger.error(
                    f"当前不是夜晚，是{web_game._werewolf_game_turn_counter}，不能执行 /night 命令"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="当前不是夜晚，不能执行 /night 命令",
                )

        if user_input == "/d" or user_input == "/day":

            # 如果是白天
            if (
                web_game._werewolf_game_turn_counter % 2 == 0
                and web_game._werewolf_game_turn_counter > 0
            ):
                # 清理之前的消息
                web_game.player_client.clear_messages()
                # 运行游戏逻辑
                await web_game.werewolf_game_day_pipeline.process()

                return WerewolfGamePlayResponse(
                    client_messages=web_game.player_client.client_messages
                )

            else:

                logger.error(
                    f"当前不是白天，是{web_game._werewolf_game_turn_counter}，不能执行 /day 命令"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="当前不是白天，不能执行 /day 命令",
                )

        if user_input == "/v" or user_input == "/vote":

            # 如果是白天
            if (
                web_game._werewolf_game_turn_counter % 2 == 0
                and web_game._werewolf_game_turn_counter > 0
            ):

                # 判断是否讨论完毕
                if WerewolfDayVoteSystem.is_day_discussion_complete(web_game):

                    # 清理之前的消息
                    web_game.player_client.clear_messages()

                    # 如果讨论完毕，则进入投票环节
                    await web_game.werewolf_game_vote_pipeline.process()

                    return WerewolfGamePlayResponse(
                        client_messages=web_game.player_client.client_messages
                    )

                else:

                    logger.error(
                        "白天讨论环节没有完成，不能进入投票阶段！！！！！！！！！！！！"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="白天讨论环节没有完成，不能进入投票阶段",
                    )
            else:

                logger.error(
                    f"当前不是白天，是{web_game._werewolf_game_turn_counter}，不能执行 /vote 命令"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="当前不是白天，不能执行 /vote 命令",
                )

        logger.error(f"未知命令: {user_input}, 什么都没做")
        return WerewolfGamePlayResponse(client_messages=[])

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"home/gameplay/v1: {request_data.user_name} failed, error: {str(e)}",
        )


###################################################################################################################################################################


@werewolf_game_api_router.get(
    path="/api/werewolf/state/v1/{user_name}/{game_name}/state",
    response_model=WerewolfGameStateResponse,
)
async def get_werewolf_game_state(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
) -> WerewolfGameStateResponse:
    logger.info(f"Getting werewolf game state for user: {user_name}, game: {game_name}")

    try:

        # 是否有房间？！！
        if not game_server.has_room(user_name):
            # logger.error(f"view_home: {user_name} has no room")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有房间",
            )

        # 是否有游戏？！！
        current_room = game_server.get_room(user_name)
        assert current_room is not None
        if current_room._game is None:
            # logger.error(f"view_home: {user_name} has no game")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏",
            )

        # 获取当前地图
        mapping_data = current_room._game.get_stage_actor_distribution_mapping()
        logger.info(
            f"view_home: {user_name} mapping_data: {mapping_data}, time={current_room._game._werewolf_game_turn_counter}"
        )

        # 返回。
        return WerewolfGameStateResponse(
            mapping=mapping_data,
            game_time=current_room._game._werewolf_game_turn_counter,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器错误: {str(e)}",
        )


###################################################################################################################################################################


@werewolf_game_api_router.get(
    path="/api/werewolf/actors/v1/{user_name}/{game_name}/details",
    response_model=WerewolfGameActorDetailsResponse,
)
async def get_werewolf_actors_details(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
    actor_names: List[str] = Query(..., alias="actors"),
) -> WerewolfGameActorDetailsResponse:

    logger.info(
        f"/werewolf/actors/v1/{user_name}/{game_name}/details: {user_name}, {game_name}, {actor_names}"
    )

    try:

        # 是否有房间？！！
        if not game_server.has_room(user_name):
            logger.error(f"view_actor: {user_name} has no room")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有房间",
            )

        # 是否有游戏？！！
        current_room = game_server.get_room(user_name)
        assert current_room is not None
        if current_room._game is None:
            logger.error(f"view_actor: {user_name} has no game")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏",
            )

        if len(actor_names) == 0 or actor_names[0] == "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供至少一个角色名称",
            )

        # 获取所有角色实体
        entities_serialization: List[EntitySerialization] = []

        # 获取指定角色实体
        actor_entities: Set[Entity] = set()

        for actor_name in actor_names:
            # 获取角色实体
            actor_entity = current_room._game.get_entity_by_name(actor_name)
            if actor_entity is None:
                logger.error(f"view_actor: {user_name} actor {actor_name} not found.")
                continue

            # 添加到集合中
            actor_entities.add(actor_entity)

        # 序列化角色实体
        entities_serialization = current_room._game.serialize_entities(actor_entities)

        # 返回!
        return WerewolfGameActorDetailsResponse(
            actor_entities_serialization=entities_serialization,
            # agent_short_term_memories=[],  # 太长了，先注释掉
        )
    except Exception as e:
        logger.error(f"get_actors_details: {user_name} error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器错误: {str(e)}",
        )


###################################################################################################################################################################
