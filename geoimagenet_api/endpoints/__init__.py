from fastapi import APIRouter
from starlette.requests import Request

from geoimagenet_api import __version__, __author__, __email__
from geoimagenet_api.openapi_schemas import ApiInfo
from geoimagenet_api.endpoints import taxonomy, taxonomy_classes, users, batches, annotations

router = APIRouter()

router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(taxonomy.router, prefix="/taxonomy", tags=["taxonomy"])
router.include_router(
    taxonomy_classes.router, prefix="/taxonomy_classes", tags=["taxonomy_classes"]
)
router.include_router(batches.router, prefix="/batches", tags=["batches"])
router.include_router(annotations.router, prefix="/annotations", tags=["annotations"])


@router.get("/", response_model=ApiInfo)
def get(request: Request):
    docs_url = str(request.url) + "docs"
    changelog_url = str(request.url) + "changelog"
    return ApiInfo(
        name="GeoImageNet API",
        version=__version__,
        authors=__author__,
        email=__email__,
        documetation_url=docs_url,
        changelog_url=changelog_url,
    )
