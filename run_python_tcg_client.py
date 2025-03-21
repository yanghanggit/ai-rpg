from typing import Final
import requests
from loguru import logger
import datetime

from tcg_models.api_models import (
    APIEndpointConfigurationRequest,
    APIEndpointConfiguration,
    APIEndpointConfiguratioResponse,
)


class ClientContext:

    def __init__(self, user_name: str, api_endpoints: str) -> None:
        self._user_name: Final[str] = user_name
        self._api_endpoints: Final[str] = api_endpoints
        self._api_endpoint_config = APIEndpointConfiguration()

    @property
    def user_name(self) -> str:
        return self._user_name

    @property
    def api_endpoints(self) -> str:
        return self._api_endpoints


##############################################################################################################################################
def _request_api_endpoints(
    client_context: ClientContext,
) -> None:

    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response = requests.post(
        client_context.api_endpoints,
        json=APIEndpointConfigurationRequest(content=f"time = {time}").model_dump(),
    )

    api_endpoint_response = APIEndpointConfiguratioResponse.model_validate(
        response.json()
    )

    if api_endpoint_response.error > 0:
        logger.error(
            f"获取API路由失败: {api_endpoint_response.message}, {api_endpoint_response.error}"
        )
        return

    logger.info(f"获取API路由成功: {api_endpoint_response.model_dump_json()}")
    client_context._api_endpoint_config = api_endpoint_response.api_endpoints


###############################################################################################################################################


def main(client_context: ClientContext) -> None:
    logger.info("启动客户端")
    while True:

        usr_input = input(f"[{client_context.user_name}]:")
        if usr_input == "":
            continue

        if usr_input == "/quit" or usr_input == "/q":
            break

        if usr_input == "/api_endpoints" or usr_input == "/api":
            _request_api_endpoints(client_context)
            continue


###############################################################################################################################################
if __name__ == "__main__":

    app = ClientContext(
        "yanghang's python game client", "http://127.0.0.1:8000/api_endpoints/v1/"
    )
    main(app)
