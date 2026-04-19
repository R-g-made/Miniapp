from fastapi import APIRouter, Depends, status
from typing import Optional, List
from uuid import UUID
from loguru import logger
from backend.api import deps
from backend.schemas.case import CaseResponse, CaseListResponse, CaseOpenRequest, CaseOpenResponse
from backend.crud.case import case as crud_case
from backend.builders.case_response import CaseResponseBuilder, CaseOpenBuilder
from backend.services.case_service import case_service
from backend.models.enums import Currency
from backend.core.exceptions import EntityNotFound, InvalidOperation, InsufficientFunds

router = APIRouter()

@router.get("", response_model=CaseListResponse)
async def get_cases(
    offset: int = 0,
    limit: int = 10,
    issuer_slug: Optional[str] = None,
    sort_by: Optional[str] = None,
    db = Depends(deps.get_db)
):
    """
    Каталог доступных кейсов с фильтрацией и сортировкой.
    """
    logger.debug(f"API: Fetching cases catalog (offset={offset}, limit={limit}, issuer={issuer_slug})")
    cases = await crud_case.get_catalog(
        db=db,
        skip=offset,
        limit=limit,
        sort_by=sort_by,
        issuer_slug=issuer_slug
    )
    return( CaseResponseBuilder()
    .with_cases(cases)
    .build_list()
    )


@router.get("/{slug}", response_model=CaseResponse)
async def get_case(slug: str, db = Depends(deps.get_db)):
    """
    Получить детальную информацию о кейсе по его slug.
    """
    logger.debug(f"API: Fetching case details for slug: {slug}")
    case = await crud_case.get_by_slug(db=db, slug=slug)
    if not case:
        logger.warning(f"API: Case not found with slug: {slug}")
        raise EntityNotFound("Case not found")
    
    return( CaseResponseBuilder()
    .with_case(case)
    .build_single()
    )


@router.post("/{slug}/open", response_model=CaseOpenResponse)
async def open_case(
    slug: str,
    obj_in: CaseOpenRequest,
    current_user = Depends(deps.get_current_user),
    db = Depends(deps.get_db)
):
    """
    Открыть кейс за TON или Stars.
    """
    logger.info(f"API: User {current_user.telegram_id} is opening case '{slug}' using {obj_in.currency}")
    
    won_sticker, price, new_balance = await case_service.open_case(
        db=db,
        user=current_user,
        case_slug=slug,
        currency=obj_in.currency
    )
    
    logger.info(f"API: Case '{slug}' opened successfully for user {current_user.telegram_id}. Won sticker: {won_sticker.catalog.name}")
    
    return (
        CaseOpenBuilder()
        .with_drop(won_sticker)
        .with_balance(new_balance, obj_in.currency)
        .build()
    )
