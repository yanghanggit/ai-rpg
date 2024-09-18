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


def next_login_state(stage_wrapper: GameStateWrapper, default_user_name: str) -> None:

    if not stage_wrapper.can_transition(GameState.LOGIN):
        return

    input_username = input(
        f"准备login,请输入用户的名字(默认为 [{default_user_name}] ):"
    )
    if input_username == "":
        input_username = default_user_name

    url_login = f"http://{WS_CONFIG.Host.value}:{WS_CONFIG.Port.value}/login/"
    response = requests.post(
        url_login, json=LoginData(username=input_username).model_dump()
    )
    login_response = LoginData.model_validate(response.json())
    if login_response.response:
        stage_wrapper.transition(GameState.LOGIN)
    else:
        logger.info("登录失败")


###############################################################################################################################################
def next_create_state(stage_wrapper: GameStateWrapper) -> None:

    if not stage_wrapper.can_transition(GameState.CREATE):
        return

    input_game_name = input("准备create,请输入游戏的名字:")

    url_create = f"http://{WS_CONFIG.Host.value}:{WS_CONFIG.Port.value}/create/"
    response = requests.post(
        url_create,
        json=CreateData(username="test", game_name=input_game_name).model_dump(),
    )
    create_response = CreateData.model_validate(response.json())
    if create_response.response:
        stage_wrapper.transition(GameState.CREATE)
    else:
        logger.info(f"创建失败 = {create_response.game_name}")


###############################################################################################################################################
def next_join_state(stage_wrapper: GameStateWrapper) -> None:

    if not stage_wrapper.can_transition(GameState.JOIN):
        return

    input_actor_name = input("准备join,请输入actor的名字:")
    url_join = f"http://{WS_CONFIG.Host.value}:{WS_CONFIG.Port.value}/join/"
    response = requests.post(
        url_join,
        json=JoinData(
            username="test", game_name="game1", actor_name=input_actor_name
        ).model_dump(),
    )
    join_response = JoinData.model_validate(response.json())
    if join_response.response:
        stage_wrapper.transition(GameState.JOIN)
    else:
        logger.info(f"加入失败 = {join_response.actor_name}")


###############################################################################################################################################
def next_start_state(stage_wrapper: GameStateWrapper) -> None:

    if not stage_wrapper.can_transition(GameState.START):
        return

    url_start = f"http://{WS_CONFIG.Host.value}:{WS_CONFIG.Port.value}/start/"
    response = requests.post(
        url_start, json=StartData(username="test", game_name="game1").model_dump()
    )
    start_response = StartData.model_validate(response.json())
    if start_response.response:
        stage_wrapper.transition(GameState.START)
    else:
        logger.info("开始失败")


###############################################################################################################################################
def next_exit_state(stage_wrapper: GameStateWrapper) -> None:

    if not stage_wrapper.can_transition(GameState.EXIT):
        return
    url_exit = f"http://{WS_CONFIG.Host.value}:{WS_CONFIG.Port.value}/exit/"
    response = requests.post(
        url_exit, json=ExitData(username="test", game_name="game1").model_dump()
    )
    exit_response = ExitData.model_validate(response.json())
    if exit_response.response:
        stage_wrapper.transition(GameState.EXIT)
    else:
        logger.info("退出失败")


###############################################################################################################################################


def web_run() -> None:

    run = True
    client_state = GameStateWrapper(GameState.LOGOUT)

    while run:

        match client_state.state:
            case GameState.LOGOUT:
                next_login_state(client_state, "北京柏林互动科技有限公司")

            case GameState.LOGIN:
                next_create_state(client_state)

            case GameState.CREATE:
                next_join_state(client_state)

            case GameState.JOIN:
                next_start_state(client_state)

            case GameState.START:
                next_exit_state(client_state)

            case GameState.EXIT:
                next_create_state(client_state)

            case _:
                assert False, "不应该到这里"

    logger.info("退出循环")


if __name__ == "__main__":

    web_run()
