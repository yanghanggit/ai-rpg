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
def enter_dungeon_stage(
    tcg_game: TCGGame, dungeon: Dungeon, ally_entities: Set[Entity]
) -> bool:
    """
    进入地下城关卡并初始化战斗环境

    协调整个关卡进入流程：验证前置条件、生成叙事消息、执行场景传送、
    设置战斗环境和启动战斗序列。

    Args:
        tcg_game: TCG游戏实例
        dungeon: 地下城实例
        ally_entities: 参与进入的盟友实体集合

    Returns:
        bool: 是否成功进入关卡并完成初始化

    Note:
        - 用于首次进入(index=0)和后续关卡推进(index>0)
        - 调用者: initialize_dungeon_first_entry, _all_heros_next_dungeon
    """
    # 验证盟友队伍非空
    if len(ally_entities) == 0:
        logger.error(f"没有英雄不能进入地下城!")
        return False

    # 1. 验证前置条件 - 获取当前关卡数据
    next_dungeon_stage_model = dungeon.get_current_stage()
    assert next_dungeon_stage_model is not None, f"{dungeon.name} 地下城关卡数据异常！"

    # 2. 获取关卡实体
    dungeon_stage_entity = tcg_game.get_stage_entity(next_dungeon_stage_model.name)
    assert (
        dungeon_stage_entity is not None
    ), f"{next_dungeon_stage_model.name} 没有对应的stage实体！"
    assert dungeon_stage_entity.has(
        DungeonComponent
    ), f"{next_dungeon_stage_model.name} 没有DungeonComponent组件！"

    logger.debug(
        f"{tcg_game.current_dungeon.name} = [{tcg_game.current_dungeon.current_stage_index}]关为：{dungeon_stage_entity.name}，可以进入"
    )

    # 3. 生成并发送传送提示消息
    if dungeon.current_stage_index == 0:
        trans_message = f"""# 提示！准备进入地下城: {dungeon_stage_entity.name}"""
    else:
        trans_message = f"""# 提示！准备进入下一个地下城: {dungeon_stage_entity.name}"""

    for ally_entity in ally_entities:
        tcg_game.append_human_message(ally_entity, trans_message)

    # 4. 执行场景传送
    tcg_game.stage_transition(ally_entities, dungeon_stage_entity)

    # 5. 设置KickOff消息并添加场景角色信息
    stage_kickoff_comp = dungeon_stage_entity.get(KickOffMessageComponent)
    assert (
        stage_kickoff_comp is not None
    ), f"{dungeon_stage_entity.name} 没有KickOffMessageComponent组件！"

    # 获取场景内角色的外貌信息
    actors_appearances_mapping: Dict[str, str] = tcg_game.get_stage_actor_appearances(
        dungeon_stage_entity
    )

    # 组织角色外貌信息列表
    actors_appearances_info = []
    for actor_name, appearance in actors_appearances_mapping.items():
        actors_appearances_info.append(f"{actor_name}: {appearance}")
    if len(actors_appearances_info) == 0:
        actors_appearances_info.append("无")

    # 追加场景角色信息到 KickOff 消息
    enhanced_kickoff_content = f"""{stage_kickoff_comp.content}
    
**场景内角色**  

{"\n\n".join(actors_appearances_info)}"""

    dungeon_stage_entity.replace(
        KickOffMessageComponent,
        stage_kickoff_comp.name,
        enhanced_kickoff_content,
    )

    # 6. 初始化战斗状态
    dungeon.combat_sequence.start_combat(Combat(name=dungeon_stage_entity.name))

    return True


#######################################################################################################################################
def initialize_dungeon_first_entry(tcg_game: TCGGame) -> bool:
    """
    初始化地下城首次进入，仅在首次进入时调用（current_stage_index < 0）

    Args:
        tcg_game: TCG游戏实例

    Returns:
        bool: 是否成功初始化并进入第一个关卡

    Note:
        此函数仅处理首次进入场景，后续关卡推进使用 enter_dungeon_stage
    """
    # 验证是否为首次进入（索引必须为-1）
    if tcg_game.current_dungeon.current_stage_index >= 0:
        logger.error(
            f"initialize_dungeon_first_entry: 索引异常 = {tcg_game.current_dungeon.current_stage_index}, "
            f"期望值为 -1（首次进入标记）"
        )
        return False

    # 初始化地下城状态
    tcg_game.current_dungeon.current_stage_index = 0
    tcg_game.create_dungeon_entities(tcg_game.current_dungeon)

    # 获取所有盟友实体并推进到第一关
    ally_entities = tcg_game.get_group(Matcher(all_of=[AllyComponent])).entities.copy()
    return enter_dungeon_stage(tcg_game, tcg_game.current_dungeon, ally_entities)


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
        if not initialize_dungeon_first_entry(web_game):
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
