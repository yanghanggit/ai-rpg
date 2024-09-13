from fastapi import FastAPI
from pydantic import BaseModel
from ws_config import WS_CONFIG

app = FastAPI()


# 定义接收的数据模型
class Data(BaseModel):
    message: str


# 定义一个POST接口
@app.post("/process/")
async def process_data(data: Data) -> dict[str, str]:
    response_message = f"服务器收到消息：{data.message}"
    return {"response": response_message}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=WS_CONFIG.Host.value, port=WS_CONFIG.Port.value)
