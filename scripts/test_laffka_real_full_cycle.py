import asyncio
import sys
import os
from loguru import logger

# Добавляем корневую директорию проекта в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.laffka_service import laffka_service

async def test_laffka_real_full_cycle():
    """
    Реальный тест полного цикла:
    1. Поиск самого дешевого листинга на маркете.
    2. Покупка этого стикера (тратит реальные TON с баланса Laffka).
    3. Вывод купленного стикера на стикербот (СС).
    """
    logger.info("🚀 Запуск РЕАЛЬНОГО теста полного цикла Laffka...")

    # 1. Поиск листинга дешевле 1 TON
    logger.info("🔍 Шаг 1: Поиск стикера дешевле 1 TON на маркете (с пагинацией)...")
    
    target_item = None
    cursor = None
    pages_checked = 0
    max_pages = 5 # Чтобы не зависнуть надолго

    while pages_checked < max_pages:
        # Используем сортировку по возрастанию цены (low high)
        listings_data = await laffka_service.get_listings(cursor=cursor, sort="price-low-high")
        items = listings_data.get("items", [])
        
        if not items:
            break

        for item in items:
            if float(item["price"]) < 1.0:
                target_item = item
                break
        
        if target_item:
            break
            
        cursor = listings_data.get("next_cursor")
        if not cursor:
            break
        
        pages_checked += 1
        logger.info(f"📄 Проверено страниц: {pages_checked}, ищем дальше...")
    
    if not target_item:
        logger.error(f"❌ Не удалось найти стикеры дешевле 1 TON на первых {pages_checked + 1} страницах.")
        return

    logger.debug(f"DEBUG: Выбранный элемент: {target_item}")
    
    listing_id = target_item["id"]
    # Попробуем найти ID стикера в разных полях
    sticker_id = target_item.get("sticker", {}).get("id") or "unknown"
    price_ton = float(target_item["price"])
    
    logger.info(f"✅ Найден стикер: {target_item.get('sticker', {}).get('name', 'Unknown')}")
    logger.info(f"📍 ID листинга: {listing_id}")
    logger.info(f"📍 Sticker ID: {sticker_id}")
    logger.info(f"💰 Цена: {price_ton} TON")

    # 2. Покупка
    logger.info(f"🛒 Шаг 2: Попытка покупки листинга {listing_id}...")
    # ВНИМАНИЕ: Это спишет реальные TON с баланса аккаунта, чей initData в .env
    purchase_result = await laffka_service.purchase_listing(listing_id)

    if "error" in purchase_result:
        logger.error(f"❌ Ошибка при покупке: {purchase_result['error']}")
        if purchase_result.get("status") == 401:
            logger.warning("💡 СОВЕТ: Твоя LAFFKA_INIT_DATA в .env просрочена или неверна.")
        return

    # Извлекаем UUID купленного стикера из ответа
    # Согласно требованиям, UUID для вывода берется из sticker.id
    sticker_uuid = purchase_result.get("sticker", {}).get("id") or purchase_result.get("id")
    
    if not sticker_uuid:
        logger.error(f"❌ В ответе покупки отсутствует ID стикера: {purchase_result}")
        return

    logger.success(f"🎉 Стикер успешно куплен! UUID в системе Laffka: {sticker_uuid}")
    logger.debug(f"Данные ответа: {purchase_result}")

    # 3. Вывод на СС (Стикербот)
    logger.info(f"📤 Шаг 3: Попытка вывода стикера {sticker_uuid} на СС...")
    
    # Определяем тип вывода на основе sticker_type из ответа
    sticker_obj = purchase_result.get("sticker", {})
    sticker_type = sticker_obj.get("sticker_type", "offchain")
    
    if sticker_type == "onchain":
        from app.core.config import settings
        logger.info(f"🔗 Стикер ончейн, вызываем withdraw_nft на адрес {settings.WALLET_ADDRESS}...")
        withdraw_success = await laffka_service.withdraw_nft(str(sticker_uuid), settings.WALLET_ADDRESS)
    else:
        logger.info("📦 Стикер оффчейн, вызываем обычный withdraw_sticker...")
        withdraw_success = await laffka_service.withdraw_sticker(str(sticker_uuid))

    if withdraw_success:
        logger.success(f"✅ ПОЛНЫЙ ЦИКЛ ЗАВЕРШЕН: Стикер {sticker_uuid} отправлен на вывод!")
    else:
        logger.error(f"❌ Ошибка на этапе вывода стикера {sticker_uuid}.")

if __name__ == "__main__":
    # Проверка наличия initData
    from app.core.config import settings
    if not settings.LAFFKA_INIT_DATA or ("query_id" not in settings.LAFFKA_INIT_DATA and "user=" not in settings.LAFFKA_INIT_DATA):
        logger.error("❌ LAFFKA_INIT_DATA в .env не заполнена или имеет неверный формат!")
        sys.exit(1)
        
    asyncio.run(test_laffka_real_full_cycle())
