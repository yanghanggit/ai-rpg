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
    NightActionCompletedComponent,
    DayVotedComponent,
)
from ..demo.werewolf_game_world import create_demo_sd_game_boot
from ..game_services.game_server import GameServerInstance
from ..game.player_session import PlayerSession
from ..game.sdg_game import SDGGame
from ..settings import (
    initialize_server_settings_instance,
)
from ..chat_services import ChatClient
from ..game.config import GLOBAL_SD_GAME_NAME
from typing import List, Set, Dict, cast, Any, final
from ..entitas import Entity, Matcher
from typing_extensions import TypedDict
from enum import IntEnum, unique


###################################################################################################################################################################
class PhaseChangeNotification(TypedDict):
    phase: str
    turn_number: int


###################################################################################################################################################################
werewolf_game_api_router = APIRouter()


###############################################################################################################################################
def announce_night_phase(sd_game: SDGGame) -> None:
    """
    宣布夜晚阶段开始,并进行夜晚阶段的初始化工作:
    1. 向所有存活玩家宣布进入夜晚
    2. 清理上一个白天阶段的标记(讨论和投票组件)
    """

    # 验证当前回合计数器是否处于夜晚阶段
    # 回合计数器规则: 0=游戏开始, 1=第一夜, 2=第一白天, 3=第二夜, 4=第二白天...
    # 夜晚阶段的特征: 计数器为奇数(1,3,5...)
    assert (
        sd_game._turn_counter % 2 == 1 or sd_game._turn_counter > 0
    ), "当前时间标记不是夜晚"

    logger.warning(f"进入夜晚,时间标记 = {sd_game._turn_counter}")

    # 获取所有角色玩家(狼人、预言家、女巫、村民)
    all_role_players = sd_game.get_group(
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
    current_night_number = (sd_game._turn_counter + 1) // 2

    # 向所有玩家发送夜晚开始的消息
    for player in all_role_players:
        sd_game.append_human_message(
            player, f"# 注意!天黑请闭眼!这是第 {current_night_number} 个夜晚"
        )

    # 清理白天阶段的标记组件
    # 获取所有带有白天讨论或投票标记的玩家
    players_with_day_markers = sd_game.get_group(
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

    # 通知客户端一个消息，夜晚阶段开始了
    notification = PhaseChangeNotification(
        phase="night", turn_number=current_night_number
    )
    sd_game.player_session.add_game_message(cast(Dict[str, Any], notification))


###############################################################################################################################################
def announce_day_phase(sd_game: SDGGame) -> None:
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
        sd_game._turn_counter % 2 == 0 and sd_game._turn_counter > 0
    ), "当前时间标记不是白天"

    logger.warning(f"进入白天,时间标记 = {sd_game._turn_counter}")

    # 获取所有角色玩家(狼人、预言家、女巫、村民)
    all_role_players = sd_game.get_group(
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
    current_day_number = sd_game._turn_counter // 2

    # 向所有玩家发送白天开始的消息
    for player in all_role_players:
        sd_game.append_human_message(
            player, f"# 注意!天亮请睁眼!这是第 {current_day_number} 个白天"
        )

    # 获取所有在昨夜被标记为击杀的玩家
    players_killed_last_night = sd_game.get_group(
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
            sd_game.append_human_message(
                player, f"# 昨晚被杀害的玩家有: {death_announcement}"
            )
    else:
        # 平安夜,无人死亡
        logger.info("在夜晚,没有玩家被杀害")
        for player in all_role_players:
            sd_game.append_human_message(player, f"# 昨晚没有玩家被杀害,平安夜")

    # 处理被杀玩家的状态转换
    for killed_player in players_killed_last_night:
        # 添加正式的死亡状态标记
        logger.info(
            f"玩家 {killed_player.name} 在第 {current_day_number} 个白天 被标记为死亡状态, 昨夜因为某种原因被杀害"
        )
        killed_player.replace(DeathComponent, killed_player.name)

    # 清理夜晚阶段的计划标记组件
    # 获取所有带有夜晚计划标记的实体
    entities_with_night_plans = sd_game.get_group(
        Matcher(
            any_of=[NightActionReadyComponent, NightActionCompletedComponent],
        )
    ).entities.copy()

    # 移除所有夜晚计划标记,为新的一天做准备
    for entity_with_plan in entities_with_night_plans:

        # 移除夜晚行动准备标记
        if entity_with_plan.has(NightActionReadyComponent):
            entity_with_plan.remove(NightActionReadyComponent)

        # 移除夜晚行动完成标记
        if entity_with_plan.has(NightActionCompletedComponent):
            entity_with_plan.remove(NightActionCompletedComponent)

    # 通知客户端一个消息，白天阶段开始了
    notification = PhaseChangeNotification(phase="day", turn_number=current_day_number)
    sd_game.player_session.add_game_message(
        cast(
            Dict[str, Any],
            notification,
        )
    )


###################################################################################################################################################################
def is_night_phase_completed(sd_game: SDGGame) -> bool:
    """
    检查夜晚阶段是否已经结束

    Args:
        sd_game: 游戏实例

    Returns:
        bool: 如果夜晚阶段已经结束返回True，否则返回False
    """

    assert sd_game._turn_counter % 2 == 1, "当前时间标记不是夜晚!!!!!"
    assert sd_game._started, "游戏还没有开始!!!!!"

    entities1 = sd_game.get_group(
        Matcher(
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
            ],
            none_of=[DeathComponent],
        )
    ).entities.copy()

    entities2 = sd_game.get_group(
        Matcher(
            all_of=[NightActionCompletedComponent],
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
            ],
            none_of=[DeathComponent],
        )
    ).entities.copy()

    return len(entities1) > 0 and len(entities2) >= len(entities1)


###################################################################################################################################################################
def is_day_phase_completed(sd_game: SDGGame) -> bool:
    """
    检查白天阶段是否已经结束（白天投票完毕就是结束）

    Args:
        sd_game: 游戏实例

    Returns:
        bool: 如果白天阶段已经结束返回True，否则返回False
    """
    # TODO: 实现白天结束的判断逻辑（投票完毕即为结束）
    assert (
        sd_game._turn_counter % 2 == 0 and sd_game._turn_counter > 0
    ), "当前时间标记不是白天!!!!!"
    assert sd_game._started, "游戏还没有开始!!!!!"

    if not is_day_discussion_complete(sd_game):
        return False

    if not is_day_vote_complete(sd_game):
        return False

    return True


###################################################################################################################################################################
# 判断村民阵营胜利：所有狼人都被淘汰且至少有一个村民存活
def check_town_victory(sd_game: SDGGame) -> bool:
    dead_werewolves = sd_game.get_group(
        Matcher(
            all_of=[WerewolfComponent, DeathComponent],
        )
    ).entities.copy()

    total_werewolves = sd_game.get_group(
        Matcher(
            all_of=[WerewolfComponent],
        )
    ).entities.copy()

    alive_town = sd_game.get_group(
        Matcher(
            any_of=[
                VillagerComponent,
                SeerComponent,
                WitchComponent,
            ],
            none_of=[DeathComponent],
        )
    ).entities.copy()

    # 村民胜利条件：所有狼人都死亡 且 至少有一个村民存活
    return len(alive_town) > 0 and len(dead_werewolves) >= len(total_werewolves)


################################################################################################################################################
# 判断狼人阵营胜利：狼人数量大于等于村民数量且至少有一个狼人存活
def check_werewolves_victory(sd_game: SDGGame) -> bool:

    town_entities = sd_game.get_group(
        Matcher(
            any_of=[
                VillagerComponent,
                SeerComponent,
                WitchComponent,
            ],
            none_of=[DeathComponent],
        )
    ).entities.copy()

    wolf_entities = sd_game.get_group(
        Matcher(
            all_of=[WerewolfComponent],
            none_of=[DeathComponent],
        )
    ).entities.copy()

    # 狼人胜利条件：狼人数量 >= 村民数量 且 至少有一个狼人存活
    return len(town_entities) <= len(wolf_entities) and len(wolf_entities) > 0


###################################################################################################################################################################
@final
@unique
class VictoryCondition(IntEnum):
    NONE = (0,)  # 无结果
    TOWN_VICTORY = (1,)  # 村民阵营胜利
    WEREWOLVES_VICTORY = (2,)  # 狼人阵营胜利


###################################################################################################################################################################
def check_victory_conditions(sd_game: SDGGame) -> VictoryCondition:
    """
    检查游戏是否达成胜利条件

    Args:
        sd_game: 游戏实例

    Returns:
        bool: 如果达成胜利条件返回True，否则返回False
    """
    town_victory = check_town_victory(sd_game)
    if town_victory:
        return VictoryCondition.TOWN_VICTORY

    werewolves_victory = check_werewolves_victory(sd_game)
    if werewolves_victory:
        return VictoryCondition.WEREWOLVES_VICTORY

    return VictoryCondition.NONE


###################################################################################################################################################################
def is_day_discussion_complete(game: SDGGame) -> bool:
    entities1 = game.get_group(
        Matcher(
            all_of=[DayDiscussedComponent],
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
                VillagerComponent,
            ],
        )
    ).entities.copy()

    entities2 = game.get_group(
        Matcher(
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
                VillagerComponent,
            ],
            none_of=[DeathComponent],
        )
    ).entities.copy()

    logger.info(
        f"讨论完成标记玩家数量: {len(entities1)} / 存活玩家数量: {len(entities2)}"
    )

    return len(entities1) > 0 and len(entities1) >= len(entities2)


###################################################################################################################################################################
def is_day_vote_complete(game: SDGGame) -> bool:
    entities1 = game.get_group(
        Matcher(
            all_of=[DayVotedComponent],
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
                VillagerComponent,
            ],
        )
    ).entities.copy()

    entities2 = game.get_group(
        Matcher(
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
                VillagerComponent,
            ],
            none_of=[DeathComponent],
        )
    ).entities.copy()

    logger.info(
        f"投票完成标记玩家数量: {len(entities1)} / 存活玩家数量: {len(entities2)}"
    )

    return len(entities1) > 0 and len(entities1) >= len(entities2)


###################################################################################################################################################################
@werewolf_game_api_router.post(
    path="/api/werewolf/start/v1/", response_model=WerewolfGameStartResponse
)
async def start_werewolf_game(
    payload: WerewolfGameStartRequest,
    game_server: GameServerInstance,
) -> WerewolfGameStartResponse:

    logger.info(f"Starting werewolf game: {payload.model_dump_json()}")

    # 先检查房间是否存在，存在就删除旧房间
    if game_server.has_room(payload.user_name):

        logger.debug(f"start/v1: {payload.user_name} room exists, removing it")

        pre_room = game_server.get_room(payload.user_name)
        assert pre_room is not None

        if pre_room._sdg_game is not None:
            logger.debug(f"start/v1: {payload.user_name} removing old game instance")

            # 保存并退出旧游戏
            pre_room._sdg_game.save()
            pre_room._sdg_game.exit()

            pre_room._sdg_game = None  # 先断开引用，等待垃圾回收

        game_server.remove_room(pre_room)

    assert not game_server.has_room(payload.user_name), "Room should have been removed."

    # 然后创建一个新的房间
    new_room = game_server.create_room(
        user_name=payload.user_name,
    )
    logger.info(f"start/v1: {payload.user_name} create room = {new_room._username}")
    assert new_room._sdg_game is None

    # 创建boot数据
    assert GLOBAL_SD_GAME_NAME == payload.game_name, "目前只支持 SD 游戏"
    world_boot = create_demo_sd_game_boot(payload.game_name)
    assert world_boot is not None, "WorldBoot 创建失败"

    # 创建游戏实例
    new_room._sdg_game = web_game = SDGGame(
        name=payload.game_name,
        player_session=PlayerSession(
            name=payload.user_name, actor="角色.主持人"  # 写死先！
        ),
        world=World(boot=world_boot),
    )

    # 创建服务器相关的连接信息。
    server_settings = initialize_server_settings_instance(Path("server_settings.json"))
    ChatClient.initialize_url_config(server_settings)

    # 新游戏！
    web_game.new_game().save()

    # 测试一下玩家控制角色，如果没有就是错误。
    assert web_game.get_player_entity() is not None, "玩家实体不存在"

    # 初始化!
    await web_game.initialize()

    # 在这里添加启动游戏的逻辑
    return WerewolfGameStartResponse(message=web_game.world.model_dump_json(indent=2))


###################################################################################################################################################################


@werewolf_game_api_router.post(
    path="/api/werewolf/gameplay/v1/", response_model=WerewolfGamePlayResponse
)
async def play_werewolf_game(
    payload: WerewolfGamePlayRequest,
    game_server: GameServerInstance,
) -> WerewolfGamePlayResponse:
    logger.info(f"Playing werewolf game: {payload.model_dump_json()}")

    try:

        # 是否有房间？！！
        if not game_server.has_room(user_name=payload.user_name):
            logger.error(f"{payload.user_name} has no room, please login first.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有登录，请先登录",
            )

        # 是否有游戏？！！
        current_room = game_server.get_room(user_name=payload.user_name)
        assert current_room is not None
        if current_room._sdg_game is None:
            logger.error(f"{payload.user_name} has no game, please login first.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏，请先登录",
            )

        user_input = payload.data.get("user_input", "")
        logger.info(f"{payload.user_name} user_input: {user_input}")

        # web_game = cast(SDGame, current_room._game)
        web_game = current_room._sdg_game

        if user_input == "/k" or user_input == "/kickoff":

            if web_game._turn_counter == 0:

                logger.info("游戏开始，准备入场记阶段！！！！！！")

                # 初始化游戏的开场流程
                await web_game.werewolf_game_kickoff_pipeline.process()

                # 标记游戏已经开始
                web_game._started = True

                # 返回当前的客户端消息
                return WerewolfGamePlayResponse(session_messages=[])

            else:
                logger.error(
                    f"当前时间标记不是0，是{web_game._turn_counter}，不能执行 /kickoff 命令"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="游戏已经开始，不能重复执行 /kickoff 命令",
                )

        if user_input == "/t" or user_input == "/time":

            if not web_game._started:
                logger.error("游戏还没有开始，不能执行 /time 命令")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="游戏还没有开始，不能执行 /time 命令",
                )

            if web_game._turn_counter > 0:
                # 说明不是第一夜或者第一天
                if web_game._turn_counter % 2 == 1:
                    # 当前是黑夜（奇数），需要检查夜晚阶段是否完成
                    if not is_night_phase_completed(web_game):
                        logger.error(
                            "当前夜晚阶段还没有完成，不能推进时间，请先完成夜晚阶段的所有操作"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="当前夜晚阶段还没有完成，不能推进时间，请先完成夜晚阶段的所有操作",
                        )
                elif web_game._turn_counter % 2 == 0:
                    # 当前是白天（偶数），需要检查白天阶段是否完成
                    if not is_day_phase_completed(web_game):
                        logger.error(
                            "当前白天阶段还没有完成，不能推进时间，请先完成白天阶段的所有操作"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="当前白天阶段还没有完成，不能推进时间，请先完成白天阶段的所有操作",
                        )
                else:
                    logger.error(
                        f"当前时间标记异常{web_game._turn_counter}，不能执行 /time 命令"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="当前时间标记异常，不能执行 /time 命令",
                    )

            # 推进时间。
            last = web_game._turn_counter
            web_game._turn_counter += 1
            logger.info(f"时间推进了一步，{last} -> {web_game._turn_counter}")

            # 判断是夜晚还是白天
            if web_game._turn_counter % 2 == 1:

                # 进入下一个夜晚
                announce_night_phase(web_game)

            else:

                # 进入下一个白天
                announce_day_phase(web_game)

                # 检查是否达成胜利条件，夜晚会产生击杀
                victory_condition = check_victory_conditions(web_game)
                if victory_condition != VictoryCondition.NONE:
                    logger.warning("游戏结束，触发胜利条件，准备终止游戏...")
                    # web_game.should_terminate = True
                    if victory_condition == VictoryCondition.TOWN_VICTORY:
                        logger.warning(
                            "\n!!!!!!!!!!!!!!!!!村民阵营胜利!!!!!!!!!!!!!!!!!!!\n"
                        )
                    elif victory_condition == VictoryCondition.WEREWOLVES_VICTORY:
                        logger.warning(
                            "\n!!!!!!!!!!!!!!!!!狼人阵营胜利!!!!!!!!!!!!!!!!!!!\n"
                        )

            # 返回！
            return WerewolfGamePlayResponse(session_messages=[])

        if user_input == "/n" or user_input == "/night":

            # 如果是夜晚
            if web_game._turn_counter % 2 == 1:

                # 运行游戏逻辑
                await web_game.werewolf_game_night_pipeline.process()

                # 返回！
                return WerewolfGamePlayResponse(session_messages=[])

            else:

                logger.error(
                    f"当前不是夜晚，是{web_game._turn_counter}，不能执行 /night 命令"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="当前不是夜晚，不能执行 /night 命令",
                )

        if user_input == "/d" or user_input == "/day":

            # 如果是白天
            if web_game._turn_counter % 2 == 0 and web_game._turn_counter > 0:

                # 运行游戏逻辑
                await web_game.werewolf_game_day_pipeline.process()

                # 返回！
                return WerewolfGamePlayResponse(session_messages=[])

            else:

                logger.error(
                    f"当前不是白天，是{web_game._turn_counter}，不能执行 /day 命令"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="当前不是白天，不能执行 /day 命令",
                )

        if user_input == "/v" or user_input == "/vote":

            # 如果是白天
            if web_game._turn_counter % 2 == 0 and web_game._turn_counter > 0:

                # 判断是否讨论完毕
                if is_day_discussion_complete(web_game):

                    # 如果讨论完毕，则进入投票环节
                    await web_game.werewolf_game_vote_pipeline.process()

                    # 检查是否达成胜利条件 投票会产生死亡
                    victory_condition = check_victory_conditions(web_game)
                    if victory_condition != VictoryCondition.NONE:
                        logger.warning("游戏结束，触发胜利条件，准备终止游戏...")
                        if victory_condition == VictoryCondition.TOWN_VICTORY:
                            logger.warning(
                                "\n!!!!!!!!!!!!!!!!!村民阵营胜利!!!!!!!!!!!!!!!!!!!\n"
                            )
                        elif victory_condition == VictoryCondition.WEREWOLVES_VICTORY:
                            logger.warning(
                                "\n!!!!!!!!!!!!!!!!!狼人阵营胜利!!!!!!!!!!!!!!!!!!!\n"
                            )

                    # 返回！
                    return WerewolfGamePlayResponse(session_messages=[])

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
                    f"当前不是白天，是{web_game._turn_counter}，不能执行 /vote 命令"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="当前不是白天，不能执行 /vote 命令",
                )

        logger.error(f"未知命令: {user_input}, 什么都没做")
        return WerewolfGamePlayResponse(session_messages=[])

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"home/gameplay/v1: {payload.user_name} failed, error: {str(e)}",
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有房间",
            )

        # 是否有游戏？！！
        current_room = game_server.get_room(user_name)
        assert current_room is not None
        if current_room._sdg_game is None:
            # logger.error(f"view_home: {user_name} has no game")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏",
            )

        # 获取当前地图
        sd_game = current_room._sdg_game
        mapping_data = sd_game.get_stage_actor_distribution_mapping()
        logger.info(
            f"view_home: {user_name} mapping_data: {mapping_data}, time={sd_game._turn_counter}"
        )

        # 返回。
        return WerewolfGameStateResponse(
            mapping=mapping_data,
            game_time=sd_game._turn_counter,
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
        if current_room._sdg_game is None:
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
            actor_entity = current_room._sdg_game.get_entity_by_name(actor_name)
            if actor_entity is None:
                logger.error(f"view_actor: {user_name} actor {actor_name} not found.")
                continue

            # 添加到集合中
            actor_entities.add(actor_entity)

        # 序列化角色实体
        entities_serialization = current_room._sdg_game.serialize_entities(
            actor_entities
        )

        # 返回!
        return WerewolfGameActorDetailsResponse(
            actor_entities_serialization=entities_serialization,
        )
    except Exception as e:
        logger.error(f"get_actors_details: {user_name} error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器错误: {str(e)}",
        )


###################################################################################################################################################################
