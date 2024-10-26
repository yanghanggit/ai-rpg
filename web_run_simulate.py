import requests
from ws_config import (
    WS_CONFIG,
    LoginRequest,
    LoginResponse,
    CreateResponse,
    CreateRequest,
    JoinRequest,
    JoinResponse,
    StartRequest,
    StartResponse,
    ExitRequest,
    ExitResponse,
    GameStateWrapper,
    GameState,
    ExecuteRequest,
    ExecuteResponse,
    WatchRequest,
    WatchResponse,
    CheckRequest,
    CheckResponse,
    FetchMessagesRequest,
    FetchMessagesResponse,
)
from loguru import logger
from typing import List


class GameClientContext:

    def __init__(self) -> None:
        self._user_name: str = ""
        self._game_name: str = ""
        self._selectable_actors: List[str] = []
        self._actor_name: str = ""
        self._input_enable = False

    def on_exit_game(self) -> None:
        self._game_name = ""
        self._selectable_actors = []
        self._actor_name = ""


###############################################################################################################################################
def _login(
    client_context: GameClientContext,
    state_wrapper: GameStateWrapper,
    default_user_name: str,
) -> None:

    if not state_wrapper.can_transition(GameState.LOGGED_IN):
        return

    input_username = input(
        f"客户端启动，需要输入用户名字(默认为 [{default_user_name}] ):"
    )

    assert default_user_name != ""
    if input_username == "" and default_user_name != "":
        input_username = default_user_name

    if input_username == "":
        logger.error("用户名不能为空!")
        return

    url_login = f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/login/"
    response = requests.post(
        url_login, json=LoginRequest(user_name=input_username).model_dump()
    )

    login_response = LoginResponse.model_validate(response.json())
    if login_response.error > 0:
        logger.warning(
            f"登录失败 = {login_response.user_name}, error = {login_response.error}, message = {login_response.message}"
        )
        return

    assert login_response.user_name == input_username

    state_wrapper.transition(GameState.LOGGED_IN)
    client_context._user_name = login_response.user_name
    logger.info(f"登录成功: {login_response.user_name}")


###############################################################################################################################################
def _create_game(
    client_context: GameClientContext, state_wrapper: GameStateWrapper
) -> None:

    assert client_context._user_name != ""

    if not state_wrapper.can_transition(GameState.GAME_CREATED):
        return

    input_game_name = input(
        f"{client_context._user_name} 准备创建一个游戏,请输入游戏的名字(建议是 World1/World2/World3 之一):"
    )

    url_create = f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/create/"
    response = requests.post(
        url_create,
        json=CreateRequest(
            user_name=client_context._user_name, game_name=input_game_name
        ).model_dump(),
    )

    create_response = CreateResponse.model_validate(response.json())
    if create_response.error > 0:
        logger.warning(
            f"创建失败 = {create_response.user_name}, error = {create_response.error}, message = {create_response.message}"
        )
        return

    assert create_response.user_name == client_context._user_name
    assert len(create_response.selectable_actors) > 0

    state_wrapper.transition(GameState.GAME_CREATED)
    client_context._game_name = create_response.game_name
    client_context._selectable_actors = create_response.selectable_actors
    logger.info(
        f"创建游戏: {create_response.user_name}, {create_response.game_name}, {create_response.selectable_actors}"
    )

    assert create_response.game_model is not None
    game_resource = create_response.game_model.model_dump_json()
    logger.info(f"游戏资源: \n{game_resource}")


###############################################################################################################################################
def _join_game(
    client_context: GameClientContext, state_wrapper: GameStateWrapper
) -> None:

    if not state_wrapper.can_transition(GameState.GAME_JOINED):
        return

    assert len(client_context._selectable_actors) > 0
    if len(client_context._selectable_actors) == 0:
        return

    while True:
        for index, actor_name in enumerate(client_context._selectable_actors):
            logger.warning(f"{index+1}. {actor_name}")

        input_actor_index = input(
            f"请[{client_context._user_name}]选择在[{client_context._game_name}]里要控制的角色(输入序号):"
        )
        if input_actor_index.isdigit():
            actor_index = int(input_actor_index)
            if actor_index > 0 and actor_index <= len(
                client_context._selectable_actors
            ):
                input_actor_name = client_context._selectable_actors[actor_index - 1]
                break
        else:
            logger.debug("输入错误，请重新输入。")

    url_join = f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/join/"
    response = requests.post(
        url_join,
        json=JoinRequest(
            user_name=client_context._user_name,
            game_name=client_context._game_name,
            actor_name=input_actor_name,
        ).model_dump(),
    )

    join_response = JoinResponse.model_validate(response.json())
    if join_response.error > 0:
        logger.warning(
            f"加入游戏失败 = {join_response.user_name}, error = {join_response.error}, message = {join_response.message}"
        )
        return

    assert join_response.user_name == client_context._user_name
    assert join_response.game_name == client_context._game_name

    state_wrapper.transition(GameState.GAME_JOINED)
    client_context._actor_name = join_response.actor_name
    logger.info(
        f"加入游戏: {join_response.user_name}, {join_response.game_name}, {join_response.actor_name}"
    )


###############################################################################################################################################
def _play(client_context: GameClientContext, state_wrapper: GameStateWrapper) -> None:

    if not state_wrapper.can_transition(GameState.PLAYING):
        return

    url_start = f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/start/"
    response = requests.post(
        url_start,
        json=StartRequest(
            user_name=client_context._user_name,
            game_name=client_context._game_name,
            actor_name=client_context._actor_name,
        ).model_dump(),
    )

    start_response = StartResponse.model_validate(response.json())
    if start_response.error > 0:
        logger.warning(
            f"开始游戏失败 = {start_response.user_name}, error = {start_response.error}, message = {start_response.message}"
        )
        return

    assert start_response.user_name == client_context._user_name
    assert start_response.game_name == client_context._game_name
    assert start_response.actor_name == client_context._actor_name

    state_wrapper.transition(GameState.PLAYING)
    logger.info(
        f"开始游戏: {start_response.user_name}, {start_response.game_name}, {start_response.actor_name}"
    )


###############################################################################################################################################
def _request_game_execute(
    client_context: GameClientContext,
    state_wrapper: GameStateWrapper,
    usr_input: List[str],
) -> None:

    assert state_wrapper.state == GameState.PLAYING

    # 推动游戏执行一次
    url_execute = f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/execute/"
    response = requests.post(
        url_execute,
        json=ExecuteRequest(
            user_name=client_context._user_name,
            game_name=client_context._game_name,
            actor_name=client_context._actor_name,
            user_input=usr_input,
        ).model_dump(),
    )

    execute_response = ExecuteResponse.model_validate(response.json())
    if execute_response.error > 0:
        logger.warning(f"执行游戏失败: {execute_response.message}")
        return

    client_context._input_enable = execute_response.player_input_enable


###############################################################################################################################################
def _request_fetch_messages(
    client_context: GameClientContext, state_wrapper: GameStateWrapper, fetch_count: int
) -> None:
    url_fetch_messages = (
        f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/fetch_messages/"
    )
    response = requests.post(
        url_fetch_messages,
        json=FetchMessagesRequest(
            user_name=client_context._user_name,
            game_name=client_context._game_name,
            actor_name=client_context._actor_name,
            index=-1,
            count=fetch_count,
        ).model_dump(),
    )

    fetch_messages_response = FetchMessagesResponse.model_validate(response.json())
    if fetch_messages_response.error > 0:
        logger.warning(
            f"观察游戏失败: {fetch_messages_response.user_name}, {fetch_messages_response.game_name}, {fetch_messages_response.actor_name}"
        )
        return

    for show_message in fetch_messages_response.messages:
        json_str = show_message.model_dump_json()
        logger.warning(json_str)


###############################################################################################################################################
def _web_player_input(
    client_context: GameClientContext, state_wrapper: GameStateWrapper
) -> None:

    assert client_context._user_name != ""
    assert client_context._game_name != ""
    assert client_context._actor_name != ""

    # 如果没有输入权限，就等待，推动游戏执行一次
    if not client_context._input_enable:
        while True:
            input(
                f"[{client_context._user_name}|{client_context._actor_name}]! 按任意键推动游戏执行一次:"
            )
            _request_game_execute(client_context, state_wrapper, [])
            _request_fetch_messages(
                client_context, state_wrapper, WS_CONFIG.SEND_MESSAGES_COUNT
            )
            break

        return

    # 正式输入
    while True:

        usr_input = input(
            f"[{client_context._user_name}|{client_context._actor_name}]:"
        )
        if usr_input == "":
            logger.warning("输入不能为空")
            continue

        if usr_input == "/quit":
            _requesting_exit(client_context, state_wrapper)
            break

        elif usr_input == "/watch" or usr_input == "/w":
            _requesting_watch(client_context, state_wrapper)
            break

        elif usr_input == "/check" or usr_input == "/c":
            _requesting_check(client_context, state_wrapper)
            break

        else:
            _request_game_execute(client_context, state_wrapper, [usr_input])
            _request_fetch_messages(
                client_context, state_wrapper, WS_CONFIG.SEND_MESSAGES_COUNT
            )
            break


###############################################################################################################################################
def _requesting_watch(
    client_context: GameClientContext, state_wrapper: GameStateWrapper
) -> None:
    url_watch = f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/watch/"
    response = requests.post(
        url_watch,
        json=WatchRequest(
            user_name=client_context._user_name,
            game_name=client_context._game_name,
            actor_name=client_context._actor_name,
        ).model_dump(),
    )

    watch_response = WatchResponse.model_validate(response.json())
    if watch_response.error > 0:
        logger.warning(
            f"观察游戏失败: {watch_response.user_name}, {watch_response.game_name}, {watch_response.actor_name}"
        )
        return

    logger.warning(
        f"观察游戏: {watch_response.user_name}, {watch_response.game_name}, {watch_response.actor_name}\n{watch_response.message}"
    )


###############################################################################################################################################
def _requesting_check(
    client_context: GameClientContext, state_wrapper: GameStateWrapper
) -> None:
    url_check = f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/check/"
    response = requests.post(
        url_check,
        json=CheckRequest(
            user_name=client_context._user_name,
            game_name=client_context._game_name,
            actor_name=client_context._actor_name,
        ).model_dump(),
    )

    check_response = CheckResponse.model_validate(response.json())
    if check_response.error > 0:
        logger.warning(
            f"检查游戏失败: {check_response.user_name}, {check_response.game_name}, {check_response.actor_name}"
        )
        return

    logger.warning(
        f"检查游戏: {check_response.user_name}, {check_response.game_name}, {check_response.actor_name}\n{check_response.message}"
    )


###############################################################################################################################################
def _requesting_exit(
    client_context: GameClientContext, state_wrapper: GameStateWrapper
) -> None:

    if not state_wrapper.can_transition(GameState.REQUESTING_EXIT):
        return
    url_exit = f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/exit/"
    response = requests.post(
        url_exit,
        json=ExitRequest(
            user_name=client_context._user_name, game_name=client_context._game_name
        ).model_dump(),
    )

    exit_response = ExitResponse.model_validate(response.json())
    if exit_response.error > 0:
        logger.warning(
            f"退出游戏失败: {exit_response.user_name}, {exit_response.game_name}"
        )
        return

    state_wrapper.transition(GameState.REQUESTING_EXIT)

    # 清理数据
    logger.info(
        f"退出游戏: {exit_response.user_name}, {client_context._game_name}, {client_context._actor_name } 清除相关数据"
    )
    client_context.on_exit_game()


###############################################################################################################################################


def web_run() -> None:

    client_state = GameStateWrapper(GameState.UNLOGGED)
    client_context = GameClientContext()
    default_user_name = "北京柏林互动科技有限公司"

    while True:

        match client_state.state:
            case GameState.UNLOGGED:
                _login(client_context, client_state, default_user_name)

            case GameState.LOGGED_IN:
                _create_game(client_context, client_state)

            case GameState.GAME_CREATED:
                _join_game(client_context, client_state)

            case GameState.GAME_JOINED:
                _play(client_context, client_state)

            case GameState.PLAYING:
                _web_player_input(client_context, client_state)

            case GameState.REQUESTING_EXIT:
                _create_game(client_context, client_state)

            case _:
                assert False, "不应该到这里"


if __name__ == "__main__":

    web_run()
