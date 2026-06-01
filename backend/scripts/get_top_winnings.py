import asyncio
import sys
import os
from datetime import datetime, date, timedelta
from typing import Optional


#FLAGS
#--all-time
#--date 2024-06-01
#--limit 10

# Добавляем корень проекта в sys.path, чтобы импорты backend.* работали
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select, and_
from backend.db.session import async_session_factory
from backend.models.sticker_action import StickerAction
from backend.models.sticker import UserSticker, StickerCatalog
from backend.models.user import User
from backend.models.enums import StickerActionType

async def get_top_winnings(
    target_date: Optional[date] = None, 
    limit: int = 10,
    all_time: bool = False
):
    """
    Собирает лучшие выигрыши из БД по стоимости (TON).
    Выводит имя победителя, название стикера и его стоимость.
    """
    async with async_session_factory() as db:
        # Основной запрос: соединяем действия со стикерами, каталог и пользователей
        query = (
            select(
                StickerAction,
                User,
                UserSticker,
                StickerCatalog
            )
            .join(UserSticker, StickerAction.sticker_pool_id == UserSticker.id)
            .join(StickerCatalog, UserSticker.catalog_id == StickerCatalog.id)
            .join(User, StickerAction.user_id == User.id)
            .where(StickerAction.action_type == StickerActionType.DROP)
        )

        # Фильтрация по времени
        if not all_time:
            if target_date:
                # За конкретный день
                start_dt = datetime.combine(target_date, datetime.min.time())
                end_dt = datetime.combine(target_date, datetime.max.time())
                query = query.where(and_(StickerAction.created_at >= start_dt, StickerAction.created_at <= end_dt))
            else:
                # По умолчанию за последние 24 часа
                last_24h = datetime.now() - timedelta(hours=24)
                query = query.where(StickerAction.created_at >= last_24h)

        # Сортировка по стоимости в TON (самые дорогие сверху)
        query = query.order_by(UserSticker.ton_price.desc(), UserSticker.stars_price.desc())
        query = query.limit(limit)

        result = await db.execute(query)
        rows = result.all()

        if not rows:
            period = f"за {target_date}" if target_date else ("за всё время" if all_time else "за последние 24 часа")
            print(f"\n[!] Выигрышей {period} не найдено.")
            return

        print(f"\n{'Дата':<18} | {'Победитель':<25} | {'Стикер':<30} | {'TON':<8} | {'Stars':<8}")
        print("-" * 95)
        
        for action, user, sticker_inst, catalog in rows:
            # Подтягиваем имя (полное имя или юзернейм)
            winner_name = user.full_name or user.username or f"ID: {user.telegram_id}"
            sticker_name = catalog.name
            won_at = action.created_at.strftime("%Y-%m-%d %H:%M")
            ton_price = sticker_inst.ton_price or 0.0
            stars_price = sticker_inst.stars_price or 0
            
            # Обрезаем длинные имена для красоты таблицы
            winner_display = (winner_name[:22] + '..') if len(winner_name) > 24 else winner_name
            sticker_display = (sticker_name[:27] + '..') if len(sticker_name) > 29 else sticker_name
            
            print(f"{won_at:<18} | {winner_display:<25} | {sticker_display:<30} | {ton_price:<8.2f} | {stars_price:<8}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Скрипт для сбора топовых выигрышей из базы данных.")
    parser.add_argument("--date", type=str, help="Дата в формате YYYY-MM-DD (например, 2024-06-01)")
    parser.add_argument("--limit", type=int, default=10, help="Количество записей в топе (по умолчанию 10)")
    parser.add_argument("--all-time", action="store_true", help="Собрать топ за всё время работы")
    
    args = parser.parse_args()
    
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print("[!] Ошибка: Неверный формат даты. Используйте ГГГГ-ММ-ДД")
            sys.exit(1)
            
    asyncio.run(get_top_winnings(target_date=target_date, limit=args.limit, all_time=args.all_time))