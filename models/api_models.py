from pydantic import BaseModel


class APIEndpointConfigurationRequest(BaseModel):
    content: str = ""


class APIEndpointConfiguration(BaseModel):
    TEST_URL: str = ""


class APIEndpointConfiguratioResponse(BaseModel):
    content: str = ""
    api_endpoints: APIEndpointConfiguration = APIEndpointConfiguration()
    error: int = 0
    message: str = ""
