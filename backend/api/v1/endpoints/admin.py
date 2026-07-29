from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
import datetime

from backend.db.session import get_db
from backend.models.user import User
from backend.models.sticker import UserSticker, StickerCatalog
from backend.models.sticker_action import StickerAction
from backend.models.case import Case
from backend.models.associations import CaseItem
from backend.models.transaction import Transaction
from backend.models.enums import StickerActionType, TransactionType, Currency
from backend.schemas.admin import (
    DashboardStats, DropHistoryResponse, DropCard, 
    StickerPoolItem, UserAdminInfo, CaseCreate, 
    CatalogStickerCreate, BroadcastCreate, AdminLogin
)
from backend.core.config import settings
from fastapi.security import APIKeyHeader

router = APIRouter()

# --- Auth Middleware ---
X_ADMIN_TOKEN = APIKeyHeader(name="X-Admin-Token")

async def verify_admin(token: str = Depends(X_ADMIN_TOKEN)):
    if token != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid admin password")
    return token

@router.post("/login")
async def login(data: AdminLogin):
    if data.password == settings.ADMIN_PASSWORD:
        return {"token": settings.ADMIN_PASSWORD}
    raise HTTPException(status_code=401, detail="Wrong password")

# --- 1. Блок "Аналитика и Статистика" ---

@router.get("/stats/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    date: Optional[datetime.date] = None,
    all_time: bool = False,
    db: AsyncSession = Depends(get_db),
    _admin = Depends(verify_admin)
):
    # Определяем фильтр по времени
    period_label = "All Time"
    time_filter_action = []
    time_filter_tx = []
    
    if not all_time:
        if date:
            period_label = str(date)
            time_filter_action.append(func.date(StickerAction.created_at) == date)
            time_filter_tx.append(func.date(Transaction.created_at) == date)
        else:
            period_label = "Today"
            today = datetime.date.today()
            time_filter_action.append(func.date(StickerAction.created_at) == today)
            time_filter_tx.append(func.date(Transaction.created_at) == today)

    # Общее количество выбитых предметов за период
    dropped_count_query = select(func.count(StickerAction.id)).where(
        and_(StickerAction.action_type == StickerActionType.DROP, *time_filter_action)
    )
    dropped_count = await db.scalar(dropped_count_query) or 0

    # Общая стоимость по флору (Floor Price) выбитых предметов за период
    floor_price_query = select(
        func.sum(StickerCatalog.floor_price_ton),
        func.sum(StickerCatalog.floor_price_stars)
    ).select_from(StickerAction).join(
        UserSticker, StickerAction.sticker_pool_id == UserSticker.id
    ).join(
        StickerCatalog, UserSticker.catalog_id == StickerCatalog.id
    ).where(
        and_(StickerAction.action_type == StickerActionType.DROP, *time_filter_action)
    )
    
    floor_res = await db.execute(floor_price_query)
    floor_ton, floor_stars = floor_res.first()

    # Общая сумма, потраченная пользователями (OPEN_CASE) за период
    # Используем таблицу Transaction для точности по времени
    spent_ton_query = select(func.sum(Transaction.amount)).where(
        and_(
            Transaction.type == TransactionType.OPEN_CASE,
            Transaction.currency == Currency.TON,
            *time_filter_tx
        )
    )
    spent_stars_query = select(func.sum(Transaction.amount)).where(
        and_(
            Transaction.type == TransactionType.OPEN_CASE,
            Transaction.currency == Currency.STARS,
            *time_filter_tx
        )
    )
    
    # Если all_time, можно брать из User.total_spent_* для быстроты, но для консистентности используем транзакции
    spent_ton = await db.scalar(spent_ton_query) or 0.0
    spent_stars = await db.scalar(spent_stars_query) or 0.0

    return DashboardStats(
        total_dropped_items=dropped_count,
        total_floor_price_ton=floor_ton or 0.0,
        total_floor_price_stars=floor_stars or 0.0,
        total_spent_ton=spent_ton,
        total_spent_stars=spent_stars,
        period_label=period_label
    )

@router.get("/stats/top-drops", response_model=DropHistoryResponse)
async def get_top_drops(
    date: Optional[datetime.date] = None,
    all_time: bool = False,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin = Depends(verify_admin)
):
    query = select(StickerAction).join(
        UserSticker, StickerAction.sticker_pool_id == UserSticker.id
    ).join(
        StickerCatalog, UserSticker.catalog_id == StickerCatalog.id
    ).join(
        User, StickerAction.user_id == User.id
    ).where(StickerAction.action_type == StickerActionType.DROP).options(
        selectinload(StickerAction.user_sticker).selectinload(UserSticker.catalog),
        selectinload(StickerAction.user_sticker).selectinload(UserSticker.owner)
    )

    if not all_time:
        if date:
            query = query.where(func.date(StickerAction.created_at) == date)
        else:
            # Сегодня
            query = query.where(func.date(StickerAction.created_at) == datetime.date.today())

    # Сортировка по стоимости флора
    query = query.order_by(StickerCatalog.floor_price_ton.desc())

    # Pagination
    total_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(total_query) or 0

    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    actions = result.scalars().all()

    items = [
        DropCard(
            sticker_id=a.user_sticker.id,
            image_url=a.user_sticker.catalog.image_url,
            name=a.user_sticker.catalog.name,
            player_name=a.user_sticker.owner.username or a.user_sticker.owner.full_name if a.user_sticker.owner else "Unknown",
            price_ton=a.user_sticker.catalog.floor_price_ton,
            price_stars=a.user_sticker.catalog.floor_price_stars,
            date=a.created_at
        ) for a in actions
    ]

    return DropHistoryResponse(items=items, total=total, page=page, size=size)

# --- 2. Блок "Пул Стикеров" ---

@router.get("/stickers/pool", response_model=List[StickerPoolItem])
async def get_sticker_pool(
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _admin = Depends(verify_admin)
):
    # Подсчет оставшихся в пуле для каждого каталога
    subquery = select(
        UserSticker.catalog_id,
        func.count(UserSticker.id).label("count")
    ).where(
        and_(UserSticker.owner_id == None, UserSticker.is_available == True)
    ).group_by(UserSticker.catalog_id).subquery()

    query = select(
        StickerCatalog,
        func.coalesce(subquery.c.count, 0).label("remaining")
    ).outerjoin(subquery, StickerCatalog.id == subquery.c.catalog_id)

    if search:
        query = query.where(StickerCatalog.name.ilike(f"%{search}%"))

    result = await db.execute(query)
    items = []
    for row in result.all():
        catalog, remaining = row
        items.append(StickerPoolItem(
            id=catalog.id,
            image_url=catalog.image_url,
            name=catalog.name,
            count_remaining=remaining,
            floor_price_ton=catalog.floor_price_ton,
            floor_price_stars=catalog.floor_price_stars
        ))
    return items

@router.patch("/stickers/{sticker_id}/owner")
async def change_sticker_owner(
    sticker_id: UUID,
    new_owner_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    _admin = Depends(verify_admin)
):
    query = select(UserSticker).where(UserSticker.id == sticker_id)
    res = await db.execute(query)
    sticker = res.scalar_one_or_none()
    if not sticker:
        raise HTTPException(status_code=404, detail="Sticker not found")
    
    sticker.owner_id = new_owner_id
    if new_owner_id:
        sticker.is_available = False # Больше не в пуле
    else:
        sticker.is_available = True # Возвращаем в пул
        
    await db.commit()
    return {"status": "success"}

# --- 3. Блок "Управление Игроками" ---

@router.get("/users", response_model=List[UserAdminInfo])
async def get_users(
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _admin = Depends(verify_admin)
):
    query = select(User)
    if search:
        query = query.where(
            (User.username.ilike(f"%{search}%")) | 
            (User.full_name.ilike(f"%{search}%")) | 
            (func.cast(User.telegram_id, String).ilike(f"%{search}%"))
        )
    
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/users/{user_id}/reset-balance")
async def reset_user_balance(user_id: UUID, db: AsyncSession = Depends(get_db), _admin = Depends(verify_admin)):
    query = update(User).where(User.id == user_id).values(balance_ton=0.0, balance_stars=0.0)
    await db.execute(query)
    await db.commit()
    return {"status": "success"}

@router.post("/users/{user_id}/adjust-balance")
async def adjust_user_balance(
    user_id: UUID, 
    amount_ton: float = 0.0, 
    amount_stars: float = 0.0,
    db: AsyncSession = Depends(get_db),
    _admin = Depends(verify_admin)
):
    query = select(User).where(User.id == user_id)
    res = await db.execute(query)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.balance_ton += amount_ton
    user.balance_stars += amount_stars
    await db.commit()
    return {"status": "success"}

# --- 4. Блок "Конструктор Кейсов" ---

@router.get("/catalog/items", response_model=List[StickerPoolItem])
async def get_catalog_items(db: AsyncSession = Depends(get_db), _admin = Depends(verify_admin)):
    # Просто все элементы каталога для выбора в кейс
    query = select(StickerCatalog)
    result = await db.execute(query)
    catalogs = result.scalars().all()
    
    return [
        StickerPoolItem(
            id=c.id,
            image_url=c.image_url,
            name=c.name,
            count_remaining=0, # Не важно здесь
            floor_price_ton=c.floor_price_ton,
            floor_price_stars=c.floor_price_stars
        ) for c in catalogs
    ]

@router.post("/cases")
async def create_case(case_in: CaseCreate, db: AsyncSession = Depends(get_db), _admin = Depends(verify_admin)):
    new_case = Case(
        name=case_in.name,
        slug=case_in.slug,
        price_ton=case_in.price_ton,
        price_stars=case_in.price_stars,
        image_url=case_in.image_url,
        styles=case_in.styles,
        is_active=True
    )
    db.add(new_case)
    await db.flush() # Получаем ID

    for catalog_id_str, weight in case_in.item_weights.items():
        item = CaseItem(
            case_id=new_case.id,
            sticker_catalog_id=UUID(catalog_id_str),
            weight=weight
        )
        db.add(item)
    
    await db.commit()
    return {"status": "success", "id": new_case.id}

# --- 4.5 Блок создание каталожного стикера ---

@router.post("/catalog/stickers")
async def create_catalog_sticker(sticker_in: CatalogStickerCreate, db: AsyncSession = Depends(get_db), _admin = Depends(verify_admin)):
    new_sticker = StickerCatalog(**sticker_in.model_dump())
    db.add(new_sticker)
    await db.commit()
    return {"status": "success", "id": new_sticker.id}

# --- 5. Блок "Рассылка в Боте" ---

@router.post("/bot/broadcast")
async def start_broadcast(broadcast_in: BroadcastCreate, db: AsyncSession = Depends(get_db), _admin = Depends(verify_admin)):
    # В реальном приложении здесь будет вызов сервиса рассылки
    # Например: await notification_service.broadcast(message=broadcast_in.message, media_url=broadcast_in.media_url)
    
    # Для демонстрации просто найдем всех пользователей и создадим задачу
    # В данном проекте есть backend/scripts/broadcast.py
    
    from backend.services.notification_service import notification_service
    
    # Это может быть долгая операция, лучше запускать в фоне
    # Но для админки можем просто запустить через сервис
    
    # await notification_service.send_broadcast(broadcast_in.message, broadcast_in.media_url)
    
    return {"status": "broadcast_started"}
