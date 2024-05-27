import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel
from auxiliary.player_input_command import PlayerCommandLogin
from auxiliary.player_proxy import create_player_proxy, get_player_proxy
from main_utils import create_rpg_game_then_build
from rpg_game import RPGGame

class TextInput(BaseModel):
    text_input: str

class TupleModel(BaseModel):  
    who: str 
    what: str

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static") 

rpggame: dict[str, RPGGame] = {}

async def start(clientip: str):
    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    worldname = "World2"
    game = create_rpg_game_then_build(worldname)
    if game is not None:
        global rpggame
        rpggame[clientip] = game
        rpggame[clientip].extendedcontext.user_ip = clientip
        logger.debug(f"User IP:{clientip} start a game.")

    await rpggame[clientip].async_execute()

    messages: list[TupleModel] = []
    messages.append(TupleModel(who=clientip, what="Start Success"))

    return messages

async def login(clientip: str):
    create_player_proxy(clientip)
    playerproxy = get_player_proxy(clientip)
    assert playerproxy is not None
    playerstartcmd = PlayerCommandLogin("/player-login", rpggame[clientip], playerproxy, "无名的复活者")
    playerstartcmd.execute()
    await rpggame[clientip].async_execute()

    messages: list[TupleModel] = []
    for message in playerproxy.clientmessages[-10:]:
        messages.append(TupleModel(who=message[0], what=message[1]))

    return messages

async def quitgame(clientip: str):
    quitclient = rpggame.pop(clientip, None)
    if quitclient is not None:
        logger.debug(f"User IP:{clientip} quit a game.")
        quitclient.exited = True
        quitclient.exit()

    messages: list[TupleModel] = []
    messages.append(TupleModel(who=clientip, what="Quit Success"))

    return messages

# async def run():
#     await rpggame.async_execute()

async def playerinput(clientip: str, command: str):
    playerproxy = get_player_proxy(clientip)
    assert playerproxy is not None
    playerproxy.commands.append(command)
    await rpggame[clientip].async_execute()

    messages: list[TupleModel] = []
    for message in playerproxy.clientmessages[-10:]:
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
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/submit")
async def submit_form(request: Request):
    json_data = await request.json()
    input_data: TextInput = TextInput(**json_data) 
    user_command: str = str(input_data.text_input)
    user_ip = request.client.host
    results = await main(user_ip, user_command)
    messages = [message_model.dict() for message_model in results]
    return JSONResponse(content={"command": user_command, "messages": messages})  

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)