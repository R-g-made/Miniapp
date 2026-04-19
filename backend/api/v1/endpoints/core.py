from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
import os
from backend.schemas.common import BootstrapResponse
from backend.builders.bootstrap import BootstrapBuilder
from backend.api import deps
from backend.crud.issuer import issuer as crud_issuer
from backend.core.config import settings
from backend.models.enums import Language
from backend.core.constants import SORTING_OPTIONS

router = APIRouter()

@router.get("/tonconnect-manifest.json", include_in_schema=False)
async def get_manifest():
    """
    Отдает манифест для TON Connect
    """
    manifest_path = os.path.join(os.getcwd(), "frontend", "public", "tonconnect-manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path)
    return {"error": "Manifest not found"}

@router.get("/bootstrap", response_model=BootstrapResponse)
async def bootstrap(
    lang: Language = Language.EN,
    db=Depends(deps.get_db)
):
    """
    Инициализация приложения: справочники и конфиги.
    """
    builder = BootstrapBuilder()
    
    issuers = await crud_issuer.get_all_active(db)
    builder.with_issuers(issuers)
    
    current_options = SORTING_OPTIONS.get(lang, SORTING_OPTIONS[Language.EN])
    builder.with_sorting_options(current_options)
    
    builder.with_config(
        maintenance=False, 
        min_deposit=settings.MIN_DEPOSIT,
        ref_percentage=settings.REFERRAL_PERCENTAGE
    )
    
    return builder.build()
