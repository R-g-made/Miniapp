import asyncio
import os
import sys

# Добавляем путь к корню проекта, чтобы импорты работали корректно
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.db.session import async_session_maker
from backend.models.associations import CaseItem
from backend.models.case import Case
from backend.models.sticker import UserSticker, StickerCatalog
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

async def main():
    print("Подключение к базе данных...")
    async with async_session_maker() as db:
        print("Получение данных о кейсах...")
        # Получаем все CaseItem с подгруженными кейсами
        stmt = select(CaseItem).options(
            selectinload(CaseItem.case)
        )
        res = await db.execute(stmt)
        case_items = res.scalars().all()

        if not case_items:
            print("Не найдено ни одного элемента CaseItem в базе данных.")
            return

        # Группируем кейсы по catalog_id
        catalog_to_cases = {}
        for item in case_items:
            cat_id = item.sticker_catalog_id
            if cat_id not in catalog_to_cases:
                catalog_to_cases[cat_id] = set()
            if item.case:
                catalog_to_cases[cat_id].add(item.case.name)

        missing = []
        print(f"Проверка {len(catalog_to_cases)} уникальных стикеров из кейсов...")
        
        for cat_id, cases in catalog_to_cases.items():
            # Проверяем наличие стикеров в пуле (is_available=True, owner_id=None)
            query = select(func.count(UserSticker.id)).where(
                UserSticker.catalog_id == cat_id,
                UserSticker.owner_id == None,
                UserSticker.is_available == True
            )
            available = await db.scalar(query) or 0
            
            # В PostgreSQL мы должны строго использовать тип UUID
            # Поэтому мы не делаем fallback-запрос со строковым ID для PostgreSQL, 
            # чтобы избежать ошибки "operator does not exist: uuid = character varying"
            
            # Если стикеров нет в пуле
            if available == 0:
                cat_stmt = select(StickerCatalog).where(StickerCatalog.id == cat_id)
                cat_res = await db.execute(cat_stmt)
                catalog = cat_res.scalar_one_or_none()
                
                if catalog:
                    missing.append({
                        "id": str(catalog.id),
                        "name": catalog.name,
                        "collection": catalog.collection_name or "Без коллекции",
                        "cases": list(cases)
                    })
        
        if not missing:
            print("\n Все стикеры из кейсов есть в наличии в пуле!")
        else:
            print(f"\nНайдено {len(missing)} недостающих стикеров:\n")
            for m in missing:
                cases_str = ", ".join(m['cases']) if m['cases'] else "Неизвестный кейс"
                print(f"Стикер: {m['name']}")
                print(f"Коллекция: {m['collection']}")
                print(f"Кейсы: {cases_str}")
                print(f"ID: {m['id']}")
                print("-" * 50)

if __name__ == "__main__":
    # Устанавливаем WindowsSelectorEventLoopPolicy для корректной работы asyncio в Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
