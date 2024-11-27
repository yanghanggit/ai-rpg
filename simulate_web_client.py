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
    ExecuteRequest,
    ExecuteResponse,
    SurveyStageRequest,
    SurveyStageResponse,
    StatusInventoryCheckRequest,
    StatusInventoryCheckResponse,
    FetchMessagesRequest,
    FetchMessagesResponse,
    RetrieveActorArchivesRequest,
    RetrieveActorArchivesResponse,
    RetrieveStageArchivesRequest,
    RetrieveStageArchivesResponse,
    APIEndpointsConfigRequest,
    APIEndpointsConfigResponse,
)
from loguru import logger
from typing import Final, List
import datetime
from my_models.config_models import APIEndpointsConfigModel
from my_services.game_state_manager import GameStateController, GameState


FETCH_MESSAGES_COUNT: Final[int] = 9999  # 多要一点得了。


class SimuWebAPP:

    def __init__(self) -> None:
        self._user_name: str = ""
        self._game_name: str = ""
        self._selectable_actors: List[str] = []
        self._actor_name: str = ""
        self._turn_player_actor = ""
        self._api_endpoints = APIEndpointsConfigModel()

    def on_exit_game(self) -> None:
        self._game_name = ""
        self._selectable_actors = []
        self._actor_name = ""

    @property
    def player_input_enable(self) -> bool:
        return self._actor_name != "" and self._actor_name == self._turn_player_actor

    @property
    def api_endpoints(self) -> APIEndpointsConfigModel:
        return self._api_endpoints

    @api_endpoints.setter
    def api_endpoints(self, value: APIEndpointsConfigModel) -> None:
        self._api_endpoints = value
        logger.info(f"获取API路由成功: {self._api_endpoints.model_dump_json()}")


###############################################################################################################################################
def _api_endpoints(
    client_context: SimuWebAPP, state_manager: GameStateController
) -> None:

    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response = requests.post(
        f"""http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/api_endpoints/""",
        json=APIEndpointsConfigRequest(content=f"time = {time}").model_dump(),
    )

    api_routes_config_response = APIEndpointsConfigResponse.model_validate(
        response.json()
    )
    if api_routes_config_response.error > 0:
        assert False, f"获取API路由失败: {api_routes_config_response.message}"
        return

    client_context.api_endpoints = api_routes_config_response.api_endpoints


###############################################################################################################################################
def _login(
    client_context: SimuWebAPP,
    state_manager: GameStateController,
    default_user_name: str,
) -> None:

    if not state_manager.can_transition(GameState.LOGGED_IN):
        return

    input_username = input(f"客户端启动，需要输入用户(默认为 [{default_user_name}] ):")

    assert default_user_name != ""
    if input_username == "" and default_user_name != "":
        input_username = default_user_name

    if input_username == "":
        logger.error("不能为空!")
        return

    response = requests.post(
        client_context.api_endpoints.LOGIN,
        json=LoginRequest(user_name=input_username).model_dump(),
    )

    login_response = LoginResponse.model_validate(response.json())
    if login_response.error > 0:
        logger.warning(
            f"登录失败 = {login_response.user_name}, error = {login_response.error}, message = {login_response.message}"
        )
        return

    assert login_response.user_name == input_username

    state_manager.transition(GameState.LOGGED_IN)
    client_context._user_name = login_response.user_name
    logger.info(f"登录成功: {login_response.user_name}")


###############################################################################################################################################
def _create_game(
    client_context: SimuWebAPP, state_manager: GameStateController
) -> None:

    assert client_context._user_name != ""

    if not state_manager.can_transition(GameState.GAME_CREATED):
        return

    input_game_name = input(
        f"{client_context._user_name} 准备创建一个游戏,请输入游戏的(建议是 World1/World2/World3/World4/World5 之一):"
    )

    response = requests.post(
        client_context.api_endpoints.CREATE,
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

    state_manager.transition(GameState.GAME_CREATED)
    client_context._game_name = create_response.game_name
    client_context._selectable_actors = create_response.selectable_actors
    logger.info(
        f"创建游戏: {create_response.user_name}, {create_response.game_name}, {create_response.selectable_actors}"
    )

    assert create_response.game_model is not None
    game_resource = create_response.game_model.model_dump_json()
    logger.info(f"游戏资源: \n{game_resource}")


###############################################################################################################################################
def _join_game(client_context: SimuWebAPP, state_manager: GameStateController) -> None:

    if not state_manager.can_transition(GameState.GAME_JOINED):
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

    response = requests.post(
        client_context.api_endpoints.JOIN,
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

    state_manager.transition(GameState.GAME_JOINED)
    client_context._actor_name = join_response.actor_name
    logger.info(
        f"加入游戏: {join_response.user_name}, {join_response.game_name}, {join_response.actor_name}"
    )


###############################################################################################################################################
def _play(client_context: SimuWebAPP, state_manager: GameStateController) -> None:

    if not state_manager.can_transition(GameState.PLAYING):
        return

    response = requests.post(
        client_context.api_endpoints.START,
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

    state_manager.transition(GameState.PLAYING)
    logger.info(
        f"开始游戏: {start_response.user_name}, {start_response.game_name}, {start_response.actor_name}"
    )


###############################################################################################################################################
def _request_game_execute(
    client_context: SimuWebAPP,
    state_manager: GameStateController,
    usr_input: List[str],
) -> None:

    assert state_manager.state == GameState.PLAYING

    # 推动游戏执行一次
    response = requests.post(
        client_context.api_endpoints.EXECUTE,
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

    # client_context._input_enable = execute_response.turn_player == client_context._actor_name
    client_context._turn_player_actor = execute_response.turn_player_actor


###############################################################################################################################################
def _request_fetch_messages(
    client_context: SimuWebAPP,
    state_manager: GameStateController,
    fetch_begin_index: int,
    fetch_count: int,
) -> None:

    response = requests.post(
        client_context.api_endpoints.FETCH_MESSAGES,
        json=FetchMessagesRequest(
            user_name=client_context._user_name,
            game_name=client_context._game_name,
            actor_name=client_context._actor_name,
            index=fetch_begin_index,  # 测试用
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
        logger.debug(json_str)


###############################################################################################################################################
def _web_player_input(
    client_context: SimuWebAPP, state_manager: GameStateController
) -> None:

    assert client_context._user_name != ""
    assert client_context._game_name != ""
    assert client_context._actor_name != ""

    # 如果没有输入权限，就等待，推动游戏执行一次
    if not client_context.player_input_enable:
        while True:
            input(
                f"[{client_context._user_name}|{client_context._actor_name}]! 按任意键推动游戏执行一次:"
            )
            _request_game_execute(client_context, state_manager, [])
            _request_fetch_messages(
                client_context, state_manager, 0, FETCH_MESSAGES_COUNT
            )
            break

        return

    # 正式输入
    while True:

        usr_input = input(
            f"[{client_context._user_name}|{client_context._actor_name}]:"
        )
        # if usr_input == "":
        #     logger.warning("输入不能为空")
        #     continue

        if usr_input == "/quit":
            _requesting_exit(client_context, state_manager)
            break

        elif usr_input == "/survey_stage_action" or usr_input == "/ssa":
            _requesting_watch(client_context, state_manager)
            break

        elif usr_input == "/status_inventory_check_action" or usr_input == "/sica":
            _requesting_check(client_context, state_manager)
            break

        elif usr_input == "/retrieve_actor_archives" or usr_input == "/raa":
            _requesting_retrieve_actor_archives(client_context, state_manager)
            break

        elif usr_input == "/retrieve_stage_archives" or usr_input == "/rsa":
            _requesting_retrieve_stage_archives(client_context, state_manager)
            break

        else:
            _request_game_execute(client_context, state_manager, [usr_input])
            _request_fetch_messages(
                client_context, state_manager, 0, FETCH_MESSAGES_COUNT
            )
            break


###############################################################################################################################################
def _requesting_watch(
    client_context: SimuWebAPP, state_manager: GameStateController
) -> None:

    response = requests.post(
        client_context.api_endpoints.SURVEY_STAGE_ACTION,
        json=SurveyStageRequest(
            user_name=client_context._user_name,
            game_name=client_context._game_name,
            actor_name=client_context._actor_name,
        ).model_dump(),
    )

    watch_response = SurveyStageResponse.model_validate(response.json())
    if watch_response.error > 0:
        logger.warning(
            f"观察游戏失败: {watch_response.user_name}, {watch_response.game_name}, {watch_response.actor_name}"
        )
        return

    logger.warning(f"观察游戏: {watch_response.model_dump_json()}")


###############################################################################################################################################
def _requesting_check(
    client_context: SimuWebAPP, state_manager: GameStateController
) -> None:

    response = requests.post(
        client_context.api_endpoints.STATUS_INVENTORY_CHECK_ACTION,
        json=StatusInventoryCheckRequest(
            user_name=client_context._user_name,
            game_name=client_context._game_name,
            actor_name=client_context._actor_name,
        ).model_dump(),
    )

    check_response = StatusInventoryCheckResponse.model_validate(response.json())
    if check_response.error > 0:
        logger.warning(
            f"检查游戏失败: {check_response.user_name}, {check_response.game_name}, {check_response.actor_name}"
        )
        return

    logger.warning(f"""检查游戏:\n{check_response.model_dump_json()}""")


###############################################################################################################################################
def _requesting_retrieve_actor_archives(
    client_context: SimuWebAPP, state_manager: GameStateController
) -> None:

    response = requests.post(
        client_context.api_endpoints.RETRIEVE_ACTOR_ARCHIVES,
        json=RetrieveActorArchivesRequest(
            user_name=client_context._user_name,
            game_name=client_context._game_name,
            actor_name=client_context._actor_name,
        ).model_dump(),
    )

    actor_archives_response = RetrieveActorArchivesResponse.model_validate(
        response.json()
    )
    if actor_archives_response.error > 0:
        logger.warning(
            f"获取角色档案失败: {actor_archives_response.user_name}, {actor_archives_response.game_name}, {actor_archives_response.actor_name}"
        )
        return

    logger.warning(f"获取角色档案: {actor_archives_response.model_dump_json()}")


###############################################################################################################################################
def _requesting_retrieve_stage_archives(
    client_context: SimuWebAPP, state_manager: GameStateController
) -> None:

    response = requests.post(
        client_context.api_endpoints.RETRIEVE_STAGE_ARCHIVES,
        json=RetrieveStageArchivesRequest(
            user_name=client_context._user_name,
            game_name=client_context._game_name,
            actor_name=client_context._actor_name,
        ).model_dump(),
    )

    stage_archives_response = RetrieveStageArchivesResponse.model_validate(
        response.json()
    )
    if stage_archives_response.error > 0:
        logger.warning(
            f"获取舞台档案失败: {stage_archives_response.user_name}, {stage_archives_response.game_name}, {stage_archives_response.actor_name}"
        )
        return

    logger.warning(f"获取舞台档案: {stage_archives_response.model_dump_json()}")


###############################################################################################################################################
def _requesting_exit(
    client_context: SimuWebAPP, state_manager: GameStateController
) -> None:

    if not state_manager.can_transition(GameState.REQUESTING_EXIT):
        return

    response = requests.post(
        client_context.api_endpoints.EXECUTE,
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

    state_manager.transition(GameState.REQUESTING_EXIT)

    # 清理数据
    logger.info(
        f"退出游戏: {exit_response.user_name}, {client_context._game_name}, {client_context._actor_name } 清除相关数据"
    )
    client_context.on_exit_game()


###############################################################################################################################################


def web_run() -> None:

    client_state = GameStateController(GameState.UNLOGGED)
    client_context = SimuWebAPP()
    default_user_name = "web_player"

    while True:

        match client_state.state:
            case GameState.UNLOGGED:
                _api_endpoints(client_context, client_state)
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
