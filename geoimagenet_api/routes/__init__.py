from geoimagenet_api.openapi_schemas import ApiInfo


def get() -> ApiInfo:
    return ApiInfo(name="Geoimagenet API", version="0.1")
