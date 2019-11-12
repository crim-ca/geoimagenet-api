from fastapi import APIRouter
from . import annotations, status, import_export

router = APIRouter()
router.include_router(annotations.router)
router.include_router(status.router)
router.include_router(import_export.router)
