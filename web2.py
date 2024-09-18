import requests
from ws_config import (
    WS_CONFIG,
    LoginData,
    CreateData,
    JoinData,
    StartData,
    ExitData,
    GameStateWrapper,
    GameState,
)
from loguru import logger
from typing import List

###############################################################################################################################################


class GameClientContext:

    def __init__(self, user_name: str) -> None:
        assert user_name != ""
        self._user_name: str = user_name
        self._game_name: str = ""
        self._selectable_actor_names: List[str] = []
        self._ctrl_actor_name: str = ""


###############################################################################################################################################
def next_login_state(
    client_context: GameClientContext, stage_wrapper: GameStateWrapper
) -> None:

    if not stage_wrapper.can_transition(GameState.LOGIN):
        return

    input_username = input(
        f"客户端启动，需要输入用户名字(默认为 [{client_context._user_name}] ):"
    )
    if input_username == "" and client_context._user_name != "":
        input_username = client_context._user_name

    if input_username == "":
        logger.error("用户名不能为空!")
        return

    url_login = f"http://{WS_CONFIG.Host.value}:{WS_CONFIG.Port.value}/login/"
    response = requests.post(
        url_login, json=LoginData(user_name=input_username).model_dump()
    )

    login_response = LoginData.model_validate(response.json())
    if not login_response.response:
        logger.warning(f"登录失败 = {login_response.user_name}")
        return

    stage_wrapper.transition(GameState.LOGIN)
    client_context._user_name = input_username
    logger.info(f"登录成功: {login_response.user_name}")


###############################################################################################################################################
def next_create_state(
    client_context: GameClientContext, stage_wrapper: GameStateWrapper
) -> None:

    assert client_context._user_name != ""

    if not stage_wrapper.can_transition(GameState.CREATE):
        return

    input_game_name = input(
        f"{client_context._user_name} 准备创建一个游戏,请输入游戏的名字(建议是 World1/World2/World3 之一):"
    )

    url_create = f"http://{WS_CONFIG.Host.value}:{WS_CONFIG.Port.value}/create/"
    response = requests.post(
        url_create,
        json=CreateData(
            user_name=client_context._user_name, game_name=input_game_name
        ).model_dump(),
    )

    create_response = CreateData.model_validate(response.json())
    if not create_response.response:
        logger.warning(
            f"{create_response.user_name} 创建失败 = {create_response.game_name}"
        )
        return

    stage_wrapper.transition(GameState.CREATE)
    client_context._game_name = input_game_name
    assert create_response.user_name == client_context._user_name
    client_context._selectable_actor_names = create_response.selectable_actor_names
    logger.info(
        f"创建游戏: {create_response.user_name}, {create_response.game_name}, {create_response.selectable_actor_names}"
    )


###############################################################################################################################################
def next_join_state(
    client_context: GameClientContext, stage_wrapper: GameStateWrapper
) -> None:

    if not stage_wrapper.can_transition(GameState.JOIN):
        return

    input_actor_name: str = ""

    if len(client_context._selectable_actor_names) > 0:

        while True:
            for index, actor_name in enumerate(client_context._selectable_actor_names):
                logger.warning(f"{index+1}. {actor_name}")

            input_actor_index = input(
                f"请[{client_context._user_name}]选择在[{client_context._game_name}]里要控制的角色(输入序号):"
            )
            if input_actor_index.isdigit():
                actor_index = int(input_actor_index)
                if actor_index > 0 and actor_index <= len(
                    client_context._selectable_actor_names
                ):
                    input_actor_name = client_context._selectable_actor_names[
                        actor_index - 1
                    ]
                    break
            else:
                logger.debug("输入错误，请重新输入。")

    else:
        while True:
            input(
                f"[{client_context._game_name}]在[{client_context._game_name}]没有可以控制的角色，只能作为观察者"
            )
            break

    url_join = f"http://{WS_CONFIG.Host.value}:{WS_CONFIG.Port.value}/join/"
    response = requests.post(
        url_join,
        json=JoinData(
            user_name=client_context._user_name,
            game_name=client_context._game_name,
            ctrl_actor_name=input_actor_name,
        ).model_dump(),
    )

    join_response = JoinData.model_validate(response.json())
    if not join_response.response:
        logger.warning(
            f"加入游戏失败: {join_response.user_name}, {join_response.game_name}, {join_response.ctrl_actor_name}"
        )
        return

    stage_wrapper.transition(GameState.JOIN)
    assert join_response.user_name == client_context._user_name
    assert join_response.game_name == client_context._game_name
    client_context._ctrl_actor_name = input_actor_name
    logger.info(
        f"加入游戏: {join_response.user_name}, {join_response.game_name}, {join_response.ctrl_actor_name}"
    )


###############################################################################################################################################
def next_start_state(
    client_context: GameClientContext, stage_wrapper: GameStateWrapper
) -> None:

    if not stage_wrapper.can_transition(GameState.START):
        return

    url_start = f"http://{WS_CONFIG.Host.value}:{WS_CONFIG.Port.value}/start/"
    response = requests.post(
        url_start,
        json=StartData(
            user_name=client_context._user_name,
            game_name=client_context._game_name,
            ctrl_actor_name=client_context._ctrl_actor_name,
        ).model_dump(),
    )

    start_response = StartData.model_validate(response.json())
    if not start_response.response:
        logger.warning(
            f"开始游戏失败: {start_response.user_name}, {start_response.game_name}, {start_response.ctrl_actor_name}"
        )
        return

    stage_wrapper.transition(GameState.START)
    assert start_response.user_name == client_context._user_name
    assert start_response.game_name == client_context._game_name
    assert start_response.ctrl_actor_name == client_context._ctrl_actor_name
    logger.info(
        f"开始游戏: {start_response.user_name}, {start_response.game_name}, {start_response.ctrl_actor_name}"
    )


###############################################################################################################################################
def next_exit_state(
    client_context: GameClientContext, stage_wrapper: GameStateWrapper
) -> None:

    if not stage_wrapper.can_transition(GameState.EXIT):
        return
    url_exit = f"http://{WS_CONFIG.Host.value}:{WS_CONFIG.Port.value}/exit/"
    response = requests.post(
        url_exit,
        json=ExitData(
            user_name=client_context._user_name, game_name=client_context._game_name
        ).model_dump(),
    )

    exit_response = ExitData.model_validate(response.json())
    if not exit_response.response:
        logger.warning(
            f"退出游戏失败: {exit_response.user_name}, {exit_response.game_name}"
        )
        return

    stage_wrapper.transition(GameState.EXIT)

    # 清理数据
    logger.info(f"退出游戏: {exit_response.user_name}, {client_context._game_name}, {client_context._ctrl_actor_name } 清除相关数据")
    client_context._game_name = ""
    client_context._selectable_actor_names = []
    client_context._ctrl_actor_name = ""
    


###############################################################################################################################################


def web_run() -> None:

    run = True
    client_state = GameStateWrapper(GameState.LOGOUT)
    client_context = GameClientContext("北京柏林互动科技有限公司")

    while run:

        match client_state.state:
            case GameState.LOGOUT:
                next_login_state(client_context, client_state)

            case GameState.LOGIN:
                next_create_state(client_context, client_state)

            case GameState.CREATE:
                next_join_state(client_context, client_state)

            case GameState.JOIN:
                next_start_state(client_context, client_state)

            case GameState.START:
                next_exit_state(client_context, client_state)

            case GameState.EXIT:
                next_create_state(client_context, client_state)

            case _:
                assert False, "不应该到这里"

    logger.info("退出循环")


if __name__ == "__main__":

    web_run()
