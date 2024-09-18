import requests
from ws_config import WS_CONFIG, LoginData
from loguru import logger

my_username = "北京柏林互动科技有限公司"
url_login = f"http://{WS_CONFIG.Host.value}:{WS_CONFIG.Port.value}/login/"

if __name__ == "__main__":

    response2 = requests.post(
        url_login, json=LoginData(username=my_username, response="").model_dump()
    )
    login_response = LoginData.model_validate(response2.json())
    logger.info(f"response2: {login_response}")
