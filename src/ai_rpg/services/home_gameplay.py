"""
家园游戏玩法服务模块

本模块提供家园系统的核心API接口，负责处理玩家在家园状态下的各种游戏操作。
家园是玩家在游戏中的安全区域，玩家可以在此与NPC互动、切换场景、准备探险等。

主要功能:
    - 家园玩法处理: 处理玩家在家园内的各种操作请求(对话、移动、推进等)
    - 地下城传送: 处理玩家从家园传送到地下城的流程
    - 状态验证: 确保玩家处于合法的家园状态

API端点:
    - POST /api/home/gameplay/v1/: 家园游戏玩法主接口
    - POST /api/home/trans_dungeon/v1/: 家园传送地下城接口

核心概念:
    - Home Pipeline: 家园状态下的处理流程，分为NPC pipeline和Player pipeline
    - Stage: 家园内的不同场景/区域
    - Dungeon Transition: 从家园到地下城的状态转换

依赖关系:
    - GameServer: 游戏服务器实例，管理所有玩家房间
    - TCGGame: 具体的游戏实例，包含玩家状态和游戏逻辑
    - home_actions: 家园动作激活模块(对话、场景切换等)
    - dungeon_stage_transition: 地下城传送相关逻辑

使用说明:
    所有接口都需要玩家处于已登录状态，且当前位置必须在家园。
    接口会自动验证玩家状态，验证失败会抛出相应的HTTP异常。
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.tcg_game import TCGGame
from .game_server_dependencies import CurrentGameServer
from ..game.game_server import GameServer
from .home_actions import activate_speak_action, activate_stage_transition
from .dungeon_stage_transition import (
    initialize_dungeon_first_entry,
)
from ..models import (
    HomeGamePlayRequest,
    HomeGamePlayResponse,
    HomeTransDungeonRequest,
    HomeTransDungeonResponse,
)

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
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/gameplay/v1/", response_model=HomeGamePlayResponse
)
async def home_gameplay(
    payload: HomeGamePlayRequest,
    game_server: CurrentGameServer,
) -> HomeGamePlayResponse:
    """
    家园游戏玩法主接口，处理玩家在家园状态下的各种操作请求

    该接口是家园系统的核心处理入口，根据玩家的不同操作标记(tag)分发到对应的处理逻辑。
    支持的操作包括：游戏推进、NPC对话、场景切换等。所有操作都需要玩家处于家园状态。

    Args:
        payload: 家园游戏玩法请求对象，包含用户名和用户输入信息
            - user_name: 用户名，用于标识玩家
            - user_input: 用户输入对象，包含操作标记(tag)和相关数据(data)
        game_server: 游戏服务器实例，由依赖注入提供

    Returns:
        HomeGamePlayResponse: 家园游戏玩法响应对象
            - client_messages: 返回给客户端的消息列表

    Raises:
        HTTPException(404): 玩家未登录或游戏实例不存在
        HTTPException(400): 玩家不在家园状态或请求类型未知
        HTTPException(500): 服务器内部错误

    支持的操作标记:
        - /advancing: 推进游戏流程，执行NPC的home pipeline处理
        - /speak: 激活对话动作，玩家与指定目标进行对话
        - /trans_home: 激活场景切换动作，切换到指定的家园场景

    示例:
        推进游戏:
        ```json
        {
            "user_name": "player1",
            "user_input": {
                "tag": "/advancing",
                "data": {}
            }
        }
        ```

        NPC对话:
        ```json
        {
            "user_name": "player1",
            "user_input": {
                "tag": "/speak",
                "data": {
                    "target": "npc_name",
                    "content": "对话内容"
                }
            }
        }
        ```
    """

    logger.info(f"/api/home/gameplay/v1/: {payload.model_dump_json()}")

    # 验证前置条件并获取游戏实例
    rpg_game = await _validate_player_at_home(
        payload.user_name,
        game_server,
    )

    # 根据用户输入的操作标记进行分发处理
    match payload.user_input.tag:

        case "/advancing":
            # 推进游戏流程：执行NPC的home pipeline，自动推进游戏状态
            await rpg_game.npc_home_pipeline.process()
            return HomeGamePlayResponse(client_messages=[])

        case "/speak":
            # 激活对话动作：玩家与指定NPC进行对话交互
            # 从data中获取对话目标(target)和对话内容(content)
            success, error_detail = activate_speak_action(
                rpg_game,
                target=payload.user_input.data.get("target", ""),
                content=payload.user_input.data.get("content", ""),
            )
            if success:
                # 对话动作激活成功后，执行玩家的home pipeline处理
                await rpg_game.player_home_pipeline.process()
                return HomeGamePlayResponse(client_messages=[])
            else:
                # 对话动作激活失败，抛出包含具体错误信息的异常
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_detail,
                )

        case "/trans_home":
            # 激活场景切换动作：在家园内切换到不同的场景
            # 从data中获取目标场景名称(stage_name)
            success, error_detail = activate_stage_transition(
                rpg_game, stage_name=payload.user_input.data.get("stage_name", "")
            )
            if success:
                # 场景切换动作激活成功后，执行玩家的home pipeline处理
                await rpg_game.player_home_pipeline.process()
                return HomeGamePlayResponse(client_messages=[])
            else:
                # 场景切换激活失败，抛出包含具体错误信息的异常
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_detail,
                )

        case _:
            # 未知的操作类型，记录错误日志并抛出异常
            logger.error(f"未知的请求类型 = {payload.user_input.tag}, 不能处理！")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知的请求类型 = {payload.user_input.tag}, 不能处理！",
            )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/trans_dungeon/v1/", response_model=HomeTransDungeonResponse
)
async def home_trans_dungeon(
    payload: HomeTransDungeonRequest,
    game_server: CurrentGameServer,
) -> HomeTransDungeonResponse:
    """
    家园传送地下城接口，处理玩家从家园进入地下城的传送请求

    该接口负责将玩家从家园状态传送到地下城。在传送前会验证玩家状态和地下城可用性，
    然后初始化地下城的首次进入流程。这是玩家开始地下城探险的入口。

    Args:
        payload: 家园传送地下城请求对象
            - user_name: 用户名，用于标识玩家
        game_server: 游戏服务器实例，由依赖注入提供

    Returns:
        HomeTransDungeonResponse: 家园传送地下城响应对象
            - message: 包含请求信息的响应消息

    Raises:
        HTTPException(404): 玩家未登录、游戏实例不存在或没有可用的地下城
        HTTPException(400): 玩家当前不在家园状态
        HTTPException(500): 地下城初始化失败或服务器内部错误

    处理流程:
        1. 验证玩家是否在家园状态
        2. 检查当前地下城是否存在可用的关卡(stages)
        3. 初始化地下城首次进入流程
        4. 返回传送成功响应

    注意事项:
        - 玩家必须处于家园状态才能传送到地下城
        - 地下城必须包含至少一个可用关卡
        - 传送失败会抛出相应的HTTP异常

    示例:
        ```json
        {
            "user_name": "player1"
        }
        ```
    """

    logger.info(f"/api/home/trans_dungeon/v1/: user={payload.user_name}")

    # 验证前置条件并获取游戏实例
    rpg_game = await _validate_player_at_home(
        payload.user_name,
        game_server,
    )

    # 检查地下城是否存在可用的关卡
    if len(rpg_game.current_dungeon.stages) == 0:
        logger.warning(
            f"玩家 {payload.user_name} 尝试传送地下城失败: 当前地下城没有可用关卡"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="当前没有可用的地下城关卡",
        )

    # 执行地下城首次进入初始化
    # 初始化包括设置玩家状态、加载地下城场景、准备战斗环境等
    if not initialize_dungeon_first_entry(rpg_game):
        logger.error(f"玩家 {payload.user_name} 地下城初始化失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="地下城初始化失败",
        )

    # 返回传送成功响应
    return HomeTransDungeonResponse(
        message=payload.model_dump_json(),
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
