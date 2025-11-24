from typing import Dict, Set
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.tcg_game import TCGGame
from .game_server_depends import GameServerInstance
from ..game.game_server import GameServer
from .home_actions import activate_speak_action, activate_stage_transition
from ..models import (
    HomeGamePlayRequest,
    HomeGamePlayResponse,
    HomeTransDungeonRequest,
    HomeTransDungeonResponse,
    AllyComponent,
    Dungeon,
    DungeonComponent,
    KickOffMessageComponent,
    Combat,
)
from ..entitas import Matcher, Entity

###################################################################################################################################################################
home_gameplay_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _validate_player_at_home(
    user_name: str,
    game_server: GameServer,
) -> TCGGame:
    """
    验证玩家是否在家园状态，包括房间存在性、TCG游戏实例和玩家当前位置检查

    Args:
        user_name: 用户名
        game_server: 游戏服务器实例

    Returns:
        TCGGame: 验证通过的 TCG 游戏实例

    Raises:
        HTTPException(404): 房间不存在或游戏实例不存在
        HTTPException(400): 玩家当前不在家园状态
        AssertionError: 房间实例状态异常
    """

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    # 获取房间实例并检查游戏是否存在
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "_validate_player_at_home: room instance is None"
    if current_room._tcg_game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏，请先登录",
        )

    # 判断游戏状态，不是Home状态不可以推进。
    if not current_room._tcg_game.is_player_at_home:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前不在家园状态，不能进行家园操作",
        )

    # 返回游戏实例
    return current_room._tcg_game


###################################################################################################################################################################
###################################################################################################################################################################
# TODO, 进入地下城！
def _dungeon_advance(
    tcg_game: TCGGame, dungeon: Dungeon, heros_entities: Set[Entity]
) -> bool:
    """
    地下城关卡推进的主协调函数

    Args:
        dungeon: 地下城实例
        heros_entities: 英雄实体集合

    Returns:
        bool: 是否成功推进到下一关卡
    """
    # 1. 验证前置条件
    # 是否有可以进入的关卡？
    upcoming_dungeon = dungeon.get_current_stage()
    if upcoming_dungeon is None:
        logger.error(
            f"{tcg_game.current_dungeon.name} 没有下一个地下城！position = {tcg_game.current_dungeon.current_stage_index}"
        )
        return False

    # 下一个关卡实体, 没有就是错误的。
    stage_entity = tcg_game.get_stage_entity(upcoming_dungeon.name)
    if stage_entity is None or not stage_entity.has(DungeonComponent):
        logger.error(f"{upcoming_dungeon.name} 没有对应的stage实体！")
        return False

    # 集体准备传送
    if len(heros_entities) == 0:
        logger.error(f"没有英雄不能进入地下城!= {stage_entity.name}")
        return False

    logger.debug(
        f"{tcg_game.current_dungeon.name} = [{tcg_game.current_dungeon.current_stage_index}]关为：{stage_entity.name}，可以进入！！！！"
    )

    # 2. 生成并发送传送提示消息
    # 准备提示词
    if dungeon.current_stage_index == 0:
        trans_message = f"""# 提示！准备进入地下城: {stage_entity.name}"""
    else:
        trans_message = f"""# 提示！准备进入下一个地下城: {stage_entity.name}"""

    for hero_entity in heros_entities:
        tcg_game.append_human_message(hero_entity, trans_message)  # 添加故事

    # 3. 执行场景传送
    tcg_game.stage_transition(heros_entities, stage_entity)

    # 4. 设置KickOff消息
    # 需要在这里补充设置地下城与怪物的kickoff信息。
    stage_kick_off_comp = stage_entity.get(KickOffMessageComponent)
    assert (
        stage_kick_off_comp is not None
    ), f"{stage_entity.name} 没有KickOffMessageComponent组件！"

    # 获取场景内角色的外貌信息
    actors_appearances_mapping: Dict[str, str] = tcg_game.get_stage_actor_appearances(
        stage_entity
    )

    # 重新组织一下
    actors_appearances_info = []
    for actor_name, appearance in actors_appearances_mapping.items():
        actors_appearances_info.append(f"{actor_name}: {appearance}")
    if len(actors_appearances_info) == 0:
        actors_appearances_info.append("无")

    # 生成追加的kickoff信息
    append_kickoff_message = f"""**场景内角色**
    
{"\n\n".join(actors_appearances_info)}"""

    # 设置组件
    stage_entity.replace(
        KickOffMessageComponent,
        stage_kick_off_comp.name,
        stage_kick_off_comp.content + "\n\n" + append_kickoff_message,
    )

    # 5. 初始化战斗状态
    dungeon.combat_sequence.start_combat(Combat(name=stage_entity.name))

    return True


#######################################################################################################################################
# TODO!!! 进入地下城。
def _all_heros_launch_dungeon(tcg_game: TCGGame) -> bool:
    if tcg_game.current_dungeon.current_stage_index < 0:
        tcg_game.current_dungeon.current_stage_index = 0  # 第一次设置，第一个关卡。
        tcg_game.create_dungeon_entities(tcg_game.current_dungeon)
        heros_entities = tcg_game.get_group(Matcher(all_of=[AllyComponent])).entities
        # return tcg_game._dungeon_advance(tcg_game.current_dungeon, heros_entities)
        return _dungeon_advance(tcg_game, tcg_game.current_dungeon, heros_entities)
    else:
        # 第一次，必须是<0, 证明一次没来过。
        logger.error(
            f"launch_dungeon position = {tcg_game.current_dungeon.current_stage_index}"
        )

    return False


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/gameplay/v1/", response_model=HomeGamePlayResponse
)
async def home_gameplay(
    payload: HomeGamePlayRequest,
    game_server: GameServerInstance,
) -> HomeGamePlayResponse:

    logger.info(f"/home/gameplay/v1/: {payload.model_dump_json()}")
    try:
        # 验证前置条件并获取游戏实例
        web_game = await _validate_player_at_home(
            payload.user_name,
            game_server,
        )

        # 根据标记处理。
        match payload.user_input.tag:

            case "/advancing":
                # 推进一次游戏
                await web_game.npc_home_pipeline.process()
                return HomeGamePlayResponse(client_messages=[])

            case "/speak":
                # 激活说话动作
                if activate_speak_action(
                    web_game,
                    target=payload.user_input.data.get("target", ""),
                    content=payload.user_input.data.get("content", ""),
                ):
                    await web_game.player_home_pipeline.process()
                return HomeGamePlayResponse(client_messages=[])

            case "/trans_home":
                # 激活场景转换动作
                if activate_stage_transition(
                    web_game, stage_name=payload.user_input.data.get("stage_name", "")
                ):
                    await web_game.player_home_pipeline.process()
                return HomeGamePlayResponse(client_messages=[])

            case _:
                logger.error(f"未知的请求类型 = {payload.user_input.tag}, 不能处理！")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未知的请求类型 = {payload.user_input.tag}, 不能处理！",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"home/gameplay/v1: {payload.user_name} failed, error: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/trans_dungeon/v1/", response_model=HomeTransDungeonResponse
)
async def home_trans_dungeon(
    payload: HomeTransDungeonRequest,
    game_server: GameServerInstance,
) -> HomeTransDungeonResponse:

    logger.info(f"/home/trans_dungeon/v1/: {payload.model_dump_json()}")
    try:
        # 验证前置条件并获取游戏实例
        web_game = await _validate_player_at_home(
            payload.user_name,
            game_server,
        )

        # 判断地下城是否存在
        if len(web_game.current_dungeon.stages) == 0:
            logger.warning(
                "没有地下城可以传送, 全部地下城已经结束。！！！！已经全部被清空！！！！或者不存在！！！！"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有地下城可以传送, 全部地下城已经结束。！！！！已经全部被清空！！！！或者不存在！！！！",
            )

        # 传送地下城执行。
        # if not web_game.launch_dungeon():
        if not _all_heros_launch_dungeon(web_game):
            logger.error("第一次地下城传送失败!!!!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="第一次地下城传送失败!!!!",
            )
        #
        return HomeTransDungeonResponse(
            message=payload.model_dump_json(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"home/trans_dungeon/v1: {payload.user_name} failed, error: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
