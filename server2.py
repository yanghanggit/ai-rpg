from fastapi import FastAPI
from loguru import logger
from ws_config import WS_CONFIG, GameStageManager, LoginData
from typing import Dict, Any
import datetime





app = FastAPI()


game_stage_mamager = GameStageManager()


@app.post("/login/")
async def login(data: LoginData) -> Dict[str, Any]:
    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return LoginData(username=data.username, response=str(time)).model_dump()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=WS_CONFIG.Host.value, port=WS_CONFIG.Port.value)
