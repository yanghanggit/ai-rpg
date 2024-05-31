import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel
from auxiliary.player_input_command import PlayerCommandLogin
from auxiliary.player_proxy import create_player_proxy, get_player_proxy, remove_player_proxy, TEST_CLIENT_SHOW_MESSAGE_COUNT
from main_utils import create_rpg_game_then_build
from rpg_game import RPGGame
from auxiliary.player_proxy import PlayerProxy
from systems.check_status_action_system import CheckStatusActionHelper, NPCCheckStatusEvent
from systems.perception_action_system import PerceptionActionHelper, NPCPerceptionEvent

class TextInput(BaseModel):
    text_input: str

class TupleModel(BaseModel):  
    who: str 
    what: str

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static") 

rpggame: dict[str, RPGGame] = {}

async def start(clientip: str) -> list[TupleModel]:
    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    worldname = "World2"
    game = create_rpg_game_then_build(worldname)
    if game is not None:
        global rpggame
        rpggame[clientip] = game
        rpggame[clientip].extendedcontext.user_ip = clientip
        logger.debug(f"User IP:{clientip} start a game.")

    #await rpggame[clientip].async_execute()

    messages: list[TupleModel] = []
    messages.append(TupleModel(who=clientip, what="Start Success"))

    return messages

async def login(clientip: str) -> list[TupleModel]:
    create_player_proxy(clientip)
    playerproxy = get_player_proxy(clientip)
    assert playerproxy is not None
    playerstartcmd = PlayerCommandLogin("/player-login", rpggame[clientip], playerproxy, "无名的复活者")
    playerstartcmd.execute()
    await rpggame[clientip].async_execute()

    messages: list[TupleModel] = []
    for message in playerproxy.clientmessages[-TEST_CLIENT_SHOW_MESSAGE_COUNT:]:
        messages.append(TupleModel(who=message[0], what=message[1]))

    return messages

async def quitgame(clientip: str) -> list[TupleModel]:
    quitclient = rpggame.pop(clientip, None)
    if quitclient is not None:
        logger.debug(f"User IP:{clientip} quit a game.")
        proxy = get_player_proxy(clientip)
        assert proxy is not None
        remove_player_proxy(proxy)
        quitclient.exited = True
        quitclient.exit()

    messages: list[TupleModel] = []
    messages.append(TupleModel(who=clientip, what="Quit Success"))

    return messages

# async def run():
#     await rpggame.async_execute()

############################################################################################################
# player 可以是立即模式
async def imme_handle_perception(rpg_game: RPGGame, playerproxy: PlayerProxy) -> None:
    context = rpg_game.extendedcontext
    playerentity = context.getplayer(playerproxy.name)
    if playerentity is None:
        return
    #
    helper = PerceptionActionHelper(context)
    helper.perception(playerentity)
    #
    safe_npc_name = context.safe_get_entity_name(playerentity)
    stageentity = context.safe_get_stage_entity(playerentity)
    assert stageentity is not None
    safe_stage_name = context.safe_get_entity_name(stageentity)
    #
    event = NPCPerceptionEvent(safe_npc_name, safe_stage_name, helper.npcs_in_stage, helper.props_in_stage)
    message = event.tonpc(safe_npc_name, context)
    #
    playerproxy.add_npc_message(safe_npc_name, message)
############################################################################################################
# player 可以是立即模式
async def imme_handle_check_status(rpg_game: RPGGame, playerproxy: PlayerProxy) -> None:
    context = rpg_game.extendedcontext
    playerentity = context.getplayer(playerproxy.name)
    if playerentity is None:
        return
    #
    context = rpg_game.extendedcontext
    helper = CheckStatusActionHelper(context)
    helper.check_status(playerentity)
    #
    safename = context.safe_get_entity_name(playerentity)
    #
    event = NPCCheckStatusEvent(safename, helper.props, helper.health, helper.role_components, helper.events)
    message = event.tonpc(safename, context)
    playerproxy.add_npc_message(safename, message)
############################################################################################################

async def playerinput(clientip: str, command: str) -> list[TupleModel]:
    #
    playerproxy = get_player_proxy(clientip)
    assert playerproxy is not None
    playerproxy.commands.append(command)
    
    #
    if "/checkstatus" in command:
        await imme_handle_check_status(rpggame[clientip], playerproxy)
    elif "/perception" in command:
        await imme_handle_perception(rpggame[clientip], playerproxy)
    else:
        playerproxy.commands.append(command)
        await rpggame[clientip].async_execute()

    messages: list[TupleModel] = []
    for message in playerproxy.clientmessages[-TEST_CLIENT_SHOW_MESSAGE_COUNT:]:
        messages.append(TupleModel(who=message[0], what=message[1]))

    return messages

async def main(clientip: str , command: str) -> list[TupleModel]:
    if "/start" in command:
        return await start(clientip)
    elif "/login" in command:
        return await login(clientip)
    elif "/quit" in command:
        return await quitgame(clientip)
    # elif "/run" in command:
    #     await run()
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