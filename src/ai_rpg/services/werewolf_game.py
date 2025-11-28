from fastapi import APIRouter, HTTPException, status
from loguru import logger
from .game_server_dependencies import CurrentGameServer
from ..models import (
    WerewolfGameStartRequest,
    WerewolfGameStartResponse,
    WerewolfGamePlayRequest,
    WerewolfGamePlayResponse,
    WerewolfGameStateResponse,
    World,
    World,
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    HunterComponent,
    NightKillTargetComponent,
    DeathComponent,
    DayDiscussedComponent,
    NightActionReadyComponent,
    NightActionCompletedComponent,
    DayVotedComponent,
    DayVoteOutComponent,
)
from ..demo.werewolf_game_world import create_demo_sd_game_boot
from ..game.player_session import PlayerSession
from ..game.sdg_game import SDGGame
from ..configuration import (
    server_configuration,
)
from ..chat_services import ChatClient
from ..game.config import GLOBAL_SDG_GAME_NAME
from typing import Dict, cast, Any, final
from ..entitas import Matcher
from typing_extensions import TypedDict
from enum import IntEnum, unique

###################################################################################################################################################################
werewolf_game_api_router = APIRouter()


###################################################################################################################################################################
class PhaseChangeNotification(TypedDict):
    phase: str
    turn_number: int


###############################################################################################################################################
def announce_night_phase(sdg_game: SDGGame) -> None:
    """
    宣布夜晚阶段开始,并进行夜晚阶段的初始化工作:
    1. 向所有存活玩家宣布进入夜晚
    2. 处理被放逐玩家的状态转换(从白天投票放逐标记转为死亡状态)
    3. 清理上一个白天阶段的标记(讨论和投票组件)
    """

    # 验证当前回合计数器是否处于夜晚阶段
    # 回合计数器规则: 0=游戏开始, 1=第一夜, 2=第一白天, 3=第二夜, 4=第二白天...
    # 夜晚阶段的特征: 计数器为奇数(1,3,5...)
    assert (
        sdg_game._turn_counter % 2 == 1 or sdg_game._turn_counter > 0
    ), "当前时间标记不是夜晚"

    logger.info(f"进入夜晚,时间标记 = {sdg_game._turn_counter}")

    # 计算当前是第几个夜晚(从1开始计数)
    current_night_number = (sdg_game._turn_counter + 1) // 2

    # 使用封装的通知方法
    sdg_game.announce_to_players(
        f"# 注意!天黑请闭眼!这是第 {current_night_number} 个夜晚"
    )

    # 获取所有在白天被标记为投票放逐的玩家
    last_day_vote_outs = sdg_game.get_group(
        Matcher(
            all_of=[DayVoteOutComponent],
        )
    ).entities.copy()

    # 处理被放逐玩家的状态转换
    for voted_out_player in last_day_vote_outs:
        voted_out_player.replace(DeathComponent, voted_out_player.name)

    # 清理白天阶段的标记组件
    sdg_game.cleanup_game_phase_markers(
        [DayDiscussedComponent, DayVotedComponent, DayVoteOutComponent]
    )

    # 通知客户端一个消息，夜晚阶段开始了
    notification = PhaseChangeNotification(
        phase="night", turn_number=sdg_game._turn_counter
    )
    sdg_game.player_session.add_game_message(cast(Dict[str, Any], notification))


###############################################################################################################################################
def announce_day_phase(sdg_game: SDGGame) -> None:
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
        sdg_game._turn_counter % 2 == 0 and sdg_game._turn_counter > 0
    ), "当前时间标记不是白天"

    logger.info(f"进入白天,时间标记 = {sdg_game._turn_counter}")

    # 计算当前是第几个白天(从1开始计数)
    current_day_number = sdg_game._turn_counter // 2

    # 使用封装的通知方法
    sdg_game.announce_to_players(
        f"# 注意!天亮请睁眼!这是第 {current_day_number} 个白天"
    )

    # 获取所有在昨夜被标记为击杀的玩家
    last_night_kills = sdg_game.get_group(
        Matcher(
            all_of=[NightKillTargetComponent],
        )
    ).entities.copy()

    # 公布昨夜死亡信息
    if len(last_night_kills) > 0:

        # 格式化死亡玩家列表信息
        death_announcement = ", ".join(
            f"{player.name}(被杀害)" for player in last_night_kills
        )
        logger.info(f"在夜晚,以下玩家被杀害: {death_announcement}")

        # 向所有玩家广播死亡信息
        sdg_game.announce_to_players(f"# 昨晚被杀害的玩家有: {death_announcement}")

        # 处理被杀玩家的状态转换
        for killed_player in last_night_kills:

            # 添加正式的死亡状态标记
            logger.info(
                f"玩家 {killed_player.name} 在第 {current_day_number} 个白天 被标记为死亡状态, 昨夜因为某种原因被杀害"
            )
            killed_player.replace(DeathComponent, killed_player.name)

    else:
        # 平安夜,无人死亡
        logger.info("在夜晚,没有玩家被杀害")
        sdg_game.announce_to_players(f"# 昨晚没有玩家被杀害,平安夜")

    # 清理夜晚阶段的计划标记组件
    sdg_game.cleanup_game_phase_markers(
        [
            NightActionReadyComponent,
            NightActionCompletedComponent,
            NightKillTargetComponent,
        ]
    )

    # 通知客户端一个消息，白天阶段开始了
    notification = PhaseChangeNotification(
        phase="day", turn_number=sdg_game._turn_counter
    )
    sdg_game.player_session.add_game_message(
        cast(
            Dict[str, Any],
            notification,
        )
    )


###################################################################################################################################################################
def is_night_phase_completed(sdg_game: SDGGame) -> bool:
    """
    检查夜晚阶段是否已经结束

    Args:
        sd_game: 游戏实例

    Returns:
        bool: 如果夜晚阶段已经结束返回True，否则返回False
    """

    assert sdg_game._turn_counter % 2 == 1, "当前时间标记不是夜晚!!!!!"
    assert sdg_game._started, "游戏还没有开始!!!!!"

    entities1 = sdg_game.get_group(
        Matcher(
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
            ],
            none_of=[DeathComponent],
        )
    ).entities.copy()

    entities2 = sdg_game.get_group(
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

    logger.debug(
        f"夜晚行动完成标记玩家数量: {len(entities2)} / 存活玩家数量: {len(entities1)}"
    )
    return len(entities1) >= 0 and len(entities2) >= len(entities1)


###################################################################################################################################################################
def is_day_phase_completed(sdg_game: SDGGame) -> bool:
    """
    检查白天阶段是否已经结束（白天投票完毕就是结束）

    Args:
        sd_game: 游戏实例

    Returns:
        bool: 如果白天阶段已经结束返回True，否则返回False
    """
    # TODO: 实现白天结束的判断逻辑（投票完毕即为结束）
    assert (
        sdg_game._turn_counter % 2 == 0 and sdg_game._turn_counter > 0
    ), "当前时间标记不是白天!!!!!"
    assert sdg_game._started, "游戏还没有开始!!!!!"

    if not is_day_discussion_complete(sdg_game):
        logger.debug("白天讨论尚未完成")
        return False

    if not is_day_vote_complete(sdg_game):
        logger.debug("白天投票尚未完成")
        return False

    return True


###################################################################################################################################################################
def check_town_victory(sdg_game: SDGGame) -> bool:
    """
    判断村民阵营胜利：所有狼人都被淘汰且至少有一个村民存活
    """

    dead_werewolves = sdg_game.get_group(
        Matcher(
            all_of=[WerewolfComponent, DeathComponent],
        )
    ).entities.copy()

    total_werewolves = sdg_game.get_group(
        Matcher(
            all_of=[WerewolfComponent],
        )
    ).entities.copy()

    alive_town = sdg_game.get_group(
        Matcher(
            any_of=[
                VillagerComponent,
                SeerComponent,
                WitchComponent,
                HunterComponent,
            ],
            none_of=[DeathComponent],
        )
    ).entities.copy()

    # 村民胜利条件：所有狼人都死亡 且 至少有一个村民存活
    logger.debug(
        f"存活村民数量: {len(alive_town)} / 死亡狼人数量: {len(dead_werewolves)} / 总狼人数量: {len(total_werewolves)}"
    )
    return len(alive_town) > 0 and len(dead_werewolves) >= len(total_werewolves)


################################################################################################################################################


def check_werewolves_victory(sdg_game: SDGGame) -> bool:
    """
    判断狼人阵营胜利：狼人数量大于等于村民数量且至少有一个狼人存活
    """

    town_entities = sdg_game.get_group(
        Matcher(
            any_of=[
                VillagerComponent,
                SeerComponent,
                WitchComponent,
                HunterComponent,
            ],
            none_of=[DeathComponent],
        )
    ).entities.copy()

    wolf_entities = sdg_game.get_group(
        Matcher(
            all_of=[WerewolfComponent],
            none_of=[DeathComponent],
        )
    ).entities.copy()

    # 狼人胜利条件：狼人数量 >= 村民数量 且 至少有一个狼人存活
    logger.debug(
        f"存活村民数量: {len(town_entities)} / 存活狼人数量: {len(wolf_entities)}"
    )
    return len(town_entities) <= len(wolf_entities) and len(wolf_entities) > 0


###################################################################################################################################################################
@final
@unique
class VictoryCondition(IntEnum):
    NONE = (0,)  # 无结果
    TOWN_VICTORY = (1,)  # 村民阵营胜利
    WEREWOLVES_VICTORY = (2,)  # 狼人阵营胜利


###################################################################################################################################################################
def check_victory_conditions(sdg_game: SDGGame) -> VictoryCondition:
    """
    检查游戏是否达成胜利条件

    Args:
        sd_game: 游戏实例

    Returns:
        bool: 如果达成胜利条件返回True，否则返回False
    """
    town_victory = check_town_victory(sdg_game)
    if town_victory:
        logger.info("村民阵营胜利")
        return VictoryCondition.TOWN_VICTORY

    werewolves_victory = check_werewolves_victory(sdg_game)
    if werewolves_victory:
        logger.info("狼人阵营胜利")
        return VictoryCondition.WEREWOLVES_VICTORY

    logger.debug("尚未达成任何胜利条件")
    return VictoryCondition.NONE


###################################################################################################################################################################
def is_day_discussion_complete(sdg_game: SDGGame) -> bool:
    """
    是否白天的讨论阶段已经完成
    """

    # 讨论完的人。
    entities1 = sdg_game.get_group(
        Matcher(
            all_of=[DayDiscussedComponent],
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
                VillagerComponent,
                HunterComponent,
            ],
        )
    ).entities.copy()

    if sdg_game._turn_counter == 2:
        logger.info("第一个白天讨论，特殊机制：即使第一晚猝死也可以参与讨论")
        entities2 = sdg_game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                    HunterComponent,
                ],
            )
        ).entities.copy()
    else:
        logger.info("后续白天讨论，存活玩家考虑死亡状态")
        entities2 = sdg_game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                    HunterComponent,
                ],
                none_of=[DeathComponent],
            )
        ).entities.copy()

    logger.info(
        f"讨论完成标记玩家数量: {len(entities1)} / 存活玩家数量: {len(entities2)}"
    )

    return len(entities1) > 0 and len(entities1) >= len(entities2)


###################################################################################################################################################################
def is_day_vote_complete(sdg_game: SDGGame) -> bool:
    """
    是否白天的投票阶段已经完成
    """

    entities1 = sdg_game.get_group(
        Matcher(
            all_of=[DayVotedComponent],
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
                VillagerComponent,
                HunterComponent,
            ],
        )
    ).entities.copy()

    entities2 = sdg_game.get_group(
        Matcher(
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
                VillagerComponent,
                HunterComponent,
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
    game_server: CurrentGameServer,
) -> WerewolfGameStartResponse:

    logger.info(f"Starting werewolf game: {payload.model_dump_json()}")

    try:
        # 先检查房间是否存在，存在就删除旧房间
        if game_server.has_room(payload.user_name):

            logger.debug(f"start/v1: {payload.user_name} room exists, removing it")

            pre_room = game_server.get_room(payload.user_name)
            assert pre_room is not None

            if pre_room._sdg_game is not None:
                logger.debug(
                    f"start/v1: {payload.user_name} removing old game instance"
                )

                # 保存并退出旧游戏
                pre_room._sdg_game.save()
                pre_room._sdg_game.exit()

                # 先断开引用，等待垃圾回收
                pre_room._sdg_game = None

            game_server.remove_room(pre_room)

        assert not game_server.has_room(
            payload.user_name
        ), "Room should have been removed."

        # 然后创建一个新的房间
        new_room = game_server.create_room(
            user_name=payload.user_name,
        )
        logger.info(f"start/v1: {payload.user_name} create room = {new_room._username}")
        assert new_room._sdg_game is None

        # 创建boot数据
        assert GLOBAL_SDG_GAME_NAME == payload.game_name, "目前只支持 SD 游戏"
        world_boot = create_demo_sd_game_boot(payload.game_name)
        assert world_boot is not None, "WorldBoot 创建失败"

        # 创建游戏实例
        new_room._sdg_game = web_game = SDGGame(
            name=payload.game_name,
            player_session=PlayerSession(
                name=payload.user_name,
                actor="角色.主持人",  # 写死先！
                game=payload.game_name,
            ),
            world=World(boot=world_boot),
        )

        # 配置聊天客户端
        ChatClient.initialize_url_config(server_configuration)

        # 新游戏！
        web_game.new_game().save()

        # 测试一下玩家控制角色，如果没有就是错误。
        assert web_game.get_player_entity() is not None, "玩家实体不存在"

        # 初始化!
        await web_game.initialize()

        # 在这里添加启动游戏的逻辑
        return WerewolfGameStartResponse(
            message=web_game.world.model_dump_json(indent=2)
        )

    except HTTPException:
        # 直接向上传播 HTTPException，不要重新包装
        raise
    except Exception as e:
        # 只捕获非预期的异常
        logger.exception(
            f"start_werewolf_game unexpected error for {payload.user_name}, error: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动游戏失败，请稍后重试",
        )


###################################################################################################################################################################


@werewolf_game_api_router.post(
    path="/api/werewolf/gameplay/v1/", response_model=WerewolfGamePlayResponse
)
async def play_werewolf_game(
    payload: WerewolfGamePlayRequest,
    game_server: CurrentGameServer,
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

        web_game = current_room._sdg_game

        if user_input == "/k" or user_input == "/kickoff":

            if web_game._turn_counter == 0 and not web_game._started:

                logger.info("游戏开始，准备入场记阶段！！！！！！")

                # 初始化游戏的开场流程
                await web_game.werewolf_game_kickoff_pipeline.process()

                # 标记游戏已经开始
                web_game._started = True

                # 返回当前的客户端消息
                return WerewolfGamePlayResponse(session_messages=[])

            else:
                logger.error(
                    f"当前时间标记不是0，或者游戏已经开始，是{web_game._turn_counter}，不能执行 /kickoff 命令"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="当前时间标记不是0，或者游戏已经开始，不能执行 /kickoff 命令",
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
                logger.info("游戏结束，触发胜利条件，准备终止游戏...")
                if victory_condition == VictoryCondition.TOWN_VICTORY:
                    logger.info("\n!!!!!!!!!!!!!!!!!村民阵营胜利!!!!!!!!!!!!!!!!!!!\n")
                elif victory_condition == VictoryCondition.WEREWOLVES_VICTORY:
                    logger.info("\n!!!!!!!!!!!!!!!!!狼人阵营胜利!!!!!!!!!!!!!!!!!!!\n")

            # 返回！
            return WerewolfGamePlayResponse(session_messages=[])

        if user_input == "/n" or user_input == "/night":

            # 如果是夜晚
            if web_game._turn_counter % 2 == 1:

                if is_night_phase_completed(web_game):
                    logger.error("夜晚阶段已经完成，不能重复执行 /night 命令")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="夜晚阶段已经完成，不能重复执行 /night 命令",
                    )

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

                if is_day_discussion_complete(web_game):
                    logger.error("白天阶段已经完成，不能重复执行 /day 命令")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="白天阶段已经完成，不能重复执行 /day 命令",
                    )

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

                if not is_day_discussion_complete(web_game):
                    logger.error(
                        "白天讨论环节没有完成，不能进入投票阶段！！！！！！！！！！！！"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="白天讨论环节没有完成，不能进入投票阶段",
                    )

                if is_day_vote_complete(web_game):
                    logger.error("白天投票环节已经完成，不能重复执行 /vote 命令")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="白天投票环节已经完成，不能重复执行 /vote 命令",
                    )

                # 如果讨论完毕，则进入投票环节
                await web_game.werewolf_game_vote_pipeline.process()

                # 检查是否达成胜利条件 投票会产生死亡
                victory_condition = check_victory_conditions(web_game)
                if victory_condition != VictoryCondition.NONE:
                    logger.info("游戏结束，触发胜利条件，准备终止游戏...")
                    if victory_condition == VictoryCondition.TOWN_VICTORY:
                        logger.info(
                            "\n!!!!!!!!!!!!!!!!!村民阵营胜利!!!!!!!!!!!!!!!!!!!\n"
                        )
                    elif victory_condition == VictoryCondition.WEREWOLVES_VICTORY:
                        logger.info(
                            "\n!!!!!!!!!!!!!!!!!狼人阵营胜利!!!!!!!!!!!!!!!!!!!\n"
                        )

                # 返回！
                return WerewolfGamePlayResponse(session_messages=[])

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

    except HTTPException:
        # 直接向上传播 HTTPException，不要重新包装
        raise
    except Exception as e:
        # 只捕获非预期的异常
        logger.exception(
            f"play_werewolf_game unexpected error for {payload.user_name}, error: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"游戏操作失败，请稍后重试",
        )


###################################################################################################################################################################


@werewolf_game_api_router.get(
    path="/api/werewolf/state/v1/{user_name}/{game_name}/state",
    response_model=WerewolfGameStateResponse,
)
async def get_werewolf_game_state(
    game_server: CurrentGameServer,
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏",
            )

        # 获取当前地图
        sd_game = current_room._sdg_game
        # mapping_data = sd_game.get_stage_actor_distribution_mapping()
        # logger.info(
        #     f"view_home: {user_name} mapping_data: {mapping_data}, time={sd_game._turn_counter}"
        # )

        # 返回。
        return WerewolfGameStateResponse(
            # mapping=mapping_data,
            game_time=sd_game._turn_counter,
            victory_condition=check_victory_conditions(sd_game).name,
            is_discussion_complete=is_day_discussion_complete(sd_game),
        )
    except HTTPException:
        # 直接向上传播 HTTPException，不要重新包装
        raise
    except Exception as e:
        # 只捕获非预期的异常
        logger.exception(
            f"get_werewolf_game_state unexpected error for {user_name}, error: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取游戏状态失败，请稍后重试",
        )


###################################################################################################################################################################


# @werewolf_game_api_router.get(
#     path="/api/werewolf/actors/v1/{user_name}/{game_name}/details",
#     response_model=WerewolfGameActorDetailsResponse,
# )
# async def get_werewolf_actors_details(
#     game_server: GameServerInstance,
#     user_name: str,
#     game_name: str,
#     actor_names: List[str] = Query(..., alias="actors"),
# ) -> WerewolfGameActorDetailsResponse:

#     logger.info(
#         f"/werewolf/actors/v1/{user_name}/{game_name}/details: {user_name}, {game_name}, {actor_names}"
#     )

#     try:

#         # 是否有房间？！！
#         if not game_server.has_room(user_name):
#             logger.error(f"view_actor: {user_name} has no room")
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="没有房间",
#             )

#         # 是否有游戏？！！
#         current_room = game_server.get_room(user_name)
#         assert current_room is not None
#         if current_room._sdg_game is None:
#             logger.error(f"view_actor: {user_name} has no game")
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="没有游戏",
#             )

#         if len(actor_names) == 0 or actor_names[0] == "":
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="请提供至少一个角色名称",
#             )

#         # 获取所有角色实体
#         entities_serialization: List[EntitySerialization] = []

#         # 获取指定角色实体
#         actor_entities: Set[Entity] = set()

#         for actor_name in actor_names:
#             # 获取角色实体
#             actor_entity = current_room._sdg_game.get_entity_by_name(actor_name)
#             if actor_entity is None:
#                 logger.error(f"view_actor: {user_name} actor {actor_name} not found.")
#                 continue

#             # 添加到集合中
#             actor_entities.add(actor_entity)

#         # 序列化角色实体
#         entities_serialization = current_room._sdg_game.serialize_entities(
#             actor_entities
#         )

#         # 返回!
#         return WerewolfGameActorDetailsResponse(
#             actor_entities_serialization=entities_serialization,
#         )
#     except HTTPException:
#         # 直接向上传播 HTTPException，不要重新包装
#         raise
#     except Exception as e:
#         # 只捕获非预期的异常
#         logger.exception(
#             f"get_werewolf_actors_details unexpected error for {user_name}, error: {str(e)}"
#         )
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"获取角色详情失败，请稍后重试",
#         )


###################################################################################################################################################################
