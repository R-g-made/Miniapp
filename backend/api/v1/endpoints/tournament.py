from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from backend.api.deps import get_current_user
from backend.db.session import get_db
from backend.models.user import User
from backend.services.tournament import tournament_service
from backend.crud.tournament import tournament_crud
from backend.builders.tournament_response import TournamentResponseBuilder
from backend.schemas.tournament import TournamentResponse

router = APIRouter()

@router.get("/leaderboard", response_model=TournamentResponse)
async def get_leaderboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    is_active = tournament_service.is_active()
    cache_data = await tournament_service.get_leaderboard_from_cache()
    
    # Если кэш пуст (например, после перезапуска сервера)
    if not cache_data.get("leaderboard"):
        settings = tournament_service.get_settings()
        if is_active:
            # Во время турнира - просто обновляем
            await tournament_service.update_leaderboard()
            cache_data = await tournament_service.get_leaderboard_from_cache()
        elif settings:
            # После турнира - проверяем, прошло ли меньше 24 часов
            try:
                end_time = datetime.strptime(settings["end_time"], "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                if now <= (end_time + timedelta(hours=24)):
                    await tournament_service.update_leaderboard()
                    cache_data = await tournament_service.get_leaderboard_from_cache()
            except Exception:
                pass

    settings = tournament_service.get_settings()
    end_time_str = settings.get("end_time")

    user_id_str = str(current_user.id)
    leaderboard = cache_data.get("leaderboard", [])
    
    # Ищем текущего пользователя в кэше лидеров (сравниваем строки для надежности)
    user_in_top = next((entry for entry in leaderboard if str(entry.get("user_id")) == user_id_str), None)

    current_user_place = "50+"
    current_user_volume = 0.0

    if user_in_top:
        current_user_place = str(user_in_top.get("place", "50+"))

    # Запрашиваем объем пользователя напрямую из БД всегда, чтобы объем обновлялся мгновенно
    try:
        # Парсим даты как UTC, а затем убираем tzinfo, так как в БД хранятся наивные даты
        start_time = datetime.strptime(settings["start_time"], "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc).replace(tzinfo=None)
        end_time = datetime.strptime(settings["end_time"], "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc).replace(tzinfo=None)
        
        volume = await tournament_crud.get_user_volume(db, current_user.id, start_time, end_time)
        current_user_volume = round(volume, 2)
        
        # Обновляем объем в кэшированном списке для консистентности на фронтенде
        if user_in_top:
            user_in_top["volume"] = current_user_volume
    except Exception:
        if user_in_top:
            current_user_volume = user_in_top.get("volume", 0.0)

    response = (
        TournamentResponseBuilder()
        .set_status(is_active, end_time_str)
        .set_cache_data(cache_data)
        .set_current_user_info(current_user_place, current_user_volume)
        .build()
    )
    return response