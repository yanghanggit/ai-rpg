import datetime
import re  
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel
from auxiliary.multi_players_game import MultiplayersGame
from auxiliary.player_command import PlayerLogin
from auxiliary.player_proxy import create_player_proxy, get_player_proxy, remove_player_proxy, TEST_CLIENT_SHOW_MESSAGE_COUNT
from main_utils import create_rpg_game
from rpg_game import RPGGame
from auxiliary.player_proxy import PlayerProxy
from systems.check_status_action_system import CheckStatusActionHelper, ActorCheckStatusEvent
from systems.perception_action_system import PerceptionActionHelper, ActorPerceptionEvent

class TextInput(BaseModel):
    text_input: str

class TupleModel(BaseModel):  
    who: str 
    what: str

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static") 

multiplayersgames: dict[str, MultiplayersGame] = {}

async def create(clientip: str) -> list[TupleModel]:
    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    worldname = "World2"
    rpg_game = create_rpg_game(worldname)
    if rpg_game is None:
        logger.error("create_rpg_game 失败。")
        return []

    #
    game = MultiplayersGame(clientip, clientip, rpg_game)
    if game is not None:
        global multiplayersgames
        multiplayersgames[clientip] = game
        multiplayersgames[clientip].rpggame.extendedcontext.user_ips.append(clientip)
        create_player_proxy(clientip)

    messages: list[TupleModel] = []
    messages.append(TupleModel(who=clientip, what=f"创建房间IP:{clientip}."))

    return messages

def parse_join_multi_game_params(command: str) -> str:
    
    # 使用正则表达式匹配@之后的内容  
    # 这个正则表达式匹配@符号后面的非空白字符  
    match = re.search(r'@(\S+)', command)  
    
    if match:  
        content = match.group(1)  # 使用group(1)获取第一个括号中匹配的内容  
        return content
    else:  
        logger.debug("在字符串中没有找到匹配的内容") 
        return ""

async def join(clientip: str, hostip: str) -> list[TupleModel]:
    messages: list[TupleModel] = []
    for userip, game in multiplayersgames.copy().items():
        if game.hostname == hostip:
            client_game = MultiplayersGame(clientip, hostip, game.rpggame)
            multiplayersgames[clientip] = client_game
            messages.append(TupleModel(who=clientip, what=f"加入房间IP:{hostip}成功."))
            multiplayersgames[clientip].rpggame.extendedcontext.user_ips.append(clientip)
            create_player_proxy(clientip)

    if len(messages) == 0:
        messages.append(TupleModel(who=clientip, what=f"加入房间IP:{hostip}失败,请检查房间IP."))

    return messages

async def pick_actor(clientip: str, actorname: str) -> list[TupleModel]:
    global multiplayersgames
    playerproxy = get_player_proxy(clientip)
    assert playerproxy is not None
    playerstartcmd = PlayerLogin("/player-login", multiplayersgames[clientip].rpggame, playerproxy, actorname)
    playerstartcmd.execute()
    await multiplayersgames[clientip].rpggame.async_execute()
    logger.debug(f"pick actor finish")

    messages: list[TupleModel] = []
    messages.append(TupleModel(who=clientip, what=f"选择了角色:{actorname}"))

    return messages


async def request_game_messages(clientip: str) -> list[TupleModel]:
    messages: list[TupleModel] = []
    playerproxy = get_player_proxy(clientip)
    if playerproxy is not None:
        for message in playerproxy.client_messages[-TEST_CLIENT_SHOW_MESSAGE_COUNT:]:
            messages.append(TupleModel(who=message[0], what=message[1]))
    else:
        messages.append(TupleModel(who=clientip, what="请先创建游戏或加入游戏."))

    return messages


async def quitgame(clientip: str) -> list[TupleModel]:
    quitclient = multiplayersgames.pop(clientip, None)
    if quitclient is not None:
        logger.debug(f"User IP:{clientip} quit a game.")
        proxy = get_player_proxy(clientip)
        assert proxy is not None
        remove_player_proxy(proxy)
        quitclient.rpggame.exited = True
        quitclient.rpggame.exit()

    messages: list[TupleModel] = []
    messages.append(TupleModel(who=clientip, what="Quit Success"))

    return messages

############################################################################################################
# player 可以是立即模式
async def imme_handle_perception(rpg_game: RPGGame, playerproxy: PlayerProxy) -> None:
    context = rpg_game.extendedcontext
    playerentity = context.get_player_entity(playerproxy.name)
    if playerentity is None:
        return
    #
    helper = PerceptionActionHelper(context)
    helper.perception(playerentity)
    #
    safe_actor_name = context.safe_get_entity_name(playerentity)
    stageentity = context.safe_get_stage_entity(playerentity)
    assert stageentity is not None
    safe_stage_name = context.safe_get_entity_name(stageentity)
    #
    event = ActorPerceptionEvent(safe_actor_name, safe_stage_name, helper.actors_in_stage, helper.props_in_stage)
    message = event.to_actor(safe_actor_name, context)
    #
    playerproxy.add_actor_message(safe_actor_name, message)
############################################################################################################
# player 可以是立即模式
async def imme_handle_check_status(rpg_game: RPGGame, playerproxy: PlayerProxy) -> None:
    context = rpg_game.extendedcontext
    playerentity = context.get_player_entity(playerproxy.name)
    if playerentity is None:
        return
    #
    context = rpg_game.extendedcontext
    helper = CheckStatusActionHelper(context)
    helper.check_status(playerentity)
    #
    safename = context.safe_get_entity_name(playerentity)
    #
    event = ActorCheckStatusEvent(safename, helper.props, helper.health, helper.actor_components, helper.events)
    message = event.to_actor(safename, context)
    playerproxy.add_actor_message(safename, message)
############################################################################################################

async def playerinput(clientip: str, command: str) -> list[TupleModel]:
    #
    playerproxy = get_player_proxy(clientip)
    assert playerproxy is not None
    playerproxy._inputs.append(command)
    
    #
    if "/checkstatus" in command:
        await imme_handle_check_status(multiplayersgames[clientip].rpggame, playerproxy)
    elif "/perception" in command:
        await imme_handle_perception(multiplayersgames[clientip].rpggame, playerproxy)
    else:
        await multiplayersgames[clientip].rpggame.async_execute()

    messages: list[TupleModel] = []
    messages.append(TupleModel(who=clientip, what=f"发送 {command}"))

    return messages

async def main(clientip: str , command: str) -> list[TupleModel]:
    if "/quit" in command:
        return await quitgame(clientip)
    elif "/create" in command:
        return await create(clientip)
    elif "/join" in command:
        hostip = parse_join_multi_game_params(command)
        return await join(clientip, hostip)
    elif "/pickactor" in command:
        actorname = parse_join_multi_game_params(command)
        return await pick_actor(clientip, actorname)
    elif "/run" in command:
        return await request_game_messages(clientip)
    else:
        return await playerinput(clientip, command)

@app.get("/")
async def read_root(request: Request) -> templates.TemplateResponse: # type: ignore
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/submit")
async def submit_form(request: Request) -> JSONResponse:
    json_data = await request.json()
    input_data: TextInput = TextInput(**json_data) 
    user_command: str = str(input_data.text_input)
    assert request.client is not None
    user_ip = request.client.host
    results = await main(user_ip, user_command)
    messages = [message_model.dict() for message_model in results]
    return JSONResponse(content={"command": user_command, "messages": messages})  

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)