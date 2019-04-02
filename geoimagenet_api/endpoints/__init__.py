from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import RedirectResponse

from geoimagenet_api import __version__, __author__, __email__
from geoimagenet_api.openapi_schemas import ApiInfo
from geoimagenet_api.endpoints import (
    taxonomy,
    taxonomy_classes,
    users,
    batches,
    annotations,
)

router = APIRouter()

router.include_router(users.router, tags=["Users"])
router.include_router(taxonomy.router, tags=["Taxonomy"])
router.include_router(taxonomy_classes.router, tags=["Taxonomy Classes"])
router.include_router(batches.router, tags=["Batches"])
router.include_router(annotations.router, tags=["Annotations"])


@router.get("/", response_model=ApiInfo, summary="General information")
def get(request: Request):
    docs_url = str(request.url) + "docs"
    redoc_url = str(request.url) + "redoc"
    changelog_url = str(request.url) + "changelog"
    return ApiInfo(
        name="GeoImageNet API",
        version=__version__,
        authors=__author__,
        email=__email__,
        documetation_url_swagger=docs_url,
        documetation_url_redoc=redoc_url,
        changelog_url=changelog_url,
    )


@router.get("/ui/", include_in_schema=False)
def redirect_ui(request: Request):
    return RedirectResponse(url=request.url.path.replace("ui/", "redoc"))
