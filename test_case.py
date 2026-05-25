import asyncio
import uuid
from loguru import logger
from backend.db.session import async_session_factory
from backend.services.case_service import case_service
from backend.crud.user import user_repository
from backend.schemas.user import UserCreate
from backend.models.enums import Currency
from backend.models.issuer import Issuer
from backend.models.sticker import StickerCatalog, UserSticker
from backend.models.case import Case
from backend.models.associations import CaseItem

ITERATIONS = 1000
CURRENCY = Currency.TON

async def setup_test_data(db):
    """Создает фейковые стикеры и 3 кейса с разными суммами шансов"""
    logger.info("Генерация тестовых данных (Иссуер, Стикеры, Кейсы)...")
    
    # 1. Создаем Иссуера
    issuer = Issuer(name="Test Issuer", slug=f"test_issuer_{uuid.uuid4().hex[:6]}")
    db.add(issuer)
    await db.flush()

    # 2. Создаем 3 стикера (Дешевый, Средний, Дорогой)
    cat_cheap = StickerCatalog(name="Test Cheap (0.1 TON)", floor_price_ton=0.1, issuer_id=issuer.id)
    cat_med = StickerCatalog(name="Test Medium (1.0 TON)", floor_price_ton=1.0, issuer_id=issuer.id)
    cat_exp = StickerCatalog(name="Test Jackpot (50.0 TON)", floor_price_ton=50.0, issuer_id=issuer.id)
    db.add_all([cat_cheap, cat_med, cat_exp])
    await db.flush()

    # 3. Наполняем пул (чтобы не было Out of Stock во время 1000 открытий)
    pool = []
    for cat in [cat_cheap, cat_med, cat_exp]:
        for _ in range(4000): # С запасом
            pool.append(UserSticker(sticker_catalog_id=cat.id, is_available=True))
    db.add_all(pool)
    await db.flush()

    # 4. Создаем 3 кейса
    cases_to_test = []
    
    configs = [
        {"name": "Sum = 1.0 (100%)", "chances": [0.80, 0.15, 0.05]},
        {"name": "Sum = 1.1 (110%)", "chances": [0.80, 0.20, 0.10]},
        {"name": "Sum = 0.9 (90%)",  "chances": [0.70, 0.15, 0.05]}
    ]

    for conf in configs:
        slug = f"test_case_{uuid.uuid4().hex[:6]}"
        case_obj = Case(
            name=conf["name"], 
            slug=slug, 
            price_ton=1.0, # Цена кейса 1 TON
            is_active=True, 
            is_chance_distribution=False
        )
        db.add(case_obj)
        await db.flush()
        
        db.add_all([
            CaseItem(case_id=case_obj.id, sticker_catalog_id=cat_cheap.id, chance=conf["chances"][0]),
            CaseItem(case_id=case_obj.id, sticker_catalog_id=cat_med.id, chance=conf["chances"][1]),
            CaseItem(case_id=case_obj.id, sticker_catalog_id=cat_exp.id, chance=conf["chances"][2]),
        ])
        cases_to_test.append((conf["name"], slug))

    await db.commit()
    return cases_to_test

async def run_test():
    async with async_session_factory() as db:
        # Подготовка данных
        cases = await setup_test_data(db)
        
        # Создаем тестового пользователя
        test_tg_id = 999999999
        user = await user_repository.get_by_telegram_id(db, test_tg_id)
        if not user:
            user_in = UserCreate(telegram_id=test_tg_id, username="test_bot_user", full_name="Test User")
            user = await user_repository.create_user(db, user_in=user_in)
            
        user.balance_ton = 9999999.0
        db.add(user)
        await db.commit()

        for case_name, case_slug in cases:
            logger.info(f"\n--- Тестируем кейс: {case_name} ---")
            drops_count = {}
            total_spent = 0.0
            total_won = 0.0
            success_count = 0
            
            for i in range(ITERATIONS):
                try:
                    user = await user_repository.get_by_telegram_id(db, test_tg_id)
                    won_sticker, price, new_balance = await case_service.open_case(
                        db=db, user=user, case_slug=case_slug, currency=CURRENCY
                    )
                    
                    sticker_name = won_sticker.catalog.name
                    sticker_price = won_sticker.catalog.floor_price_ton or 0.0
                    
                    drops_count[sticker_name] = drops_count.get(sticker_name, 0) + 1
                    total_spent += price
                    total_won += sticker_price
                    success_count += 1
                except Exception as e:
                    logger.error(f"Ошибка: {e}")
                    break

            print("\n" + "="*50)
            print(f"📊 РЕЗУЛЬТАТЫ: {case_name}")
            print("="*50)
            print(f"💰 Потрачено: {total_spent:.2f} TON")
            print(f"🎁 Выиграно: {total_won:.2f} TON")
            
            rtp = (total_won / total_spent * 100) if total_spent > 0 else 0
            print(f"📈 Фактический RTP: {rtp:.2f}%")
            
            print("\n📦 СТАТИСТИКА ДРОПА:")
            sorted_drops = sorted(drops_count.items(), key=lambda x: x[1], reverse=True)
            for name, count in sorted_drops:
                percentage = (count / success_count * 100) if success_count > 0 else 0
                print(f" - {name}: {count} раз ({percentage:.2f}%)")
            print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(run_test())